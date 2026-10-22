"""Loading the committed page fixtures.

One place that knows how a fixture filename is put together, so the tests can
say "give me the pages" and nothing else has to care that the dpi is encoded in
the name or that a fixture is a third of the size of the page it came from.

Fixtures are downsampled, so anything a test measures in fixture pixels means
nothing on its own. FixturePage.scale converts to source pixels at 300 dpi,
which is where the expected values in the tests are recorded and the only
coordinate system in which a tolerance can be compared against a measurement of
the real scan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
import pytest

from recto.frames import RECTO, VERSO, Frame, Provenance
from recto.pipeline import Pipeline, StageOutput
from recto.pngio import read_png
from recto.stages.blank import DropBlank
from recto.stages.border import CropBorder
from recto.stages.deskew import Deskew
from recto.stages.despeckle import Despeckle
from recto.stages.figures import MaskFigures
from recto.stages.furniture import StripFoot, StripHead
from recto.stages.split import SplitSpread

FIXTURE_DIR = Path(__file__).parent / "fixtures"

FIGURE_DIR = FIXTURE_DIR / "figures"

SOURCE_DPI = 300
"""The resolution the scan is at, and the one expected values are recorded in."""

_FILENAME = re.compile(r"^p(\d{4})@(\d+)dpi\.png$")


@dataclass(frozen=True)
class FixturePage:
    """One committed page, and what is needed to read it in context."""

    path: Path
    page_number: int
    dpi: int

    @property
    def scale(self) -> float:
        """Source pixels per fixture pixel."""
        return SOURCE_DPI / self.dpi

    def to_source(self, pixels: float) -> int:
        """Convert a fixture measurement to source pixels at 300 dpi."""
        return round(pixels * self.scale)

    def frame(self) -> Frame:
        """A fresh frame holding this page.

        Fresh every time: stages return new frames but the pipeline appends to
        the history list in place, so handing the same Frame to two tests would
        let one test see the other's history.
        """
        return Frame(
            image=read_png(self.path),
            provenance=Provenance(
                source=self.path,
                page_index=self.page_number - 1,
                dpi=self.dpi,
            ),
        )

    def __str__(self) -> str:
        return f"p{self.page_number:04d}"


def load_fixtures() -> list[FixturePage]:
    """Every fixture on disk, in page order.

    A module-level function rather than only a pytest fixture, because
    parametrising a test over the pages needs them at collection time.
    """
    found = []
    for path in sorted(FIXTURE_DIR.glob("*.png")):
        match = _FILENAME.match(path.name)
        if match is None:
            raise ValueError(
                f"{path.name} is not a fixture name. Expected p0009@100dpi.png, "
                "which is what tests/make_fixtures.py writes."
            )
        found.append(
            FixturePage(path=path, page_number=int(match[1]), dpi=int(match[2]))
        )
    return found


@pytest.fixture(scope="session")
def fixture_pages() -> list[FixturePage]:
    """Every fixture on disk, for tests that want the whole set at once."""
    pages = load_fixtures()
    if not pages:
        pytest.skip(
            "no fixtures under tests/fixtures. "
            "Run: python tests/make_fixtures.py <path to the scan>"
        )
    return pages


@lru_cache(maxsize=None)
def cleaned(page: FixturePage) -> tuple[Frame, int]:
    """The spread after crop and despeckle, and where the crop landed.

    Computed once per session, because most tests start here and redoing it for
    every parametrised case is most of what makes a suite slow. The offset is
    the crop's left edge, which is what turns a column in the cleaned image
    back into a column of the page. Callers must treat the frame as read only:
    stages return new frames rather than changing their input, so calling apply
    on it is safe, but running it through a Pipeline is not, because the
    pipeline appends to each frame's history in place.
    """
    cropped = CropBorder().apply(page.frame())
    offset = cropped.findings[0].shape.x
    return Despeckle().apply(cropped.frames[0]).frames[0], offset


@lru_cache(maxsize=None)
def pages_of(page: FixturePage) -> dict[str, Frame]:
    """The pages a fixture spread splits into, keyed by side, computed once.

    What the deskew stage receives: split, and with a blank page dropped.
    Read only, for the same reason as cleaned.
    """
    spread, _ = cleaned(page)
    after_split = Pipeline([SplitSpread(), DropBlank()])
    return {f.provenance.side: f for f in after_split.run(spread)}


@lru_cache(maxsize=None)
def masked_of(page: FixturePage) -> dict[str, Frame]:
    """Get the pages of a fixture spread as strip-head receives them.

    Each page is deskewed and its figures are masked. The result is computed
    once for each session. Read only, for the same reason as cleaned.

    Args:
        page: A fixture spread.

    Returns:
        The masked pages, keyed by side.
    """
    return {
        side: MaskFigures().apply(Deskew().apply(frame).frames[0]).frames[0]
        for side, frame in pages_of(page).items()
    }


def spread(number: int) -> FixturePage:
    """Find the fixture spread for a page number.

    Args:
        number: The one-based page number of the spread.

    Returns:
        The fixture spread.

    Raises:
        LookupError: If no fixture has that page number.
    """
    for page in load_fixtures():
        if page.page_number == number:
            return page
    raise LookupError(f"no fixture for page {number}")


@lru_cache(maxsize=None)
def stripped_head(page: int, side: str) -> tuple[Frame, StageOutput]:
    """Run strip-head on one 100 dpi page, once for each session.

    Args:
        page: Page number of the spread.
        side: VERSO or RECTO.

    Returns:
        The page as strip-head received it, and what the stage gave back.
    """
    frame = masked_of(spread(page))[side]
    return frame, StripHead().apply(frame)


@dataclass(frozen=True)
class FigureCrop:
    """A 300 dpi crop of a straightened page, as the figure stage receives it."""

    name: str
    path: Path

    def frame(self) -> Frame:
        return Frame(
            image=read_png(self.path),
            provenance=Provenance(source=self.path, page_index=0, dpi=SOURCE_DPI),
        )

    def __str__(self) -> str:
        return self.name


def load_figure_crops() -> list[FigureCrop]:
    """Every figure crop on disk, in name order."""
    return [
        FigureCrop(name=path.stem, path=path)
        for path in sorted(FIGURE_DIR.glob("*.png"))
    ]


FOOT_DIR = FIXTURE_DIR / "foot"

COLUMN_DIR = FIXTURE_DIR / "columns"

_FOOT_NAME = re.compile(r"^(p\d{4}-(?:verso|recto))@(\d+)\.png$")


@dataclass(frozen=True)
class FootCrop:
    """A 300 dpi crop of the bottom of a page, as strip-foot receives it."""

    label: str
    path: Path
    top: int
    """Row of the page where the crop starts. Add it to go back to page rows."""

    def frame(self) -> Frame:
        """Make a fresh frame that holds the crop.

        Returns:
            A new frame at 300 dpi, so that no test sees the history of another.
        """
        return Frame(
            image=read_png(self.path),
            provenance=Provenance(source=self.path, page_index=0, dpi=SOURCE_DPI),
        )

    def __str__(self) -> str:
        return self.label


def load_foot_crops() -> list[FootCrop]:
    """Find every foot crop on disk, in label order.

    Returns:
        One FootCrop for each file in tests/fixtures/foot.

    Raises:
        ValueError: If a file name does not tell the page and the first row.
    """
    found = []
    for path in sorted(FOOT_DIR.glob("*.png")):
        match = _FOOT_NAME.match(path.name)
        if match is None:
            raise ValueError(
                f"{path.name} is not a foot crop name. Expected "
                "p0012-verso@3460.png, which is what tests/make_fixtures.py writes."
            )
        found.append(FootCrop(label=match[1], path=path, top=int(match[2])))
    return found


@lru_cache(maxsize=None)
def stripped_foot(crop: FootCrop) -> tuple[Frame, StageOutput]:
    """Run strip-foot on one 300 dpi crop, once for each session.

    Args:
        crop: The crop.

    Returns:
        The crop as strip-foot received it, and what the stage gave back.
    """
    frame = crop.frame()
    return frame, StripFoot().apply(frame)


def column_page() -> Frame:
    """Load the column page, as split-columns receives it.

    Returns:
        A fresh frame of p41 recto at 300 dpi, head and foot already whited.

    Raises:
        FileNotFoundError: If the fixture is missing.
    """
    path = COLUMN_DIR / "p0041-recto.png"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing. Run: python tests/make_fixtures.py <path to the scan>"
        )
    return Frame(
        image=read_png(path),
        provenance=Provenance(source=path, page_index=40, side=RECTO),
    )


def ink(image: np.ndarray) -> np.ndarray:
    """The same test every stage uses."""
    return image < 200


@dataclass(frozen=True)
class Letters:
    """The pieces of type on an image, for tests that check where ink goes."""

    labels: np.ndarray
    """Component label of each pixel. Label 0 is paper."""

    stats: np.ndarray
    """One row per label: x, y, width, height, area, as OpenCV gives them."""

    kept: np.ndarray
    """Labels of the components that are type, in label order."""

    def crossing(self, row: int) -> np.ndarray:
        """Find the type that crosses one row.

        Args:
            row: A row of the image.

        Returns:
            The labels of the components whose rows include row.
        """
        top = self.stats[self.kept, 1]
        bottom = top + self.stats[self.kept, 3]
        return self.kept[(top <= row) & (row < bottom)]


def letters(image: np.ndarray, dpi: int, area: int = 50) -> Letters:
    """Find the type on an image with a rule that is not the stages' own.

    The stages use bands.letter_ink. A test that used it as well would agree
    with the stage by construction. This rule keeps every component of at least
    area px at 300 dpi. It drops strokes taller than 45 px and three times
    taller than wide, such as pieces of the column rule. Commas and full stops
    are mostly smaller than 50 px and are not counted.

    Args:
        image: A greyscale page or crop.
        dpi: Resolution of the image.
        area: Smallest component kept, in px at 300 dpi.

    Returns:
        The components and which of them are type.
    """
    scale = dpi / SOURCE_DPI
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        ink(image).astype(np.uint8), connectivity=8
    )
    width, height = stats[:, cv2.CC_STAT_WIDTH], stats[:, cv2.CC_STAT_HEIGHT]
    stroke = (height > 3 * width) & (height > 45 * scale)
    big = stats[:, cv2.CC_STAT_AREA] >= max(1, round(area * scale**2))
    kept = np.flatnonzero(big & ~stroke)
    return Letters(labels=labels, stats=stats, kept=kept[kept > 0])


HEAD_ROWS = {
    (10, VERSO): (393, 414),
    (13, RECTO): (352, 386),
    (13, VERSO): (369, 402),
    (24, RECTO): (429, 455),
    (24, VERSO): (378, 412),
    (43, RECTO): (376, 401),
    (43, VERSO): (341, 375),
    (56, RECTO): (380, 405),
    (56, VERSO): (324, 363),
    (60, RECTO): (426, 442),
    (60, VERSO): (380, 405),
    (74, RECTO): (397, 428),
    (74, VERSO): (362, 396),
    (76, RECTO): (420, 446),
    (76, VERSO): (358, 391),
}
"""For each body page of the fixtures, two rows in source px at 300 dpi: the
lowest row of the running head's descenders, and the highest row of the first
body line's letters. Read by eye on the 300 dpi page with a ruler, and checked
against a list of the components in the gap. Specks, the column rule, a pen
stroke on p13 verso and a flourish on p43 verso are not counted as either.

