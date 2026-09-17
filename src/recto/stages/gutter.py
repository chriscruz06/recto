"""Find the gutter of a spread: the fold between its two pages.

The textbook way to find a gutter is to look for the widest band of white down
the middle of the image, because in a clean scan the fold is empty paper. This
scan is the other way round. The binding curves away from the glass and the
shadow it casts was binarised along with everything else, so what sits between
the two pages is a band of black. Measured over the 76 pages of the sample,
the smoothed ink fraction at the fold runs 0.53 to 1.00, median 0.90, against
a median of about 0.22 for the ordinary text around it. The gutter is a
maximum in the column profile, not a valley, and a valley finder pointed at
this book would lock onto the white margin beside the fold instead.

The method is a column profile. Take the fraction of each pixel column that is
ink, smooth it a little, and find the highest point near the centre of the
spread. The band is then everything around that peak still at least half as
dark as the peak itself. Half the peak is a relative test rather than a fixed
ink level, and that is what lets one rule measure the title page, whose fold
is a thin grey line peaking at 0.53, the same way as page 10, whose fold is
solid black at 1.00.

Measurements behind the two constants, taken over all 76 pages after
CropBorder and Despeckle:

    SMOOTH_WIDTH. The answer is unchanged for any width from 1 to 45 pixels:
    no page's centre moves more than 3 px across that whole range. At 60 the
    title page breaks, its band swelling from 24 px to 377 px and its centre
    moving 496 px, because its fold is faint enough to be averaged into the
    surrounding page. So the safe band has a hard top and no measurable
    bottom, and 16 sits near the bottom of it deliberately. Widening the
    filter also widens every band: the title page measures 24 px at 16 and
    34 px at 30, and the band is what the split will cut away.

    SEARCH_FRACTION. The largest distance measured between the gutter centre
    and the middle of the image was 104 px, 1.8 percent of the page width,
    median 16 px. A window of 12 percent either side is about six times that.

Neither constant is load-bearing on this scan. The fold is dark enough that
widening the window to 40 percent and dropping the smoothing entirely still
finds the same band on all 76 pages. They are guards for a scan that is not
this one: the window bounds how far a split can land from the middle if the
input turns out not to be a spread, and the smoothing holds the edition's
printed column rules down. Those rules measure 6 to 20 px wide and reach a
raw column ink of 0.77, high enough to matter if they ever fell inside the
window; at 16 px of smoothing the one measured on page 76 falls to 0.30
against a fold peak of 1.00.

The stage reports a runner-up: the darkest point in the window outside the
band. On most pages that is ordinary text ink, around 0.25, though on page 11
it is the second lobe of the fold itself at 0.56. The peak beats it by a
median factor of 3.1, worst 1.78. A page where that ratio approaches 1 is one
whose fold was not clearly the darkest band near the middle, which is why
SplitSpread prints it.

This module measures and does not cut. It holds no stage of its own: SplitSpread
calls find_gutter, rather than a detection stage leaving its result on the frame
for the split to pick up, because a note passed from one stage to another is a
channel the debug overlay cannot show.

Known limitation, found on page 11: where the binding shadow has two dark
lobes the band takes the darker one and the other survives as a stripe at the
edge of a page. See split.py for what that costs.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

SEARCH_FRACTION = 0.12
"""Search this fraction of the width either side of centre."""

SMOOTH_WIDTH = 16
"""Box filter width over the column profile, in pixels at REFERENCE_DPI."""

REFERENCE_DPI = 300
"""The resolution SMOOTH_WIDTH is measured at."""

INK_BELOW = 200
"""Pixels darker than this count as ink."""


@dataclass(frozen=True)
class Gutter:
    """Where the gutter is, and the evidence for it."""

    left: int
    """First pixel column of the dark band."""

    right: int
    """One past the last pixel column of the dark band."""

    peak: float
    """Smoothed ink fraction at the darkest point of the band."""

    floor: float
    """Median smoothed ink fraction across the search window."""

    runner_up: float
    """Darkest smoothed ink fraction in the window outside the band."""

    runner_up_at: int
    """Pixel column where runner_up was found."""

    window: tuple[int, int]
    """The columns that were searched, start inclusive and end exclusive."""

    @property
    def centre(self) -> int:
        return (self.left + self.right) // 2

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def found(self) -> bool:
        return self.width > 0

    @property
    def margin(self) -> float:
        """How far the peak beats the best thing outside the band.

        Measured 1.78 to 4.92 on the sample, median 3.1. Near 1 means the
        darkest band near the middle was no darker than the page around it,
        which is what a page that is not a spread should look like.
        """
        return self.peak / self.runner_up if self.runner_up > 0 else float("inf")


def find_gutter(
    image: np.ndarray,
    dpi: int,
    *,
    search_fraction: float = SEARCH_FRACTION,
    smooth_width: int = SMOOTH_WIDTH,
    reference_dpi: int = REFERENCE_DPI,
    ink_below: int = INK_BELOW,
) -> Gutter:
    """Locate the dark band down the middle of a spread.

    A plain function rather than a method, so the split stage can call it
    without building a FindGutter first.
    """
    ink = image < ink_below
    width = ink.shape[1]

    # Smoothing is a length, so it scales linearly with resolution.
    kernel_width = max(1, round(smooth_width * dpi / reference_dpi))
    profile = ink.mean(axis=0)
    smoothed = np.convolve(profile, np.ones(kernel_width) / kernel_width, mode="same")

    centre = width // 2
    reach = max(kernel_width, int(width * search_fraction))
    lo, hi = max(0, centre - reach), min(width, centre + reach)
    window = smoothed[lo:hi]

    floor = float(np.median(window))
    at = int(np.argmax(window))
    peak = float(window[at])

    if peak <= 0:
        return Gutter(centre, centre, 0.0, floor, 0.0, centre, (lo, hi))

    # Walk out from the peak to the first column on each side that drops below
    # half of it. Stopping at the window edge keeps a weak peak from growing a
    # band that runs out into the text.
    below = window < peak / 2
    gaps_left = np.flatnonzero(below[:at])
    gaps_right = np.flatnonzero(below[at:])
    left = lo + (int(gaps_left[-1]) + 1 if gaps_left.size else 0)
    right = lo + at + (int(gaps_right[0]) if gaps_right.size else len(window) - at)

    # The runner-up is whatever is darkest in the window once the band and the
    # smoothing's spill either side of it are set aside.
    outside = np.ones(len(window), dtype=bool)
    start = max(0, left - lo - kernel_width)
    outside[start : right - lo + kernel_width] = False
    if outside.any():
        next_at = int(np.argmax(np.where(outside, window, -1.0)))
        runner_up, runner_up_at = float(window[next_at]), lo + next_at
    else:
        runner_up, runner_up_at = 0.0, centre

    return Gutter(left, right, peak, floor, runner_up, runner_up_at, (lo, hi))
