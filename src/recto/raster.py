"""Rasterise PDF pages to greyscale images.

This is the only module that knows the input is a PDF. Everything downstream
works on numpy arrays and never needs to think about page objects again.

Rendering goes through pypdfium2 rather than pdf2image because pypdfium2 ships
its own PDFium build and needs no poppler binary on PATH, which is one fewer
thing to install on Windows.

Rendered pages are cached as PNGs on disk. A full volume takes a long time to
render, and tuning the later stages means running them over the same pages
again and again, so paying the render cost once is worth the disk space.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np
import pypdfium2 as pdfium

from recto.pngio import read_png, write_png

# The Jammy scans are 300 dpi bitonal images, and rendering a scan above its own
# resolution only interpolates. That softens every glyph edge, which costs
# accuracy in each connected-component stage that follows, so the default sits
# at the native resolution rather than higher.
DEFAULT_DPI = 300

# A PDF user space unit is 1/72 inch, so this converts dpi to a render scale.
POINTS_PER_INCH = 72

# FPDF_PAGEOBJ_IMAGE. pypdfium2 exposes page object types as plain integers.
_IMAGE_OBJECT = 3

DEFAULT_CACHE = Path("work/raster")


@dataclass(frozen=True)
class RasterPage:
    """One rendered page, both in memory and on disk."""

    index: int
    """Zero-based index into the PDF."""

    path: Path
    """Where the rendered PNG was written or read from."""

    image: np.ndarray
    """Greyscale uint8 array, shape (height, width)."""

    @property
    def number(self) -> int:
        """One-based page number, matching what a PDF viewer shows."""
        return self.index + 1


def parse_page_range(spec: str, page_count: int) -> list[int]:
    """Turn a page range string into sorted zero-based page indices.

    Accepts comma-separated single pages and inclusive ranges, written
    one-based to match what a PDF viewer shows: "9", "8-10", "1,4,7-9".

    Page numbers are one-based on the way in and zero-based everywhere inside
    the codebase. This function and RasterPage.number are the only two places
    that conversion is allowed to happen.
    """
    wanted: set[int] = set()

    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            first, _, last = part.partition("-")
            start = _to_index(first, page_count)
            stop = _to_index(last, page_count)
            if start > stop:
                raise ValueError(f"page range {part!r} runs backwards")
            wanted.update(range(start, stop + 1))
        else:
            wanted.add(_to_index(part, page_count))

    if not wanted:
        raise ValueError(f"{spec!r} selects no pages")

    return sorted(wanted)


def _to_index(text: str, page_count: int) -> int:
    """Parse a one-based page number and return its zero-based index."""
    text = text.strip()
    try:
        number = int(text)
    except ValueError:
        raise ValueError(f"{text!r} is not a page number") from None

    if number < 1:
        raise ValueError(f"page numbers start at 1, got {number}")
    if number > page_count:
        raise ValueError(
            f"page {number} is past the end of the document, which has {page_count}"
        )

    return number - 1


def native_dpi(page: pdfium.PdfPage) -> float | None:
    """Best guess at the resolution the scan on this page was made at.

    A scanned page is one large image object placed on an otherwise empty page,
    so dividing that image's pixel width by the page width in inches recovers
    the resolution it was captured at. Returns None for a page holding no image
    objects, which is what a born-digital PDF looks like.
    """
    width_inches = page.get_size()[0] / POINTS_PER_INCH
    if width_inches <= 0:
        return None

    best: float | None = None
    for obj in page.get_objects():
        if obj.type != _IMAGE_OBJECT:
            continue
        try:
            meta = obj.get_metadata()
        except Exception:
            # Some image objects refuse to report metadata. One unreadable
            # object should not cost us the reading from the others.
            continue
        dpi = meta.width / width_inches
        if best is None or dpi > best:
            best = dpi

    return best


def render_page(page: pdfium.PdfPage, dpi: int) -> np.ndarray:
    """Render one page to a greyscale uint8 array."""
    bitmap = page.render(scale=dpi / POINTS_PER_INCH, grayscale=True)
    array = bitmap.to_numpy()

    # A greyscale bitmap arrives as (height, width). Squeeze a trailing channel
    # axis if one ever shows up, so a renderer change cannot quietly hand a
    # three-dimensional array to stages that assume two.
    if array.ndim == 3:
        array = array[:, :, 0]

    return np.ascontiguousarray(array, dtype=np.uint8)


def cache_path(out_dir: Path, source: Path, index: int, dpi: int) -> Path:
    """Where the rendered PNG for one page lives.

    The filename carries the one-based page number so that browsing the cache
    folder lines up with browsing the PDF, and the dpi so that rendering the
    same book at two resolutions keeps both rather than overwriting one.
    """
    return out_dir / source.stem / f"p{index + 1:04d}@{dpi}dpi.png"


def rasterise(
    source: Path,
    *,
    pages: str | None = None,
    dpi: int = DEFAULT_DPI,
    out_dir: Path = DEFAULT_CACHE,
    force: bool = False,
) -> Iterator[RasterPage]:
    """Render the selected pages, yielding them in page order.

    Pages already in the cache are read from disk rather than rendered again,
    unless force is set. Yielding rather than returning a list matters: a full
    volume at 300 dpi is tens of megabytes per page, and holding all of them at
    once would be a problem long before the book ended.

    Replacing a PDF while keeping its filename will serve stale cached images,
    since the cache key is the filename rather than the file contents. Pass
    force in that case.
    """
    pdf = pdfium.PdfDocument(source)
    try:
        indices = parse_page_range(pages, len(pdf)) if pages else list(range(len(pdf)))

        for index in indices:
            path = cache_path(out_dir, source, index, dpi)

            if path.exists() and not force:
                yield RasterPage(index=index, path=path, image=read_png(path))
                continue

            image = render_page(pdf[index], dpi)
            write_png(path, image)
            yield RasterPage(index=index, path=path, image=image)
    finally:
        pdf.close()
