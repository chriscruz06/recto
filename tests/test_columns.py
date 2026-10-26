"""Regression cover for the column split.

Three oracles, none of them the stage under test.

    The kind of page, seen by eye. Body pages are two columns. The preface on
    p1 verso, the title page, the privilege and the prologue opening on p4
    recto are one. The catalogue on p1 recto and the opening on p11 recto have
    a title across both columns. COLUMNS gives the frames each must make, and
    on p11 recto the title must end in the first frame: the last title line
    ends at row 1965 and the first column line starts at 2085, read by eye.

    The letters. On a body page the cut must divide no letter. Each letter of
    the page must keep its ink in one column frame, to WHOLE. This runs at
    300 dpi, on p41 recto and on the fourteen foot crops. Thin upright pieces
    are left out: they are the column rule, which the stage removes.

    A known shear. Shear p41 recto by a known slope, and the slope of the cut
    must change by that slope. The truth is the shear that this file applied,
    as in the applied rotation test of test_deskew. p41 recto is the page
    where every shear from -0.03 to +0.03 comes back exact to the step.

The frame counts run on the 100 dpi spreads, where every count is the same as
at 300 dpi. The geometry does not hold at 100 dpi: the slant of the cut on p11
recto is +10 px for each 1000 rows there and +30 at 300 dpi, and on p1 recto
the title block ends at 1089, 36 px into the last title line. Thus p1 recto is
tested for its frame count only.

Each constant was moved one way and the other, with these files, test_bands
and test_furniture run together. A test fails at: REACH 15 and 600, CLEAR 14,
SLANT 0.02, SLANT_STEP 0.001 and 0.004, SPLIT_MAX 0.15 and 0.45, TITLE_FIRST
1 and TITLE_CLEAN 1. No test fails at REACH 50 to 300, CLEAR 1 to 8, SLANT
0.06, TITLE_FIRST 8 or TITLE_CLEAN 4 to 30. TITLE_TALL from 15 to
100 has no test that fails. The stage docstring found that CLEAR at 4 and the
need for TITLE_TALL show on pages of parts 3 and 4, and the fixtures are all
from part 1.

Commit 17a adds UPRIGHT and WIDEST in stages/whole.py. A test fails at UPRIGHT
1.2 and WIDEST 20, and none at UPRIGHT 4 or 100 or WIDEST 60 to 1000. Here the
oracle leaves the rule pieces out, and no fused piece near the gap is wide.
The stage docstring measures both on the four parts.
"""

from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np
import pytest

from conftest import (
    HEAD_ROWS,
    SOURCE_DPI,
    column_page,
    letters,
    load_fixtures,
    load_foot_crops,
    masked_of,
    spread,
    stripped_foot,
    stripped_head,
)
from recto.frames import RECTO, VERSO, Frame, Line
from recto.pipeline import StageOutput
from recto.stages.columns import SplitColumns
from recto.stages.furniture import StripFoot

COLUMNS = {
    (1, VERSO): 1,
    (1, RECTO): 3,
    (2, RECTO): 1,
    (4, VERSO): 1,
    (4, RECTO): 1,
    (11, RECTO): 3,
    **{page: 2 for page in HEAD_ROWS},
}
"""Page number and side: frames the split must make. Every page frame of the
fixtures is here."""

TITLE = (1965, 2085)
"""p11 recto, source px: the last row of the title, and the first row of the
columns under it. Read by eye on the 300 dpi page."""

SHEARS = [-0.03, -0.01, 0.01, 0.03]
"""Px across for each px down. All stay inside the stage's SLANT of 0.04, as
p41 recto slants +0.004. Shears of -0.02 and +0.02 also come back exact, and
are left out to keep the suite fast."""

LETTER = 90
"""Px. The smallest component counted as a letter here. Commit 05 measured
that letters are 90 px and up. Under that are punctuation, speckle and pieces
of the column rule, and the stage whites the rule on purpose."""

SLOPE_TOLERANCE = 0.002
"""Px across for each px down, the search step of commit 16. Measured error on
p41 recto: at most 0.0002, because the cut is drawn between whole pixels. A
search step of 0.003 or 0.004 fails."""

UPRIGHT = 2
"""A piece this many times taller than wide is a piece of the column rule. The
three such pieces that the split cuts on these pages were looked at, and all
three are the rule."""

WHOLE = 0.99
"""Share of its ink that each letter must keep in one column frame. Measured
worst is 0.994, on p51 recto, where a letter touches the top edge of the crop.
Before commit 17a it was 0.962: the gap took 1 to 3 px columns off a letter at
the edge of a column, on 7 of the 15 pages."""


def page_id(case: tuple[int, str]) -> str:
    """Name a page for the test report.

    Args:
        case: Page number and side.

    Returns:
        A name such as p0013-recto.
    """
    return f"p{case[0]:04d}-{case[1]}"


@lru_cache(maxsize=None)
def split_page(page: int, side: str) -> StageOutput:
    """Run head, foot and column stages on one 100 dpi page, once for each session.

    Args:
        page: Page number of the spread.
        side: VERSO or RECTO.

    Returns:
        What split-columns gave back.
    """
    _, head = stripped_head(page, side)
    foot = StripFoot().apply(head.frames[0])
    return SplitColumns().apply(foot.frames[0])


