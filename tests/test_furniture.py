"""Regression cover for stripping the running head and the foot row.

The oracles are rows read by eye, and the assertions are about ink, not about
where the stage puts its cut. A test that compared the cut with a stored row
would only repeat what the stage did on the day it was written.

The head (100 dpi spreads). For each body page, conftest.HEAD_ROWS gives the
head's bottom and the first line's top. Every letter that crosses a row inside
the head must be above the cut, and every letter that crosses a row inside the
first line must be under it. A component that crosses both rows is neither,
such as the pen stroke from the head into the first line on p13 verso. The
front matter pages without a head must come back unchanged.

The foot (300 dpi crops). For the ten foot rows labelled by eye in commit 13,
the letters of the foot row must be under the cut, and the letters above it
over the cut. That is not fully true now, so the bound is in px, FOOT_SLACK,
and it records what the stage does:

    On 7 of the 10 pages no row separates the two. The descenders of the last
    line and the tops of the foot row share 4 to 10 rows. On p12 verso the p
    of ipso reaches row 3757 and the i of the catchword starts at 3749.

    On the other 3, p47 verso, p59 verso and p71 verso, 6 to 12 white rows
    separate them, but the cut still takes 1 to 7 px off a descender. The cut
    is halfway between the bands, and a band stops above its descenders.

Over the ten, the cut leaves at most 6 px of a foot row letter above it and
takes at most 7 px off a descender. A cut that follows the letters, and not a
row, would remove both.

Bounds are in source px at 300 dpi. At 300 dpi the head cut leaves no head
letter under it, and it reaches at most 4 px into a first line ascender, on p60
verso. At 100 dpi a head letter hangs at most 6 px under the cut, and the cut
reaches at most 6 px into a first line letter, on 13 of the 15 pages. LOOSER
names the other two.

Each constant was moved one way and the other, with these files, test_bands
and test_columns run together. A test fails at: HEAD_MIN 30, LINE_MAX 25,
GAP_MAX 30, PIECE 5, COLUMN_WIDE 950, LINE_DEPTH 20 and 50, and ABOVE 40. No
test fails at HEAD_MIN 50, LINE_MAX 30 to 60, GAP_MAX 40 to 150, PIECE 15 to
80, COLUMN_WIDE 100 to 800 or ABOVE 5. LINE_MIN from 15 to 23, START from 50
to 700 and START_INK from 0.005 to 0.3 have no test that fails. The stage
docstring found that each of those changes at most four of 555 frames, and
the fixtures hold none of them.
"""

from __future__ import annotations

import numpy as np
import pytest

from conftest import (
    FOOT_ROW,
    HEAD_MIDDLE,
    HEAD_ROWS,
    LINE_MIDDLE,
    SOURCE_DPI,
    FootCrop,
    letters,
    load_foot_crops,
    spread,
    stripped_foot,
    stripped_head,
)
from recto.frames import RECTO, VERSO
from recto.pipeline import StageOutput

SLACK = 6
"""Source px, two fixture px. How far a head letter may hang under the cut,
and how far the cut may reach into a first line letter."""

LOOSER = {(43, VERSO): 18, (76, RECTO): 18}
"""Pages where the 100 dpi head cut leaves 15 source px of the head under it.
On p43 verso the right half bands the head without its descenders, and the
cut is 29 px higher than at 300 dpi. On p76 recto a speck fuses to a head
letter at 100 dpi and reaches under the cut. At 300 dpi both are clear."""

NO_HEAD = [(1, VERSO), (1, RECTO), (2, RECTO), (4, VERSO), (4, RECTO), (11, RECTO)]
"""Pages of the fixtures that carry no running head, seen by eye: the preface
and the catalogue on page 1, the title page, the privilege, the prologue
opening on p4 recto, and the commentary opening on p11 recto."""

ABOVE_FOOT = 20
"""Px. A letter that starts this far over the foot row is in a line above it.
The foot row sits 0 to 71 px under the line above, 24 at the median."""

TALL = (25, 60)
"""Px. Only letters with an ascender or a descender can reach the cut, and they
are this tall. Letters of x-height only, specks, and the speckled strip at the
outer edge of the leaf are left out."""

FOOT_SLACK = 8
"""Px. Measured: the cut leaves at most 6 px of a foot row letter above it, and
takes at most 7 px off a descender of the last line. See the module docstring."""


def page_id(case: tuple[int, str]) -> str:
    """Name a page for the test report.

    Args:
        case: Page number and side.

    Returns:
        A name such as p0013-recto.
    """
    return f"p{case[0]:04d}-{case[1]}"


def head_cut(output: StageOutput) -> int:
    """Read the cut row from the finding that strip-head reports.

    Args:
        output: What strip-head gave back.

    Returns:
        The first row under the cut.

    Raises:
        AssertionError: If the stage found no head.
    """
    found = [f for f in output.findings if f.kind == "running-head"]
    assert found, f"no running head found: {output.summary}"
    return found[0].shape.height


