"""Cut a spread into its two pages at the gutter.

This is where the pipeline stops working on photographs and starts working on
pages. Everything before it narrows one image; from here on a page frame knows
which side of the book it came from, and its label says so.

The cut goes at the edges of the gutter band, not at its centre. Cutting at the
centre would leave half the fold on each page, and the fold is the darkest thing
on the spread: 0.53 to 1.00 ink against 0.22 for text. That much ink on the
inner edge of every page would bias the deskew estimate, make a blank verso read
as inky, and hand OCR a black bar to interpret. The band is the thing this stage
exists to throw away.

The measurements, taken over all 76 pages of the sample:

    There is room to cut. Between the band edge and the nearest ink on the page
    side there is a median of 279 px of white, minimum 45. The band never runs
    close to type.

    The fold has a fringe past the band edge, because the band ends where the
    ink falls to half the peak and the shadow keeps fading after that. Measured
    to where it drops under a tenth of the peak, the fringe reaches 11 px past
    the band on a median edge and 32 px on the worst of the 152 edges. INSET is
    32 so that every edge in the sample clears it. The cost is small: after
    insetting, the median white left before the next ink is still 247 px, and
    the tightest case is 22 px on page 74, where what sits near the cut is
    scanner speckle rather than type.

Known residue, page 11. Where the binding shadow has two dark lobes the band
takes the darker one, and the other stays on the verso as a speckled stripe
about 100 px wide. It is noise, not type, and nothing downstream reads it as
text, but it is ink that the blank check and the deskew will see. Two pages of
the sample show it. The fix, if it turns out to matter, is to look for a second
lobe rather than to widen the inset, which would start eating margins on the
other 74 pages.

The stage does not refuse a page. All 76 spreads split correctly, the weakest
at a peak-to-runner-up margin of 1.78, so there is no measured basis for a
threshold below which the split should decline, and inventing one would mean
guessing. What it does instead is put the margin in the summary line, so a page
where the fold was not clearly the darkest band near the middle is visible in
the debug output rather than silently wrong.
"""

from __future__ import annotations

import numpy as np

from recto.frames import Box, Finding, Frame, Line, RECTO, VERSO
from recto.pipeline import StageOutput
from recto.stages.gutter import find_gutter

INSET = 32
"""Extra pixels trimmed past each band edge at REFERENCE_DPI, for the fringe."""

REFERENCE_DPI = 300
"""The resolution INSET is measured at."""


class SplitSpread:
    """Cut the spread at the gutter, verso first then recto."""

    name = "split-spread"

    def __init__(
        self,
        *,
        inset: int = INSET,
        reference_dpi: int = REFERENCE_DPI,
    ) -> None:
        self.inset = inset
        self.reference_dpi = reference_dpi

    def apply(self, frame: Frame) -> StageOutput:
        gutter = find_gutter(frame.image, frame.provenance.dpi)
        width = frame.width
        inset = round(self.inset * frame.provenance.dpi / self.reference_dpi)

        left = max(0, gutter.left - inset)
        right = min(width, gutter.right + inset)

        band = Finding(
            "gutter",
            Box(gutter.left, 0, gutter.width, frame.height),
            note=f"peak {gutter.peak:.2f}, {gutter.margin:.1f}x the next darkest",
        )

        # The search window already caps the cut at search_fraction from the
        # middle, so neither half can normally come out this small. This is here
        # so that a future profile with a careless window degrades to "did not
        # split" rather than to a sliver that fails somewhere further down with
        # no explanation.
        if left < width // 4 or right > width - width // 4:
            return StageOutput(
                frames=[frame],
                findings=[band],
                summary=f"cut at {left} and {right} would leave a sliver, not split",
            )

        # Slicing columns gives a view into the spread, which keeps the whole
        # spread alive in memory and hands OpenCV a non-contiguous array further
        # down. Copy, so each page stands on its own.
        verso = np.ascontiguousarray(frame.image[:, :left])
        recto = np.ascontiguousarray(frame.image[:, right:])

        where = "at the fold" if gutter.found else "at the middle, no fold found"
        summary = (
            f"split {where}: cut {left} and {right} of {width}, "
            f"verso {left}px, recto {width - right}px, "
            f"dropped {right - left}px, margin {gutter.margin:.1f}x"
        )

        return StageOutput(
            frames=[
                frame.derive(verso, side=VERSO),
                frame.derive(recto, side=RECTO),
            ],
            findings=[
                band,
                Finding("frame", Line(left, 0, left, frame.height), note="verso cut"),
                Finding("frame", Line(right, 0, right, frame.height), note="recto cut"),
            ],
            summary=summary,
        )
