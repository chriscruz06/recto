"""Regression cover for stripping the running head and the foot row.

The oracles are rows read by eye, and the assertions are about ink, not about
where the stage puts its cut. A test that compared the cut with a stored row
would only repeat what the stage did on the day it was written.

The head (100 dpi spreads). For each body page, conftest.HEAD_ROWS gives the
head's bottom and the first line's top. Every letter that crosses a row inside
the head must lose all its ink, and every letter that crosses a row inside the
first line must keep all of it. A component that crosses both rows is neither,
such as the pen stroke from the head into the first line on p13 verso. The
front matter pages without a head must come back unchanged.

The foot (300 dpi crops). For the ten foot rows labelled by eye in commit 13,
every letter of the foot row must lose all its ink, and every letter above it
must keep all of it. On 7 of the 10 pages no row separates the two: the
descenders of the last line and the tops of the foot row share 4 to 10 rows.
Before commit 17a the cut left up to 6 px of a foot row letter and took up to
7 px off a descender. Now each letter that the cut crosses goes whole to one
side, and the tests ask for that.

Past each cut, nothing may stay but the parts of components that also reach
the kept side, and on the kept side nothing may go but such parts.

Each constant was moved one way and the other, with these files, test_bands
and test_columns run together. A test fails at: HEAD_MIN 30, LINE_MAX 25,
GAP_MAX 30, PIECE 5, COLUMN_WIDE 950, LINE_DEPTH 20 and 50, and ABOVE 40. No
test fails at HEAD_MIN 50, LINE_MAX 30 to 60, GAP_MAX 40 to 150, PIECE 15 to
80, COLUMN_WIDE 100 to 800 or ABOVE 5. LINE_MIN from 15 to 23, START from 50
to 700 and START_INK from 0.005 to 0.3 have no test that fails. The stage
docstring found that each of those changes at most four of 555 frames, and
the fixtures hold none of them.

Commit 17a adds TALLEST in stages/whole.py. A test fails at 30 and 40, and none
at 90 or 150: the fixtures hold no two lines fused into one piece. The stage
docstring measures that on the four parts.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from conftest import (
    FOOT_ROW,
    HEAD_MIDDLE,
    HEAD_ROWS,
    LINE_MIDDLE,
    SOURCE_DPI,
    FootCrop,
    Letters,
    ink,
    letters,
    load_foot_crops,
    spread,
    stripped_foot,
    stripped_head,
)
from recto.frames import RECTO, VERSO
from recto.pipeline import StageOutput

KEEP = 0.99
"""Share of its ink that a letter on the kept side of a cut must keep.
Measured: all of it, on every page here."""

LOOSER = {(43, VERSO): 0.2, (76, RECTO): 0.2}
"""Share of its ink that a head letter may keep on two pages at 100 dpi.
Measured 0.16 and 0.06; on the other 13 pages, none. On p43 verso the right
half bands the head without its descenders, and the cut is 29 px higher than
at 300 dpi. On p76 recto a speck fuses to a head letter at 100 dpi. At 300 dpi
both are clear."""

NO_HEAD = [(1, VERSO), (1, RECTO), (2, RECTO), (4, VERSO), (4, RECTO), (11, RECTO)]
"""Pages of the fixtures that carry no running head, seen by eye: the preface
and the catalogue on page 1, the title page, the privilege, the prologue
opening on p4 recto, and the commentary opening on p11 recto."""

ABOVE_FOOT = 20
"""Px. A letter that starts this far over the foot row is in a line above it.
The foot row sits 0 to 71 px under the line above, 24 at the median."""

TALLEST = 60
"""Px. A taller piece above the foot row is not a letter. On p76 recto a
stroke 135 px tall at the edge of the leaf reaches under the cut."""


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


def kept(found: Letters, image: np.ndarray, ids: np.ndarray) -> np.ndarray:
    """Find the share of its ink that each letter keeps in an image.

    Args:
        found: The letters of the image before the stage.
        image: The image after the stage.
        ids: Labels of the letters to check.

    Returns:
        For each label in ids, the share of its ink that is still ink.
    """
    left = np.bincount(
        found.labels.ravel(), weights=ink(image).ravel(), minlength=len(found.stats)
    )
    return left[ids] / found.stats[ids, cv2.CC_STAT_AREA]


def stray_ink(before: np.ndarray, after: np.ndarray, cut: int) -> tuple[int, int]:
    """Count the ink that a row cut changes outside the letters it crosses.

    Args:
        before: The image before the stage.
        after: The image after the stage.
        cut: The first row under the cut.

    Returns:
        Pixels of ink still above the cut, and pixels of ink gone under it,
        that belong to no component reaching both sides of the cut.
    """
    count, labels = cv2.connectedComponents(
        ink(before).astype(np.uint8), connectivity=8
    )
    both = np.zeros(count, dtype=bool)
    both[np.intersect1d(np.unique(labels[:cut]), np.unique(labels[cut:]))] = True
    both[0] = False
    lone = ~both[labels]
    changed = ink(before) & ~ink(after)
    return int((ink(after) & lone)[:cut].sum()), int((changed & lone)[cut:].sum())


@pytest.mark.parametrize("case", list(HEAD_ROWS), ids=page_id)
def test_head_goes_and_first_line_stays(case: tuple[int, str]) -> None:
    """Check that the head letters lose their ink and the first line keeps it.

    Args:
        case: Page number and side.
    """
    page, side = case
    frame, output = stripped_head(page, side)
    scale = spread(page).scale
    found = letters(frame.image, frame.provenance.dpi)
    head_bottom, first_top = HEAD_ROWS[case]
    head = set(found.crossing(round((head_bottom - HEAD_MIDDLE) / scale)))
    line = set(found.crossing(round((first_top + LINE_MIDDLE) / scale)))
    assert head and line, f"{case}: no letters on the measured rows"

    after = output.frames[0].image
    most = float(kept(found, after, np.array(sorted(head - line))).max())
    least = float(kept(found, after, np.array(sorted(line - head))).min())
    assert most <= LOOSER.get(case, 0.0), f"{case}: a head letter keeps {most:.0%}"
    assert least >= KEEP, f"{case}: a first line letter keeps {least:.0%}"


@pytest.mark.parametrize("case", list(HEAD_ROWS), ids=page_id)
def test_head_cut_moves_only_whole_letters(case: tuple[int, str]) -> None:
    """Check that the stage whites above its cut and keeps under it, but for letters.

    Args:
        case: Page number and side.
    """
    frame, output = stripped_head(*case)
    above, under = stray_ink(frame.image, output.frames[0].image, head_cut(output))
    assert (above, under) == (0, 0), (
        f"{case}: {above} px of ink stay above the cut, {under} px go under it"
    )


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
    """Check that every letter of the foot row loses all its ink.

    Args:
        crop: A crop with a labelled foot row.
    """
    frame, output = stripped_foot(crop)
    top, bottom = (row - crop.top for row in FOOT_ROW[crop.label])
    found = letters(frame.image, SOURCE_DPI)
    centre = found.stats[found.kept, 1] + found.stats[found.kept, 3] / 2
    in_row = found.kept[(centre >= top) & (centre < bottom)]
    assert in_row.size, f"{crop.label}: no letters in the labelled foot row"

    most = float(kept(found, output.frames[0].image, in_row).max())
    assert most == 0.0, f"{crop.label}: a foot row letter keeps {most:.0%}"


@pytest.mark.parametrize("crop", labelled_crops(), ids=str)
def test_lines_above_keep_their_ink(crop: FootCrop) -> None:
    """Check that every letter above the foot row keeps its ink.

    Args:
        crop: A crop with a labelled foot row.
    """
    frame, output = stripped_foot(crop)
    top = FOOT_ROW[crop.label][0] - crop.top
    found = letters(frame.image, SOURCE_DPI)
    y, height = found.stats[found.kept, 1], found.stats[found.kept, 3]
    above = found.kept[(y < top - ABOVE_FOOT) & (height <= TALLEST)]

    share = kept(found, output.frames[0].image, above)
    worst = int(np.argmin(share))
    assert share[worst] >= KEEP, (
        f"{crop.label}: letter at row {found.stats[above[worst], 1] + crop.top} "
        f"keeps {share[worst]:.0%} of its ink"
    )


@pytest.mark.parametrize("crop", labelled_crops(), ids=str)
def test_foot_cut_moves_only_whole_letters(crop: FootCrop) -> None:
    """Check that the stage whites under its cut and keeps above it, but for letters.

    Args:
        crop: A crop with a labelled foot row.
    """
    frame, output = stripped_foot(crop)
    cut = foot_cut(output)
    # stray_ink checks a cut that whites the rows above it. This cut whites the
    # rows under it, so the images go in upside down.
    flipped = stray_ink(
        frame.image[::-1], output.frames[0].image[::-1], frame.height - cut
    )
    assert flipped == (0, 0), (
        f"{crop.label}: {flipped[0]} px of ink stay under the cut, "
        f"{flipped[1]} px go above it"
    )
