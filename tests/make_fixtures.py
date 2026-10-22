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

The figure stage gets its own fixtures, because a third of the resolution is too
coarse for it. At 100 dpi the decorated I on page 11 fuses with the words beside
it and its box grows from 587 to 891 px wide; at 150 dpi it is still 84 px too
tall. So figure fixtures are 300 dpi crops, and they are crops of what the stage
actually receives, pages already split and straightened, because a tilt smears
exactly the row structure the stage reads. That makes them depend on the stages
before it: if the split or the deskew changes, regenerate. Nine crops, 0.8 MB.

The foot row and the column split also need 300 dpi (commit 17). At 100 dpi the
foot row merges with the last line on two of the 24 page frames, and the gap
between the columns is 5 to 20 px, against CLEAR at 2. Two kinds of fixture:

    Foot crops. Fourteen pages after mask-figures, cut from 300 rows above
    the foot row, or above the last line of type, down to the bottom of the
    page, full width. On all fourteen the bands under the first 100 rows of
    the crop agree with the full page within 1 px, and strip-foot cuts at the
    same row. The row where the crop starts is in the file name. 0.85 MB.

    One column page. p41 recto as split-columns receives it, head and foot
    already whited. It is a full page because the slant of the cut is fixed
    by the length of the gap: on crops of ten lines an applied shear came
    back up to 12 px per 1000 rows wrong. 0.56 MB.

Run it from the repo root:

    python tests/make_fixtures.py C:/Users/cruz0/Desktop/part1.pdf
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium

from recto.frames import Frame, Provenance
from recto.pipeline import Pipeline
from recto.pngio import write_png
from recto.raster import DEFAULT_DPI, render_page
from recto.stages.blank import DropBlank
from recto.stages.border import CropBorder
from recto.stages.deskew import Deskew
from recto.stages.despeckle import Despeckle
from recto.stages.figures import MaskFigures
from recto.stages.furniture import StripFoot, StripHead
from recto.stages.split import SplitSpread

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


FIGURE_DIR = FIXTURE_DIR / "figures"

FIGURE_CROPS = {
    "hieronymus": ("p0008-verso", (650, 280, 2700, 2350),
                   "headpiece and decorated H, the plan's named test case"),
    "initial-i": ("p0011-recto", (150, 2300, 1350, 3250),
                  "decorated I with the first line welded to its foot"),
    "device": ("p0004-verso", (950, 1700, 2150, 2750),
               "printer's device"),
    "initial-v": ("p0001-recto", (300, 1150, 1400, 1650),
                  "decorated V, the smallest figure in the volume"),
    "title-woodcut": ("p0002-recto", (200, 1650, 2550, 3450),
                      "title woodcut, the largest, with type welded to its frame"),
    "title-caps": ("p0002-recto", (250, 330, 2500, 800),
                   "display capitals as big as a drop cap, must survive"),
    "fused-column": ("p0012-recto", (1150, 2150, 2300, 3850),
                     "half a column fused into one component, must survive"),
    "fused-lines": ("p0076-recto", (300, 2550, 2300, 3900),
                    "body text fused into blobs, must survive"),
    "column-rule": ("p0076-recto", (950, 350, 1450, 3850),
                    "column rule broken up by speckle, 73 holes, must survive"),
}
"""Name: (page label, (x0, y0, x1, y1) on the straightened page, why it is here)."""


FOOT_DIR = FIXTURE_DIR / "foot"

FOOT_CROPS = {
    "p0012-verso": (3460, "catchword in, a single short word"),
    "p0025-recto": (3460, "signature C 3 and catchword"),
    "p0047-verso": (3430, "catchword in"),
    "p0049-recto": (3410, "signature G 3 and a lone ampersand"),
    "p0051-recto": (3390, "foot row, with noise labelled in both halves"),
    "p0054-recto": (3390, "direction line, signature and catchword, 823 px wide"),
    "p0059-verso": (3410, "catchword"),
    "p0066-verso": (3420, "catchword"),
    "p0071-verso": (3440, "catchword"),
    "p0076-recto": (3480, "foot row 22 px under the last line"),
    "p0019-recto": (3540, "speck and stroke under the foot row, right half"),
    "p0034-verso": (3410, "speck row under the last line, left half"),
    "p0069-recto": (3470, "stroke and speck under the catchword, right half"),
    "p0071-recto": (3480, "stroke under the foot row, right half"),
}
"""Page label: (first row of the crop on the page, why it is here).

The first ten carry the foot rows labelled by eye in commit 13. The last four
carry noise that comes back as a band when the run floor drops to 20 or 22 px.
Each crop starts 300 rows above the foot row or the last line, rounded down to
ten."""