def test_every_page_has_a_count() -> None:
    """Check that no fixture page is silently untested."""
    sides = {
        (page.page_number, side)
        for page in load_fixtures()
        for side in masked_of(page)
    }
    assert sides == set(COLUMNS)


@pytest.mark.parametrize("case", list(COLUMNS), ids=page_id)
def test_frame_count(case: tuple[int, str]) -> None:
    """Check that a page makes as many frames as it has text blocks.

    Args:
        case: Page number and side.
    """
    output = split_page(*case)
    labels = [frame.provenance.label for frame in output.frames]
    expected = [f"p{case[0]:04d}-{case[1]}-c{i + 1}" for i in range(COLUMNS[case])]
    assert labels == expected, f"{case}: {output.summary}"


def test_title_block_holds_the_whole_title() -> None:
    """Check that the title of p11 recto ends in the first frame."""
    title = split_page(11, RECTO).frames[0]
    end = title.height * spread(11).scale
    first, last = TITLE
    assert first <= end <= last, f"title frame ends at {end:.0f} source px"


@lru_cache(maxsize=None)
def page41() -> Frame:
    """Load p41 recto once for each session. Read only, as conftest.cleaned.

    Returns:
        The column page as split-columns receives it.
    """
    return column_page()


@lru_cache(maxsize=None)
def body_pages() -> list[tuple[str, Frame]]:
    """Get the 300 dpi body pages as split-columns receives them.

    Returns:
        Name and frame of p41 recto and of each foot crop after strip-foot.
    """
    pages = [("p0041-recto", page41())]
    for crop in load_foot_crops():
        pages.append((crop.label, stripped_foot(crop)[1].frames[0]))
    return pages


def body_names() -> list[str]:
    """List the names of the 300 dpi body pages.

    Returns:
        The name of p41 recto and of each foot crop.
    """
    return ["p0041-recto", *(crop.label for crop in load_foot_crops())]


@pytest.mark.parametrize("name", body_names())
def test_every_letter_lands_whole_in_one_column(name: str) -> None:
    """Check that the cut divides no letter and drops no letter.

    Args:
        name: The page.
    """
    frame = dict(body_pages())[name]
    output = SplitColumns().apply(frame)
    assert len(output.frames) == 2, f"{name}: {output.summary}"
    left, right = (f.image < 200 for f in output.frames)

    found = letters(frame.image, SOURCE_DPI, area=LETTER)
    offset = frame.width - right.shape[1]
    count = len(found.stats)
    in_left = np.bincount(
        found.labels[:, : left.shape[1]].ravel(), weights=left.ravel(), minlength=count
    )
    in_right = np.bincount(
        found.labels[:, offset:].ravel(), weights=right.ravel(), minlength=count
    )
    width, height = found.stats[found.kept, 2], found.stats[found.kept, 3]
    letter = found.kept[height < UPRIGHT * width]
    share = np.maximum(in_left[letter], in_right[letter]) / found.stats[letter, 4]
    worst = int(np.argmin(share))
    x, y = found.stats[letter[worst], :2]
    assert share[worst] >= WHOLE, (
        f"{name}: letter at {x},{y} keeps {share[worst]:.0%} of its ink in one column"
    )


def shear(image: np.ndarray, slope: float) -> np.ndarray:
    """Shear an image so that each row moves across by slope times its row.

    The rows above the middle move the other way from the rows below it, and
    the canvas grows so that nothing is cut off.

    Args:
        image: A greyscale page.
        slope: Px across for each px down.

    Returns:
        The sheared page, on a white canvas.
    """
    height, width = image.shape
    pad = int(np.ceil(abs(slope) * height / 2)) + 2
    turn = np.float32([[1, slope, pad - slope * height / 2], [0, 1, 0]])
    return cv2.warpAffine(
        image,
        turn,
        (width + 2 * pad, height),
        flags=cv2.INTER_NEAREST,
        borderValue=255,
    )


def cut_slope(image: np.ndarray) -> float:
    """Find the slope of the cut that split-columns makes.

    Args:
        image: A page as split-columns receives it, at 300 dpi.

    Returns:
        Px across for each px down.

    Raises:
        AssertionError: If the page does not split in two.
    """
    frame = Frame(image=image, provenance=page41().provenance)
    output = SplitColumns().apply(frame)
    lines = [f.shape for f in output.findings if isinstance(f.shape, Line)]
    assert lines, output.summary
    line = lines[0]
    return (line.x2 - line.x1) / (line.y2 - line.y1)


@lru_cache(maxsize=None)
def unsheared_slope() -> float:
    """Find the slope of the cut on p41 recto, once for each session.

    Returns:
        Px across for each px down.
    """
    return cut_slope(page41().image)


@pytest.mark.parametrize("applied", SHEARS)
def test_recovers_an_applied_shear(applied: float) -> None:
    """Check that the slope of the cut follows a shear of the page.

    Args:
        applied: The shear, px across for each px down.
    """
    before = unsheared_slope()
    after = cut_slope(shear(page41().image, applied))
    assert abs(after - before - applied) <= SLOPE_TOLERANCE, (
        f"shear {applied:+}: slope {after:+.4f}, expected {before + applied:+.4f}"
    )
