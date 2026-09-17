"""Rebuild the committed page fixtures from a source PDF.

The tests run against a dozen real pages committed under tests/fixtures/.
Real pages, because every constant in this codebase was measured on this scan
and a synthetic spread would not exercise any of them. Committed, because a
test suite that needs a 28 MB PDF on your Desktop is a test suite nobody else
can run.

They are downsampled to a third, 100 dpi, and pushed back to pure black and
white. Both choices were measured on the twelve pages:

    Resolution. Against a fold measured straight off the 300 dpi render, the
    detected gutter centre is within 4 source px at a third and within 2 at a
    half, so a third costs nothing this suite can see. A quarter costs nothing
    either, but it leaves a printed line pitch of 12 px against 16 at a third,
    and the later milestones band lines off that pitch. A third is the coarsest
    setting that keeps the pages useful for the tests that come after this one.

    Bitonal. The scan is already bitonal, so the grey that appears in a
    downsample is an artefact of the resize rather than anything in the book,
    and every stage here thresholds it away again at INK_BELOW. Thresholding it
    at write time instead takes the twelve files from 8.5 MB to 2.0 MB.

Expected values live in test_spread.py in source pixels at 300 dpi, not in
fixture pixels, so regenerating at a different factor does not invalidate them.

Run it from the repo root:

    python tests/make_fixtures.py C:/Users/cruz0/Desktop/part1.pdf
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium

from recto.pngio import write_png
from recto.raster import DEFAULT_DPI, render_page

FIXTURE_DIR = Path(__file__).parent / "fixtures"

FACTOR = 3
"""Downsample factor. See the module docstring for why it is not 2 or 4."""

INK_BELOW = 200
"""Matches the stages: anything darker than this is ink, so it survives as black."""

PAGES = {
    1: "woodcut headpiece, catalogue setting, both pages full",
    2: "title page, faint fold, near blank verso, the weakest gutter in the volume",
    4: "woodcut headpiece and printer's device, sparse verso",
    10: "blank recto, ornament at the foot of the verso",
    11: "opening page, headpiece and drop cap, two-lobed fold, blank verso",
    13: "plain body spread, gutter furthest to the right in the volume",
    24: "plain body spread",
    43: "plain body spread, widest fold measured, 81 px",
    56: "plain body spread, one of the narrowest folds, 38 px",
    60: "plain body spread, gutter furthest to the left in the volume",
    74: "plain body spread, tightest clearance between fold and neighbouring ink",
    76: "plain body spread, solid black fold",
}
"""Which pages, and what each one is here to exercise."""


def fixture_path(page_number: int, dpi: int) -> Path:
    """Where one fixture lives.

    The dpi goes in the filename, the same way the raster cache does it, because
    every pixel threshold in the pipeline is relative to a resolution and a test
    that loads a page has to know which one it is holding.
    """
    return FIXTURE_DIR / f"p{page_number:04d}@{dpi}dpi.png"


def downsample(image: np.ndarray, factor: int) -> np.ndarray:
    """Shrink by an integer factor and threshold back to black and white."""
    height, width = image.shape
    small = cv2.resize(
        image,
        (width // factor, height // factor),
        interpolation=cv2.INTER_AREA,
    )
    return np.where(small < INK_BELOW, 0, 255).astype(np.uint8)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="the source scan, 300 dpi")
    parser.add_argument("--factor", type=int, default=FACTOR)
    args = parser.parse_args()

    dpi = DEFAULT_DPI // args.factor
    pdf = pdfium.PdfDocument(args.pdf)
    try:
        for number, why in PAGES.items():
            page = render_page(pdf[number - 1], DEFAULT_DPI)
            small = downsample(page, args.factor)
            path = fixture_path(number, dpi)
            write_png(path, small)
            print(f"{path.name}  {small.shape[1]}x{small.shape[0]}  {why}")
    finally:
        pdf.close()


if __name__ == "__main__":
    main()