The tests use two rows derived from these, which are less sensitive to how
exactly they were read: HEAD_MIDDLE above the bottom, inside the head's type,
and LINE_MIDDLE under the top, inside the first line's letters."""

HEAD_MIDDLE = 45
"""A head letter descends about 25 px under its baseline, and its x-height is
about 40 px. Thus this many px above the head's bottom is inside the head's
letters. On the 15 pages it crosses 12 to 34 of them at 100 dpi."""

LINE_MIDDLE = 17
"""Ascenders rise about 10 px over the x-height of a 24 px body line. Thus
this many px under the first line's top is inside its letters. On the 15 pages
it crosses 11 to 45 of them at 100 dpi."""

FOOT_ROW = {
    "p0012-verso": (3764, 3788),
    "p0025-recto": (3769, 3790),
    "p0047-verso": (3737, 3758),
    "p0049-recto": (3711, 3736),
    "p0051-recto": (3699, 3721),
    "p0054-recto": (3697, 3744),
    "p0059-verso": (3718, 3740),
    "p0066-verso": (3724, 3746),
    "p0071-verso": (3746, 3770),
    "p0076-recto": (3789, 3811),
}
"""Top and bottom row of the foot row in the right half, page rows at 300 dpi.
Labelled by eye in commit 13."""