@pytest.mark.parametrize("case", list(HEAD_ROWS), ids=page_id)
def test_head_goes_and_first_line_stays(case: tuple[int, str]) -> None:
    """Check that the cut falls between the head and the first body line.

    Args:
        case: Page number and side.
    """
    page, side = case
    frame, output = stripped_head(page, side)
    scale = spread(page).scale
    cut = head_cut(output)
    found = letters(frame.image, frame.provenance.dpi)
    head_bottom, first_top = HEAD_ROWS[case]
    head = set(found.crossing(round((head_bottom - HEAD_MIDDLE) / scale)))
    line = set(found.crossing(round((first_top + LINE_MIDDLE) / scale)))
    assert head and line, f"{case}: no letters on the measured rows"

    stats = found.stats
    hangs = max((stats[i, 1] + stats[i, 3] - cut) * scale for i in head - line)
    reaches = max((cut - stats[i, 1]) * scale for i in line - head)
    limit = LOOSER.get(case, SLACK)
    assert hangs <= limit, f"{case}: a head letter hangs {hangs:.0f} px under the cut"
    assert reaches <= SLACK, (
        f"{case}: the cut reaches {reaches:.0f} px into the first line"
    )


@pytest.mark.parametrize("case", list(HEAD_ROWS), ids=page_id)
def test_head_rows_are_white(case: tuple[int, str]) -> None:
    """Check that the stage whites every row above its cut and changes nothing under it.

    Args:
        case: Page number and side.
    """
    frame, output = stripped_head(*case)
    cut = head_cut(output)
    after = output.frames[0].image
    assert (after[:cut] == 255).all()
    assert np.array_equal(after[cut:], frame.image[cut:])


@pytest.mark.parametrize("case", NO_HEAD, ids=page_id)
def test_front_matter_keeps_its_top(case: tuple[int, str]) -> None:
    """Check that a page with no running head comes back unchanged.

    Args:
        case: Page number and side.
    """
    frame, output = stripped_head(*case)
    assert output.frames == [frame], f"{case}: {output.summary}"


def foot_cut(output: StageOutput) -> int:
    """Read the cut row from the finding that strip-foot reports.

    Args:
        output: What strip-foot gave back.

    Returns:
        The first row that the stage whites.

    Raises:
        AssertionError: If the stage found no foot row.
    """
    found = [f for f in output.findings if f.kind == "catchword"]
    assert found, f"no foot row found: {output.summary}"
    return found[0].shape.y


def labelled_crops() -> list[FootCrop]:
    """List the foot crops that carry a labelled foot row.

    Returns:
        The crops named in conftest.FOOT_ROW.
    """
    return [crop for crop in load_foot_crops() if crop.label in FOOT_ROW]


@pytest.mark.parametrize("crop", labelled_crops(), ids=str)
def test_foot_row_goes(crop: FootCrop) -> None:
    """Check that the foot row is under the cut, apart from the tips of tall letters.

    Args:
        crop: A crop with a labelled foot row.
    """
    frame, output = stripped_foot(crop)
    cut = foot_cut(output)
    top, bottom = (row - crop.top for row in FOOT_ROW[crop.label])
    found = letters(frame.image, SOURCE_DPI)
    centre = found.stats[found.kept, 1] + found.stats[found.kept, 3] / 2
    in_row = found.kept[(centre >= top) & (centre < bottom)]
    assert in_row.size, f"{crop.label}: no letters in the labelled foot row"

    over = cut - int(found.stats[in_row, 1].min())
    assert over <= FOOT_SLACK, (
        f"{crop.label}: a foot row letter starts {over} px over the cut"
    )
    assert (output.frames[0].image[cut:] == 255).all()


@pytest.mark.parametrize("crop", labelled_crops(), ids=str)
def test_last_line_loses_at_most_a_tip(crop: FootCrop) -> None:
    """Check that no letter above the foot row reaches far under the cut.

    Args:
        crop: A crop with a labelled foot row.
    """
    frame, output = stripped_foot(crop)
    cut = foot_cut(output)
    top = FOOT_ROW[crop.label][0] - crop.top
    found = letters(frame.image, SOURCE_DPI)
    y, height = found.stats[found.kept, 1], found.stats[found.kept, 3]
    tall = (height >= TALL[0]) & (height <= TALL[1])
    above = found.kept[(y < top - ABOVE_FOOT) & tall]

    under = int((found.stats[above, 1] + found.stats[above, 3]).max()) - cut
    assert under <= FOOT_SLACK, (
        f"{crop.label}: a letter above the foot row reaches {under} px under the cut"
    )
