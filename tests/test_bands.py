"""Regression cover for line banding.

Three oracles, none of them the stage under test.

    The printed line pitch. The book sets its body lines 48 to 50 px apart at
    300 dpi. This is a property of the type, measured in commit 13. Thus on a
    body half the median distance between bands must be the pitch, and no two
    bands under the head can be closer than three quarters of it: a body line
    split in two gives two bands about half a pitch apart.

    The head and the first body line, read by eye (conftest.HEAD_ROWS). In at
    least one half of the page, no band may hold both. Most of the rules that
    put large type together act on the head, and a wrong value either merges it
    into the first line or breaks it.

    The foot rows and the noise labelled by eye at 300 dpi in commit 13. Each
    foot row must be a band, and nothing may be banded under the last real row
    of the four noise halves.

The pitch and head tests run on the 100 dpi spreads. There, the band count of
each of the 30 body halves is within 2 of the count at 300 dpi, and within 1 on
29 of them. The foot and noise tests run on 300 dpi crops, because at 100 dpi
the foot row merges with the last line on two of the 21 page frames.

Each constant in Tuning was moved one way and the other, and these files,
test_furniture and test_columns run together (all three stages call
band_lines). A test fails at: letter_area 45 and 135, stroke_aspect 8, pitch
36, smooth 9, peak_reach 12 and 20, rise 0.4 and 0.6, merge_gap 6 and 18,
sliver 10 and 21, fold_reach 15 and 45, piece_height 0.2 and 0.6, piece_gap
0.15 and 0.45, min_run 20 and 40, bridge 1, block_fraction 0.125 and 0.4, and
block_gap 75 and 300. No test fails at stroke_aspect 2, pitch 60, smooth 2 or
bridge 20. full_run is the weak one: no test fails from 30 to 300, and the
first failure is at 600.
"""

from __future__ import annotations

from functools import lru_cache
from statistics import median

import pytest

from conftest import (
    FOOT_ROW,
    HEAD_MIDDLE,
    HEAD_ROWS,
    LINE_MIDDLE,
    SOURCE_DPI,
    FootCrop,
    load_foot_crops,
    masked_of,
    spread,
)
from recto.stages.bands import Band, band_lines

PITCH = (45, 53)
"""Source px. The median band spacing of a body half must lie in this range.
Measured over the 30 body halves at 100 dpi: 48 to 49.5."""

SPLIT = 36
"""Source px, three quarters of the pitch. Measured closest pair of bands
under the head, over the 30 body halves at 100 dpi: 42."""

NOISE = {
    "p0019-recto": (1, 3849),
    "p0034-verso": (0, 3719),
    "p0069-recto": (1, 3771),
    "p0071-recto": (1, 3780),
}
"""Half (0 left, 1 right) and the bottom row of its last real row of type, page
rows at 300 dpi. Under each, specks and a stray stroke were labelled as noise in
commit 13. These four are the noise that a run floor of 20 or 22 px bands
again. The rows were checked by eye on the page."""

NOISE_CLEAR = 20
"""Px. A band that starts this far under the last real row is noise. The
noise in these halves starts 41 to 89 px under it."""


def body_halves() -> list[tuple[int, str, int]]:
    """List the body page halves of the 100 dpi fixtures.

    Returns:
        Page number, side and half for each half of each page in HEAD_ROWS.
    """
    return [(page, side, half) for page, side in HEAD_ROWS for half in (0, 1)]


def half_id(case: tuple[int, str, int]) -> str:
    """Name a body half for the test report.

    Args:
        case: Page number, side and half.

    Returns:
        A name such as p0013-recto-1.
    """
    return f"p{case[0]:04d}-{case[1]}-{case[2]}"


def page_id(case: tuple[int, str]) -> str:
    """Name a page for the test report.

    Args:
        case: Page number and side.

    Returns:
        A name such as p0013-recto.
    """
    return f"p{case[0]:04d}-{case[1]}"


@lru_cache(maxsize=None)
def bands_of(page: int, side: str) -> tuple[list[Band], list[Band]]:
    """Band one 100 dpi page, once for each session.

    Args:
        page: Page number of the spread.
        side: VERSO or RECTO.

    Returns:
        The bands of the left and the right half.
    """
    frame = masked_of(spread(page))[side]
    return band_lines(frame.image, frame.provenance.dpi)


@lru_cache(maxsize=None)
def crop_bands(crop: FootCrop) -> tuple[list[Band], list[Band]]:
    """Band one 300 dpi foot crop, once for each session.

    Args:
        crop: The crop.

    Returns:
        The bands of the left and the right half, in crop rows.
    """
    return band_lines(crop.frame().image, SOURCE_DPI)