COLUMN_DIR = FIXTURE_DIR / "columns"

COLUMN_PAGE = "p0041-recto"
"""The page for the column split. Of the part 1 body pages, it has the
narrowest gap, 19 px, among the pages where a shear of 0.01 to 0.03 either way
comes back exact to the step."""


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


def straightened_pages(pdf: pdfium.PdfDocument, numbers: set[int]) -> dict:
    """Each requested spread split, blank-checked and deskewed, keyed by label.

    Exactly the stages that run before MaskFigures, named here rather than
    taken from the registry so that adding a stage later does not silently
    change what the figure fixtures are.
    """
    before_figures = Pipeline(
        [CropBorder(), Despeckle(), SplitSpread(), DropBlank(), Deskew()]
    )
    pages = {}
    for number in sorted(numbers):
        frame = Frame(
            image=render_page(pdf[number - 1], DEFAULT_DPI),
            provenance=Provenance(source=Path("scan"), page_index=number - 1),
        )
        for page in before_figures.run(frame):
            pages[page.provenance.label] = page.image
    return pages


def write_figure_crops(pdf: pdfium.PdfDocument) -> None:
    numbers = {int(label[1:5]) for label, _, _ in FIGURE_CROPS.values()}
    pages = straightened_pages(pdf, numbers)
    for name, (label, (x0, y0, x1, y1), why) in FIGURE_CROPS.items():
        crop = pages[label][y0:y1, x0:x1]
        path = FIGURE_DIR / f"{name}.png"
        write_png(path, np.where(crop < INK_BELOW, 0, 255).astype(np.uint8))
        print(f"figures/{path.name}  {crop.shape[1]}x{crop.shape[0]}  {why}")


def masked_pages(pdf: pdfium.PdfDocument, labels: set[str]) -> dict:
    """Get each requested page as the strip-head stage receives it.

    The stages are named here and not taken from the registry. Thus a stage
    that a later commit adds does not change these fixtures.

    Args:
        pdf: The source scan.
        labels: Page labels, such as p0012-verso.

    Returns:
        Each requested page after mask-figures, keyed by label.
    """
    before_head = Pipeline(
        [
            CropBorder(),
            Despeckle(),
            SplitSpread(),
            DropBlank(),
            Deskew(),
            MaskFigures(),
        ]
    )
    pages = {}
    for number in sorted({int(label[1:5]) for label in labels}):
        frame = Frame(
            image=render_page(pdf[number - 1], DEFAULT_DPI),
            provenance=Provenance(source=Path("scan"), page_index=number - 1),
        )
        for page in before_head.run(frame):
            if page.provenance.label in labels:
                pages[page.provenance.label] = page
    return pages


def write_foot_crops(pdf: pdfium.PdfDocument) -> None:
    """Write the foot crops, each from its first row to the bottom of the page.

    Args:
        pdf: The source scan.
    """
    pages = masked_pages(pdf, set(FOOT_CROPS))
    for label, (y0, why) in FOOT_CROPS.items():
        crop = pages[label].image[y0:]
        path = FOOT_DIR / f"{label}@{y0}.png"
        write_png(path, np.where(crop < INK_BELOW, 0, 255).astype(np.uint8))
        print(f"foot/{path.name}  {crop.shape[1]}x{crop.shape[0]}  {why}")


def write_column_page(pdf: pdfium.PdfDocument) -> None:
    """Write the column page as split-columns receives it.

    The page is made bitonal before the head and the foot are found, because
    the tests give the stages a bitonal page.

    Args:
        pdf: The source scan.
    """
    page = masked_pages(pdf, {COLUMN_PAGE})[COLUMN_PAGE]
    page = page.derive(np.where(page.image < INK_BELOW, 0, 255).astype(np.uint8))
    for stage in (StripHead(), StripFoot()):
        page = stage.apply(page).frames[0]
    path = COLUMN_DIR / f"{COLUMN_PAGE}.png"
    write_png(path, page.image)
    print(f"columns/{path.name}  {page.width}x{page.height}  head and foot whited")


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
        write_figure_crops(pdf)
        write_foot_crops(pdf)
        write_column_page(pdf)
    finally:
        pdf.close()


if __name__ == "__main__":
    main()
