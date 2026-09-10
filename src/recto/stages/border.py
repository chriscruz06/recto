"""Crop the black scanner border off a spread.

Every page in the sample is surrounded by a band of solid black where the
scanner saw past the edge of the book. It is not decorative: it dominates the
ink on the page, so it biases the deskew estimate, it makes a blank verso look
inky to the blank detector, and it is the largest connected component in every
image the pipeline touches. It has to go first.

Two things make it harder than it sounds.

The border is asymmetric. On this scan the left band is about 74 pixels, the
right runs 57 to 101, the bottom 25 to 62, and the top is barely there at 4 to
11. So a fixed inset is wrong, and each edge has to be measured separately.

The border is also tilted, because the scan is. That means a horizontal band
crosses a row only partway, and the row's mean ink decays gradually from the
edge instead of stepping down. Thresholding on the mean is what a first attempt
does, and it lands the crop in a different place on nearly every page: on the
sample it put the right edge at 305 pixels on three pages and 78 on a fourth,
because it was picking up dense scanner noise as though it were border.

What works is asking a different question. A border row contains one very long
unbroken run of ink, thousands of pixels wide. A row of type never does: the
longest run measured anywhere in the body text of the sample was 348 pixels,
against a threshold of 888. Run length also survives the tilt, because a band
crossing part of a row is still an unbroken stretch.

Run length alone over-crops in one specific way, which the title page found.
The right side of that page carries a wide strip of dense speckle whose runs
are long but whose ink is thin, and cropping on run length alone cut 539 pixels
off the right edge, straight through the final I of ALBERTI. So an edge has to
satisfy both tests: a long unbroken run, and a genuinely dark line. With both,
that page crops 74 pixels like every other one.

Known limitation: a rectangle cannot follow a tilted border, so a wedge of
black survives in two opposite corners. It is small, it never reaches the text
block, and every consumer of this stage tolerates it. The clean fix is a second
crop after deskew, once the border is axis-aligned, and that is worth doing
only if the residue turns out to matter.
"""

from __future__ import annotations

import numpy as np

from recto.frames import Box, Finding, Frame
from recto.pipeline import StageOutput

RUN_FRACTION = 0.15
"""An edge line must hold an unbroken ink run at least this fraction of its span."""

DARK_FRACTION = 0.5
"""And at least this fraction of the whole line must be ink."""

SEARCH_FRACTION = 0.15
"""Only look this far in from each edge, which also caps how much can be cut."""

INSET = 8
"""Extra pixels trimmed past the detected edge at REFERENCE_DPI, for the fringe."""

REFERENCE_DPI = 300

INK_BELOW = 200


def longest_runs(mask: np.ndarray, axis: int) -> np.ndarray:
    """Longest unbroken run of True along each row (axis=1) or column (axis=0).

    Vectorised rather than looped: differencing a padded mask turns every run
    into a matching pair of rising and falling edges, and maximum.at reduces
    those to one value per line. On a 5921 by 4385 page the loop version takes
    long enough to be annoying during tuning, which is when it gets run most.
    """
    lines = mask if axis == 1 else mask.T
    padded = np.pad(lines, ((0, 0), (1, 1)), constant_values=False).astype(np.int8)
    deltas = np.diff(padded, axis=1)

    starts_line, starts_at = np.where(deltas == 1)
    _, ends_at = np.where(deltas == -1)

    longest = np.zeros(lines.shape[0], dtype=int)
    if starts_line.size:
        np.maximum.at(longest, starts_line, ends_at - starts_at)
    return longest


class CropBorder:
    """Trim the black scanner border, one edge at a time."""

    name = "crop-border"

    def __init__(
        self,
        *,
        run_fraction: float = RUN_FRACTION,
        dark_fraction: float = DARK_FRACTION,
        search_fraction: float = SEARCH_FRACTION,
        inset: int = INSET,
        reference_dpi: int = REFERENCE_DPI,
        ink_below: int = INK_BELOW,
    ) -> None:
        self.run_fraction = run_fraction
        self.dark_fraction = dark_fraction
        self.search_fraction = search_fraction
        self.inset = inset
        self.reference_dpi = reference_dpi
        self.ink_below = ink_below

    def apply(self, frame: Frame) -> StageOutput:
        ink = frame.image < self.ink_below
        height, width = ink.shape
        inset = round(self.inset * frame.provenance.dpi / self.reference_dpi)

        top, bottom = self._edges(
            longest_runs(ink, axis=1), ink.mean(axis=1), span=width, inset=inset
        )
        left, right = self._edges(
            longest_runs(ink, axis=0), ink.mean(axis=0), span=height, inset=inset
        )

        # The search window already caps each cut at search_fraction, so this
        # cannot normally fire. It is here so that a future profile with a
        # careless search_fraction degrades to "did nothing" rather than to an
        # empty image that fails somewhere further down with no explanation.
        if right - left < width // 2 or bottom - top < height // 2:
            return StageOutput(
                frames=[frame],
                findings=[Finding("frame", Box(0, 0, width, height))],
                summary="crop would have removed most of the page, left uncropped",
            )

        cropped = frame.image[top:bottom, left:right]
        summary = (
            f"cropped L{left} T{top} R{width - right} B{height - bottom}, "
            f"{width}x{height} to {right - left}x{bottom - top}"
        )

        return StageOutput(
            frames=[frame.derive(cropped)],
            findings=[Finding("frame", Box(left, top, right - left, bottom - top))],
            summary=summary,
        )

    def _edges(
        self,
        runs: np.ndarray,
        means: np.ndarray,
        *,
        span: int,
        inset: int,
    ) -> tuple[int, int]:
        """Find where the border stops at each end of one axis.

        A line counts as border when it holds a long unbroken run and is mostly
        ink. Both tests matter: see the module docstring for the page that
        proves it. The answer is the last border line found within the search
        window, not the first non-border line, because the border is ragged and
        has white gaps in it that would otherwise stop the scan early.
        """
        count = len(runs)
        border = (runs >= self.run_fraction * span) & (means >= self.dark_fraction)
        window = max(1, int(count * self.search_fraction))

        head = np.flatnonzero(border[:window])
        low = int(head[-1]) + 1 + inset if head.size else 0

        tail = np.flatnonzero(border[-window:])
        high = count - (window - int(tail[0])) - inset if tail.size else count

        return max(0, low), min(count, high)
