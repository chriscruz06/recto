"""Regression cover for finding and whiting out figures.

The crops are 300 dpi pieces of straightened pages, as the stage receives them.
tests/make_fixtures.py says why they are not the 100 dpi spread fixtures.

Each figure was marked by hand as two rectangles, drawn on the crop and checked
by eye. REGION is the figure's whole visible extent, including anything welded
to it, and CORE sits well inside it. The assertions are the plan's done-when,
stated so they can be checked:

    The figure is boxed: every core ends up covered.

    Nothing else is boxed: every box the stage finds overlaps a marked region,
    so the negative crops, full of things a size rule would take, must come
    back with none.

    No type loses ink: every component that is not wholly inside a marked
    region keeps at least 99 percent of its ink through the masking. This is
    the one that matters. It is how the box around the page 11 initial was
    caught shaving the tops off the line below it, before the box was trimmed
    to the figure's body. Measured now, every such component in every crop
    keeps all of its ink.

Marking a region rather than an exact box makes the tests robust to the stage
landing a pixel or two differently on another machine, whose deskew can settle
a step away from this one's and move a figure slightly.
"""

from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np
import pytest

from conftest import FigureCrop, ink, load_figure_crops
from recto.frames import Box
from recto.pipeline import StageOutput
from recto.stages.figures import MaskFigures

REGION = {
    "hieronymus": [(130, 110, 1930, 590), (120, 1370, 720, 1960)],
    "initial-i": [(150, 150, 750, 770)],
    "device": [(150, 180, 1070, 920)],
    "initial-v": [(140, 130, 330, 320)],
    "title-woodcut": [(100, 110, 2240, 1700)],
}
"""Figure extents as (x0, y0, x1, y1) in crop pixels. Crops not listed hold no
figures and must come back with no boxes."""

MARGIN = 50
"""A core is its region shrunk by this much on every side."""

KEEP = 0.99
"""Share of its ink every piece of type must keep."""


@lru_cache(maxsize=None)
def masked(crop: FigureCrop) -> tuple[np.ndarray, StageOutput]:
    """Run the stage once per crop per session."""
    frame = crop.frame()
    return frame.image, MaskFigures().apply(frame)


def regions(crop: FigureCrop) -> list[tuple[int, int, int, int]]:
    return REGION.get(crop.name, [])


def cores(crop: FigureCrop) -> list[tuple[int, int, int, int]]:
    return [
        (x0 + MARGIN, y0 + MARGIN, x1 - MARGIN, y1 - MARGIN)
        for x0, y0, x1, y1 in regions(crop)
    ]


def overlaps(box: Box, area: tuple[int, int, int, int]) -> bool:
    x0, y0, x1, y1 = area
    across = box.x < x1 and x0 < box.x + box.width
    down = box.y < y1 and y0 < box.y + box.height
    return across and down


def within(box: tuple[int, int, int, int], area: tuple[int, int, int, int]) -> bool:
    x, y, w, h = box
    x0, y0, x1, y1 = area
    return x >= x0 and y >= y0 and x + w <= x1 and y + h <= y1


@pytest.mark.parametrize("crop", load_figure_crops(), ids=str)
def test_every_figure_is_boxed(crop: FigureCrop) -> None:
    image, output = masked(crop)
    boxed = np.zeros(image.shape, dtype=bool)
    for finding in output.findings:
        b = finding.shape
        boxed[b.y : b.y + b.height, b.x : b.x + b.width] = True

    for x0, y0, x1, y1 in cores(crop):
        covered = float(boxed[y0:y1, x0:x1].mean())
        assert covered >= 0.99, (
            f"{crop.name}: only {covered:.0%} of the figure at {x0},{y0} was boxed"
        )


@pytest.mark.parametrize("crop", load_figure_crops(), ids=str)
def test_nothing_else_is_boxed(crop: FigureCrop) -> None:
    _, output = masked(crop)
    for finding in output.findings:
        assert any(overlaps(finding.shape, r) for r in regions(crop)), (
            f"{crop.name}: boxed {finding.shape}, which is not a figure"
        )


@pytest.mark.parametrize("crop", load_figure_crops(), ids=str)
def test_type_keeps_its_ink(crop: FigureCrop) -> None:
    image, output = masked(crop)
    before = ink(image).astype(np.uint8)
    after = ink(output.frames[0].image)

    count, labels, stats, _ = cv2.connectedComponentsWithStats(before, connectivity=8)
    # Ink that survived, summed per component in a single pass.
    surviving = np.bincount(labels.ravel(), weights=after.ravel(), minlength=count)
    for label in range(1, count):
        box = tuple(int(v) for v in stats[label, :4])
        if any(within(box, r) for r in regions(crop)):
            continue
        area = int(stats[label, cv2.CC_STAT_AREA])
        kept = float(surviving[label]) / area
        assert kept >= KEEP, (
            f"{crop.name}: component at {box[0]},{box[1]} kept only {kept:.0%} "
            "of its ink"
        )
