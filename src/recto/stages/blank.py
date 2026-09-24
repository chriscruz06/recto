"""Skip pages with nothing printed on them.

The volume has blank versos, and a blank scan is worse than useless downstream:
it costs a deskew pass that has no lines to measure, it produces a column split
from a profile with no columns in it, and it hands OCR an image that yields
either nothing or hallucinated punctuation from the speckle. The check is the
ink ratio, measured after despeckling, on the page as it came off the spread.

What the ratio has to see past is the fold. A blank verso is mostly the scanner
border and the leftover half of the binding shadow, and on page 11, where the
fold has two dark lobes and the stage before this one only cuts the darker one
away, that residue is 73 percent of the ink on the page. Counted plainly, that
page measures 1.55 percent ink against 5.56 for the sparsest printed page in
the volume, a gap of 3.6 times. Dropping the large components that touch the
frame first, which is what the fold residue and the corner wedge are, takes it
to 0.42 percent and opens the gap to 13 times:

    page             plain ink    frame-touching blobs dropped
    p0002-verso        0.254%                 0.254%
    p0003-verso        0.372%                 0.328%
    p0010-recto        0.362%                 0.362%
    p0011-verso        1.549%                 0.417%
    ------------------------------------------------- blank ends here
    p0004-verso        5.558%                 5.511%
    p0001-recto       10.275%                10.275%

Real pages lose almost nothing to that trim, 0.05 percentage points or less,
because type does not touch the frame.

MAX_INK sits at 1.0 percent, not at the middle of the band. The two mistakes
are not equal: keeping a blank page costs one junk image that OCR turns into
nothing, and dropping a printed page loses text that nothing downstream can
recover, because by then there is no evidence it was ever there. So the
threshold sits two and a half times above the inkiest blank and five and a half
times below the sparsest printed page, near the bottom of the safe band.

The skip is recorded rather than silent. A stage that returns no frames deletes
a physical page from the run, and the manifest still has to account for it: the
book has a verso there whether or not anything was printed on it. Skipped pages
land in self.skipped, which is per run because the registry builds stages per
run, the same way DebugWriter accumulates the overlays it has written.

This runs before Deskew, not after. A blank page gives the angle search nothing
to maximise, so whatever angle comes back is arbitrary rather than wrong, and
deskew grows the canvas by up to 6.8 percent, which would dilute the very ratio
this stage measures.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from recto.frames import Box, Finding, Frame, Provenance
from recto.pipeline import StageOutput

MAX_INK = 0.010
"""A page at or under this fraction of ink is blank. See the docstring."""

INK_BELOW = 200
"""Pixels darker than this count as ink."""

EDGE_AREA = 2000
"""Smallest component, in pixels at REFERENCE_DPI, that counts as fold residue
rather than type when it touches the frame. The largest thing on these pages
that is genuinely type is a drop cap at around 1,200 px."""

REFERENCE_DPI = 300
"""The resolution EDGE_AREA is measured at."""


@dataclass(frozen=True)
class Skipped:
    """One page that was not emitted, and why."""

    provenance: Provenance
    ink: float


def page_ink(image: np.ndarray, *, ink_below: int, edge_area: int) -> float:
    """Fraction of the page that is ink, ignoring what the fold left behind.

    A component is discounted when it is both large and touching the frame.
    Both tests matter: type never touches the frame, and the speckle that does
    is never large.
    """
    ink = (image < ink_below).astype(np.uint8)
    height, width = ink.shape

    count, _, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    if count <= 1:
        return 0.0

    left, top = stats[1:, cv2.CC_STAT_LEFT], stats[1:, cv2.CC_STAT_TOP]
    across, down = stats[1:, cv2.CC_STAT_WIDTH], stats[1:, cv2.CC_STAT_HEIGHT]
    areas = stats[1:, cv2.CC_STAT_AREA]

    touching = (
        (left <= 1)
        | (top <= 1)
        | (left + across >= width - 1)
        | (top + down >= height - 1)
    )
    residue = touching & (areas >= edge_area)

    return float((areas.sum() - areas[residue].sum()) / ink.size)


@dataclass
class DropBlank:
    """Emit nothing for a page with no printing on it, and write it down."""

    max_ink: float = MAX_INK
    ink_below: int = INK_BELOW
    edge_area: int = EDGE_AREA
    reference_dpi: int = REFERENCE_DPI
    skipped: list[Skipped] = field(default_factory=list)

    name = "drop-blank"

    def apply(self, frame: Frame) -> StageOutput:
        # Area scales with the square of the resolution, the same way the
        # despeckle threshold does, and for the same reason.
        scale = (frame.provenance.dpi / self.reference_dpi) ** 2
        ink = page_ink(
            frame.image,
            ink_below=self.ink_below,
            edge_area=max(1, round(self.edge_area * scale)),
        )

        findings = [
            Finding(
                kind="ink",
                shape=Box(0, 0, frame.width, frame.height),
                note=f"{ink:.2%} ink",
            )
        ]

        if ink <= self.max_ink:
            self.skipped.append(Skipped(provenance=frame.provenance, ink=ink))
            return StageOutput(
                frames=[],
                findings=findings,
                summary=f"blank at {ink:.2%} ink, page skipped",
            )

        return StageOutput(
            frames=[frame],
            findings=findings,
            summary=f"{ink:.2%} ink, kept",
        )
