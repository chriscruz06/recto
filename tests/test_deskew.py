"""Regression cover for deskew.

Two kinds of expected value, and they come from different places.

The angles in EXPECTED_ANGLE were measured on the 300 dpi render, and each was
checked by something that shares nothing with projection variance: rotate the
page by the angle, then correlate the row ink of a strip near its left edge
against one near its right. A straight page lines the two up at zero shift.
Eight of the nine left at most 0.11 degrees of tilt behind. The ninth is the
catalogue page, where that check cannot work because the two columns of the list
do not share baselines, so it was checked by eye at full size in commit 09.

The applied-rotation test needs no measurement at all. Rotate a page by a known
angle and the estimator has to find that angle again, on top of whatever tilt
the page already had. The truth is the rotation this file applied.

Tolerances were measured, not chosen. At fixture resolution the estimate lands
within 0.05 degrees of the full resolution one on every page here but the
catalogue page, which comes out 0.25 high because its variance peak is almost
flat. The fine step is 0.05, and two machines can land a step apart on a flat
peak: 1.80 here and 1.85 on another install, for the same page. So TOLERANCE
allows three steps, and the catalogue page is named with its own.
"""

from __future__ import annotations

from functools import lru_cache

import pytest

from conftest import FixturePage, load_fixtures, pages_of
from recto.frames import RECTO, VERSO
from recto.stages.deskew import Deskew, estimate_angle, rotate, score_mask

EXPECTED_ANGLE = {
    (1, RECTO): +1.80,
    (2, RECTO): +1.15,
    (11, RECTO): +0.50,
    (13, RECTO): -0.05,
    (24, RECTO): +0.85,
    (43, RECTO): -0.20,
    (74, VERSO): -0.45,
    (74, RECTO): +1.20,
    (76, RECTO): +1.10,
}
"""Degrees, measured at 300 dpi and checked independently. See the docstring.

Chosen to span the volume: the steepest page, the most negative, one already
straight, the title page, and the opening page with its woodcuts."""

TOLERANCE = 0.15
"""Degrees. Three fine steps. Measured worst at fixture resolution is 0.05."""

LOOSER = {(1, RECTO): 0.30}
"""The catalogue page's flat variance peak puts it 0.25 out at 100 dpi."""

APPLIED = [
    (13, RECTO, -1.5),
    (13, RECTO, +2.0),
    (43, VERSO, -1.5),
    (43, VERSO, +2.0),
    (74, VERSO, -1.5),
    (74, VERSO, +2.0),
]
"""Page, side, and a rotation to apply. Measured error across 18 such trials is
at most 0.10 degrees."""


def angle_of(image, dpi: int) -> float:
    return estimate_angle(score_mask(image, dpi))


@lru_cache(maxsize=None)
def page_angle(number: int, side: str) -> float:
    """The estimate for an unrotated fixture page, computed once per session."""
    frame = pages_of(fixture(number))[side]
    return angle_of(frame.image, frame.provenance.dpi)


def fixture(number: int) -> FixturePage:
    for page in load_fixtures():
        if page.page_number == number:
            return page
    pytest.skip(f"fixture for page {number} is missing")


def measured_cases():
    return [
        (page, side)
        for page in load_fixtures()
        for side in (VERSO, RECTO)
        if (page.page_number, side) in EXPECTED_ANGLE
    ]


@pytest.mark.parametrize("case", measured_cases(), ids=lambda c: f"{c[0]}-{c[1]}")
def test_angle_matches_measurement(case) -> None:
    page, side = case
    frame = pages_of(page)[side]
    found = page_angle(page.page_number, side)

    expected = EXPECTED_ANGLE[(page.page_number, side)]
    limit = LOOSER.get((page.page_number, side), TOLERANCE)
    assert abs(found - expected) <= limit, (
        f"{frame.provenance.label}: {found:+.2f} deg, expected {expected:+.2f} "
        f"within {limit}"
    )


@pytest.mark.parametrize("case", APPLIED, ids=lambda c: f"p{c[0]:04d}-{c[1]}{c[2]:+}")
def test_recovers_an_applied_rotation(case) -> None:
    number, side, applied = case
    frame = pages_of(fixture(number))[side]
    dpi = frame.provenance.dpi

    before = page_angle(number, side)
    after = angle_of(rotate(frame.image, applied), dpi)

    # Rotating the page by applied adds applied to its tilt, so the correction
    # the estimator finds has to move the other way by the same amount.
    assert abs(after - (before - applied)) <= TOLERANCE, (
        f"{frame.provenance.label} rotated {applied:+}: found {after:+.2f}, "
        f"expected {before - applied:+.2f}"
    )


def test_straightened_page_stays_straight() -> None:
    """Running deskew on its own output should find nothing left to do."""
    frame = pages_of(fixture(74))[RECTO]
    straightened = Deskew().apply(frame).frames[0]

    again = angle_of(straightened.image, straightened.provenance.dpi)
    assert abs(again) <= TOLERANCE


def test_cap_leaves_the_page_alone() -> None:
    """An estimate past the cap is treated as a failed estimate, not a tilt.

    Nothing in the four parts reaches the real cap of 4.0 degrees, so this
    lowers it below a page that genuinely needs 1.2 and checks the stage
    declines.
    """
    frame = pages_of(fixture(74))[RECTO]
    output = Deskew(cap=0.5).apply(frame)

    assert output.frames == [frame]
    assert "cap" in output.summary
