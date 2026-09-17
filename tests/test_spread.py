"""Regression cover for finding the gutter and cutting the spread at it.

The expected gutter positions below were not taken from find_gutter. They were
measured off the 300 dpi render with a deliberately different and much dumber
rule: the contiguous run of columns in the middle fifth of the page that are at
least half ink, with no smoothing, no search window and no half-peak walk. Five
of the twelve were then checked by eye at full resolution, including the widest
fold, the thinnest, and the two-lobed one. Had the expected values come out of
the stage under test, this file would assert only that the code still does
whatever it did the day it was written.

Distances are in source pixels at 300 dpi throughout, so the numbers stay
comparable to every other measurement in the project and survive regenerating
the fixtures at a different resolution.
"""

from __future__ import annotations

import pytest

from conftest import FixturePage, load_fixtures
from recto.frames import RECTO, VERSO
from recto.stages.border import CropBorder
from recto.stages.despeckle import Despeckle
from recto.stages.gutter import find_gutter
from recto.stages.split import SplitSpread

GUTTER_CENTRE = {
    1: 2972,
    2: 2965,
    4: 3000,
    10: 3054,
    11: 3057,
    13: 3062,
    24: 2974,
    43: 2982,
    56: 2937,
    60: 2923,
    74: 2956,
    76: 2957,
}
"""Hand-measured gutter centre per page, in source pixels. See the docstring."""

TOLERANCE = 12
"""Source pixels. Measured error across the twelve pages is 0 to 4, so this is
three times the worst case, and the failure it exists to catch moves the answer
by 494."""

EDGE_STRIP = 40
"""Source pixels at a page's inner edge, checked for surviving fold."""

EDGE_INK = 0.15
"""No column in that strip may be inkier than this. Measured worst is 0.07,
excluding the page below. A fold is 0.53 to 1.00, so this is nowhere near
either."""

KNOWN_RESIDUE = {(11, VERSO): 0.60}
"""Page 11's fold has two dark lobes. The band takes the darker one and the
other stays on the verso, measured at 0.56. It is documented in split.py as
known residue, so it is allowed here rather than silently passing, and the
bound still fires if it grows."""


def pipeline_to_split(page: FixturePage):
    """Run the stages that come before the split, and report where the crop was.

    The crop offset matters because findings describe the frame a stage was
    given: once CropBorder has cut, every column index downstream is relative to
    the cropped image, and the expected values are relative to the page.
    """
    cropped = CropBorder().apply(page.frame())
    offset = cropped.findings[0].shape.x
    cleaned = Despeckle().apply(cropped.frames[0]).frames[0]
    return cleaned, offset


@pytest.mark.parametrize("page", load_fixtures(), ids=str)
def test_every_fixture_has_a_measured_gutter(page: FixturePage) -> None:
    """A fixture with no expected value would otherwise be silently untested."""
    assert page.page_number in GUTTER_CENTRE


@pytest.mark.parametrize("page", load_fixtures(), ids=str)
def test_gutter_lands_on_the_fold(page: FixturePage) -> None:
    cleaned, offset = pipeline_to_split(page)
    gutter = find_gutter(cleaned.image, cleaned.provenance.dpi)

    found = page.to_source(gutter.centre + offset)
    expected = GUTTER_CENTRE[page.page_number]
    assert abs(found - expected) <= TOLERANCE, (
        f"gutter at {found}, expected {expected} within {TOLERANCE} source px"
    )


@pytest.mark.parametrize("page", load_fixtures(), ids=str)
def test_split_gives_verso_then_recto(page: FixturePage) -> None:
    cleaned, _ = pipeline_to_split(page)
    frames = SplitSpread().apply(cleaned).frames

    assert len(frames) == 2
    verso, recto = frames
    assert verso.provenance.side == VERSO
    assert recto.provenance.side == RECTO
    assert verso.provenance.label.endswith("-verso")
    assert recto.provenance.label.endswith("-recto")

    # Neither half may be a sliver, and together they cannot exceed the spread.
    for half in frames:
        assert half.width > cleaned.width // 4
        assert half.height == cleaned.height
    assert verso.width + recto.width < cleaned.width


@pytest.mark.parametrize("page", load_fixtures(), ids=str)
def test_split_leaves_no_fold_on_the_pages(page: FixturePage) -> None:
    """The point of cutting at the band edges rather than at its centre."""
    cleaned, _ = pipeline_to_split(page)
    verso, recto = SplitSpread().apply(cleaned).frames
    strip = max(1, round(EDGE_STRIP / page.scale))

    edges = (
        (verso, verso.image[:, -strip:]),
        (recto, recto.image[:, :strip]),
    )
    for half, edge in edges:
        side = half.provenance.side
        darkest = float((edge < 200).mean(axis=0).max())
        limit = KNOWN_RESIDUE.get((page.page_number, side), EDGE_INK)
        assert darkest <= limit, (
            f"{half.provenance.label} carries ink at {darkest:.2f} "
            f"within {EDGE_STRIP} source px of the cut, limit {limit}"
        )


def test_a_wrong_smoothing_is_caught() -> None:
    """Proves the tolerance above has teeth.

    The smoothing width is the one gutter constant with a measured failure
    point: anything from 1 to 45 gives the same answer on every page, and at 60
    the title page's fold, the faintest in the volume at 0.53 ink, gets averaged
    into the surrounding paper. At 90 the detected centre moves 494 source px,
    forty times the tolerance. If this test ever passes, either the tolerance
    has been widened past the point of meaning anything or the fixture is no
    longer the title page.
    """
    title = [p for p in load_fixtures() if p.page_number == 2]
    if not title:
        pytest.skip("the title page fixture is missing")
    page = title[0]

    cleaned, offset = pipeline_to_split(page)
    wrong = find_gutter(cleaned.image, cleaned.provenance.dpi, smooth_width=90)
    found = page.to_source(wrong.centre + offset)

    assert abs(found - GUTTER_CENTRE[2]) > TOLERANCE