def source(rows: float, page: int) -> float:
    """Convert fixture rows to source px.

    Args:
        rows: A length or a row at the fixture's resolution.
        page: Page number of the spread.

    Returns:
        The same length or row at 300 dpi.
    """
    return rows * spread(page).scale


def centres_under_head(page: int, side: str, half: int) -> list[float]:
    """Find the centres of the bands under the head, in source px.

    Args:
        page: Page number of the spread.
        side: VERSO or RECTO.
        half: 0 for the left half, 1 for the right.

    Returns:
        The centre row of each band whose centre is under the head's bottom.
    """
    head_bottom, _ = HEAD_ROWS[(page, side)]
    centres = [source((b.top + b.bottom) / 2, page) for b in bands_of(page, side)[half]]
    return [c for c in centres if c > head_bottom]


@pytest.mark.parametrize("case", body_halves(), ids=half_id)
def test_line_spacing_is_the_pitch(case: tuple[int, str, int]) -> None:
    """Check that the bands of a body half sit one printed line apart.

    Args:
        case: Page number, side and half.
    """
    centres = centres_under_head(*case)
    spacing = median(b - a for a, b in zip(centres, centres[1:]))
    low, high = PITCH
    assert low <= spacing <= high, f"{case}: median spacing {spacing:.0f} source px"


@pytest.mark.parametrize("case", body_halves(), ids=half_id)
def test_no_body_line_is_split(case: tuple[int, str, int]) -> None:
    """Check that no two bands under the head are closer than a body line allows.

    Args:
        case: Page number, side and half.
    """
    centres = centres_under_head(*case)
    closest = min(b - a for a, b in zip(centres, centres[1:]))
    assert closest >= SPLIT, f"{case}: two bands {closest:.0f} source px apart"


@pytest.mark.parametrize("case", list(HEAD_ROWS), ids=page_id)
def test_head_and_first_line_are_apart(case: tuple[int, str]) -> None:
    """Check that one half of the page bands the head and the first line apart.

    One half only, because that is what strip-head needs. It takes the cut from
    the half that keeps them apart. The other half bands them together on 62 of
    555 page frames at 300 dpi, and here on p43 verso left and p76 recto right.

    Args:
        case: Page number and side.
    """
    page, side = case
    head_bottom, first_top = HEAD_ROWS[case]
    in_head = head_bottom - HEAD_MIDDLE
    in_line = first_top + LINE_MIDDLE

    def merges(half: list[Band]) -> bool:
        """Tell if one band of a half holds both measured rows.

        Args:
            half: The bands of one half.

        Returns:
            True if a band reaches from inside the head into the first line.
        """
        return any(
            source(b.top, page) <= in_head and source(b.bottom, page) > in_line
            for b in half
        )

    assert not all(merges(half) for half in bands_of(page, side)), (
        f"{case}: both halves band the head and the first line together"
    )


def foot_crops() -> list[FootCrop]:
    """List the foot crops that carry a labelled foot row.

    Returns:
        The crops named in FOOT_ROW.
    """
    return [crop for crop in load_foot_crops() if crop.label in FOOT_ROW]


def noise_crops() -> list[FootCrop]:
    """List the foot crops that carry labelled noise.

    Returns:
        The crops named in NOISE.
    """
    return [crop for crop in load_foot_crops() if crop.label in NOISE]


def test_every_label_has_a_crop() -> None:
    """Check that no label is silently untested because its crop is missing."""
    labels = {crop.label for crop in load_foot_crops()}
    assert set(FOOT_ROW) | set(NOISE) <= labels


@pytest.mark.parametrize("crop", foot_crops(), ids=str)
def test_foot_row_is_a_band(crop: FootCrop) -> None:
    """Check that the foot row is banded, so strip-foot can find it.

    Args:
        crop: A crop with a labelled foot row.
    """
    top, bottom = (row - crop.top for row in FOOT_ROW[crop.label])
    right = crop_bands(crop)[1]
    assert any(b.top < bottom and top < b.bottom for b in right), (
        f"{crop.label}: no band at rows {top + crop.top} to {bottom + crop.top}"
    )


@pytest.mark.parametrize("crop", noise_crops(), ids=str)
def test_noise_is_not_banded(crop: FootCrop) -> None:
    """Check that nothing is banded under the last real row of a noise half.

    Args:
        crop: A crop with labelled noise.
    """
    half, last = NOISE[crop.label]
    below = [
        (b.top + crop.top, b.bottom + crop.top)
        for b in crop_bands(crop)[half]
        if b.top + crop.top > last + NOISE_CLEAR
    ]
    assert not below, f"{crop.label}: noise banded at {below}"

