"""Remove scanner noise by dropping tiny connected components.

The scans arrive already binarised, and badly: every page carries thousands of
one and two pixel marks. They cost nothing to look at and a great deal to
process, because every speck is a connected component that OCR will try to read
as punctuation, and because every projection profile in the stages that follow
is measuring ink, and a speck is ink.

Choosing the threshold is the whole job, and it is not symmetric. Leaving a
speck in costs a stray mark. Taking a comma out costs a character that nothing
downstream can recover, because by then there is no evidence it was ever there.
So the default sits well below where damage begins.

The number came from measuring page 9 of the Jammy sample at 300 dpi:

    area   components   what they are
    1-5    2,012        single and double pixel marks, pure noise
    6-15   5,102        round dots, scattered through the margins
    16-25  1,303        the first punctuation shapes appear
    26-44    907        commas and apostrophes, clearly type
    45-89  1,315        periods, colons and the dots over i
    90+    7,003        letters and letter fragments

Rendering a blank margin window at rising thresholds, the removable speckle in
it drops from 20 marks to 3 by the time the threshold reaches 15, and does not
improve after that: what survives is ink blots too large for an area filter to
touch. Meanwhile the damage starts much higher up. At 60 the dots over i begin
disappearing, so "principio" renders as "prıncıpıo", and by 90 commas are going
too. That leaves a wide safe band, and 16 sits near the bottom of it: it takes
out 40 percent of the components on the page while costing 1.1 percent of the
ink, and it is nowhere near the punctuation.

A convenient way to hold it in mind: anything smaller than a 4 by 4 pixel block
at 300 dpi is noise.
"""

from __future__ import annotations

import numpy as np

import cv2

from recto.frames import Box, Finding, Frame
from recto.pipeline import StageOutput

MIN_AREA = 16
"""Smallest component kept, in pixels, at REFERENCE_DPI."""

REFERENCE_DPI = 300
"""The resolution MIN_AREA was measured at."""

INK_BELOW = 200
"""Pixels darker than this count as ink."""

WHITE = 255

MAX_FINDINGS = 300
"""Cap on specks drawn in the debug overlay. See _findings for why."""


class Despeckle:
    """Drop connected components below a minimum area."""

    name = "despeckle"

    def __init__(
        self,
        min_area: int = MIN_AREA,
        *,
        reference_dpi: int = REFERENCE_DPI,
        ink_below: int = INK_BELOW,
        max_findings: int = MAX_FINDINGS,
    ) -> None:
        self.min_area = min_area
        self.reference_dpi = reference_dpi
        self.ink_below = ink_below
        self.max_findings = max_findings

    def threshold_for(self, dpi: int) -> int:
        """Scale the area threshold to the resolution the page was rendered at.

        Area grows with the square of the resolution, so a threshold measured at
        300 dpi is four times too small at 600. Getting this wrong is quiet:
        the pipeline still runs, it just stops removing anything.
        """
        scale = (dpi / self.reference_dpi) ** 2
        return max(2, round(self.min_area * scale))

    def apply(self, frame: Frame) -> StageOutput:
        min_area = self.threshold_for(frame.provenance.dpi)

        ink = (frame.image < self.ink_below).astype(np.uint8)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
        areas = stats[:, cv2.CC_STAT_AREA]

        small = areas < min_area
        # Label 0 is the background, which is by far the largest component on
        # the page and must never be considered for removal.
        small[0] = False

        cleaned = frame.image.copy()
        cleaned[small[labels]] = WHITE

        removed = int(small.sum())
        total = max(count - 1, 0)
        ink_removed = int(areas[small].sum())
        ink_total = int(areas[1:].sum()) if total else 0

        summary = (
            f"removed {removed:,} of {total:,} components under area {min_area}, "
            f"{ink_removed / ink_total:.2%} of ink"
            if ink_total
            else "no ink on this frame, kept as is"
        )

        return StageOutput(
            frames=[frame.derive(cleaned)],
            findings=self._findings(stats, areas, small),
            summary=summary,
        )

    def _findings(
        self,
        stats: np.ndarray,
        areas: np.ndarray,
        small: np.ndarray,
    ) -> list[Finding]:
        """Mark the largest of the removed components, not a sample of them.

        Tens of thousands of boxes would be slow to draw and impossible to read,
        so the overlay has to show a subset. The largest removals are the right
        subset: they are the ones closest to the threshold, which makes them the
        ones most likely to be punctuation that should have been kept. A random
        sample would mostly show single pixels, which prove nothing.
        """
        removed_labels = np.flatnonzero(small)
        if removed_labels.size == 0:
            return []

        largest_first = removed_labels[np.argsort(areas[removed_labels])[::-1]]

        return [
            Finding(
                kind="speck",
                shape=Box(
                    int(stats[label, cv2.CC_STAT_LEFT]),
                    int(stats[label, cv2.CC_STAT_TOP]),
                    int(stats[label, cv2.CC_STAT_WIDTH]),
                    int(stats[label, cv2.CC_STAT_HEIGHT]),
                ),
                note=f"area {int(areas[label])}",
            )
            for label in largest_first[: self.max_findings]
        ]
