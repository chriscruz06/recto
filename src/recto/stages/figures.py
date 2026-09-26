"""Find woodcuts, decorated initials and printer's ornaments, and white them out.

They have to go before the column split. A headpiece spans both columns and
fills the whitespace valley the split reads, and a drop cap is a block of solid
ink that OCR will read as a string of punctuation.

The obvious rule is size: anything far bigger than a letter is a figure. On
this scan that rule deletes body text. The binarisation is heavy enough that on
many pages whole paragraphs of type have fused into single connected
components. On page 12 the lower half of the right column is one component,
915 by 1494 px, bigger than any drop cap in the volume. The median glyph area is
no yardstick either: measured on eleven pages it runs from 30 px to 330 px,
depending on whether surviving speckle or fused words dominate the count.

So a component is a figure only when it passes all five tests below. Each was
measured on every component over 15,000 px on eleven pages, hand labelled as
one of fifteen figures, sixteen fused-text blobs, seven title-page capitals or
ten printed column rules, then checked against every page of the volume.

    MIN_AREA. The smallest real figure is the decorated V on page 1 at
    20,592 px. Below 15,000 there is nothing that is a figure rather than a
    piece of one.

    MAX_ASPECT. The column rules are single components 1,760 to 4,077 px tall
    and 22 to 123 px wide, an aspect of 33 or more. No figure exceeds 8. The
    rules must survive, because the column split may read them.

    MIN_HOLES. Hatching encloses white, so a woodcut is full of holes: 59 on
    the smallest figure, 5,570 on the title woodcut. The display capitals on
    the title page are as large as a drop cap but are letters, with 6 to 25.

    MAX_ROW_VARIATION. Text is printed lines with lighter rows between them, so
    the ink per row inside its box swings, while a woodcut is inked all the way
    through. Measured as the coefficient of variation of row ink, ignoring the
    outer tenth of rows where an ornament's outline tapers: figures 0.06 to
    0.30, fused text 0.41 to 0.52.

    MAX_LINE_PITCH. Row variation fails when the text is dark enough to fill
    the gaps between lines, which is what happened on page 12. What survives is
    regularity: the lines still repeat at the book's line pitch. Scored as the
    strongest autocorrelation of the detrended row profile at a lag between 35
    and 75 px: figures 0.05 to 0.36, every fused block tall enough to hold three
    lines 0.47 to 0.84, the page 12 block at 0.84. A blob too short to show a
    pitch is left to the row variation test, which catches those.

The whole box is whited out, not the component's silhouette. Compared on the
volume, the silhouette leaves a grey halo and fragments of the headpiece on
page 1, and on the one case where the choice could have saved text, below, it
loses exactly the same letters.

Known behaviour, measured over all 148 pages:

    The speckled scanner strip along the outer edge of a recto, outside the
    leaf, passes on pages 12 and 45 and is whited out. There is no text there,
    so it costs nothing, but the finding is labelled figure when it is noise.

    An ink blot on page 33 passes. It has fused with four letters it sits on,
    and those letters go with it; letters that only share its bounding box
    survive. Excluding blots would need a rule separating them from woodcuts,
    and the only candidate measured, enclosed white, splits them at 0.04
    against 0.08 on a single example. That is not a rule worth shipping.

    A band of separate fleurons, like the one heading the privilege on page 3,
    is found only through its largest fused piece, and the fleurons outside
    that piece's box remain.

The boxes are the record. Findings are what the manifest will carry, so what
was whited out of a page, and where, survives past the run that did it.
"""

from __future__ import annotations

import cv2
import numpy as np

from recto.frames import Box, Finding, Frame
from recto.pipeline import StageOutput

MIN_AREA = 15_000
"""Smallest component, in pixels at REFERENCE_DPI, considered at all."""

MAX_ASPECT = 16
"""Longer side over shorter. Above this it is a rule, not a figure."""

MIN_HOLES = 40
"""Enclosed white regions a component needs to be hatching rather than a letter."""

MAX_ROW_VARIATION = 0.35
"""Row-ink variation inside the box above which it is text. See the docstring."""

MAX_LINE_PITCH = 0.42
"""Line-pitch regularity above which it is text. See the docstring."""

PITCH_RANGE = (35, 75)
"""Lags searched for a line pitch, in pixels at REFERENCE_DPI."""

EDGE_TRIM = 0.10
"""Fraction of rows ignored at the top and bottom of a box when measuring it."""

REFERENCE_DPI = 300
"""The resolution MIN_AREA is measured at."""

INK_BELOW = 200
"""Pixels darker than this count as ink."""

WHITE = 255


def count_holes(component: np.ndarray) -> int:
    """White regions fully enclosed by the component."""
    _, hierarchy = cv2.findContours(
        component, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
    )
    if hierarchy is None:
        return 0
    return int((hierarchy[0][:, 3] >= 0).sum())


def row_variation(ink_in_box: np.ndarray, trim: float = EDGE_TRIM) -> float:
    """Coefficient of variation of row ink inside a box, edges trimmed."""
    rows = ink_in_box.mean(axis=1)
    cut = max(1, int(len(rows) * trim))
    if len(rows) > 4 * cut:
        rows = rows[cut:-cut]
    mean = float(rows.mean())
    return float(rows.std() / mean) if mean > 0 else 0.0


def line_pitch(
    ink_in_box: np.ndarray,
    lags: tuple[int, int],
    trim: float = EDGE_TRIM,
) -> float | None:
    """How strongly the rows repeat at a printed line pitch.

    The row profile is detrended first, so a block that darkens towards the
    foot of the page scores on its line structure rather than on the drift.
    Returns None when the box is too short to hold a pitch, so the caller can
    tell "not periodic" apart from "could not measure".
    """
    rows = ink_in_box.mean(axis=1).astype(np.float64)
    cut = max(1, int(len(rows) * trim))
    if len(rows) > 4 * cut:
        rows = rows[cut:-cut]

    low, high = lags
    if len(rows) < 2 * low + 10:
        return None

    span = 2 * high + 1
    if len(rows) > span:
        rows = rows - np.convolve(rows, np.ones(span) / span, mode="same")
    rows = rows - rows.mean()
    energy = float((rows * rows).sum())
    if energy == 0:
        return 0.0

    return max(
        float((rows[:-lag] * rows[lag:]).sum()) / energy
        for lag in range(low, min(high, len(rows) // 2) + 1)
    )


def outermost(boxes: list[Box]) -> list[Box]:
    """Drop any box that lies wholly inside another.

    A woodcut can break into pieces that each pass on their own, like the
    inner panel of the title woodcut. Whiting it twice does no harm, but it
    would put a redundant entry in the record the manifest reads.
    """
    kept: list[Box] = []
    for box in sorted(boxes, key=lambda b: b.width * b.height, reverse=True):
        inside = any(
            k.x <= box.x
            and k.y <= box.y
            and k.x + k.width >= box.x + box.width
            and k.y + k.height >= box.y + box.height
            for k in kept
        )
        if not inside:
            kept.append(box)
    return sorted(kept, key=lambda b: (b.y, b.x))


class MaskFigures:
    """Box and white out anything that is a picture rather than type."""

    name = "mask-figures"

    def __init__(
        self,
        *,
        min_area: int = MIN_AREA,
        max_aspect: float = MAX_ASPECT,
        min_holes: int = MIN_HOLES,
        max_row_variation: float = MAX_ROW_VARIATION,
        max_line_pitch: float = MAX_LINE_PITCH,
        pitch_range: tuple[int, int] = PITCH_RANGE,
        reference_dpi: int = REFERENCE_DPI,
    ) -> None:
        self.min_area = min_area
        self.max_aspect = max_aspect
        self.min_holes = min_holes
        self.max_row_variation = max_row_variation
        self.max_line_pitch = max_line_pitch
        self.pitch_range = pitch_range
        self.reference_dpi = reference_dpi

    def figures(self, image: np.ndarray, dpi: int) -> list[Box]:
        """Boxes of every component that passes all five tests."""
        ink = (image < INK_BELOW).astype(np.uint8)
        _, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)

        # Area grows with the square of resolution, lengths linearly.
        scale = dpi / self.reference_dpi
        floor = self.min_area * scale**2
        lags = (
            max(2, round(self.pitch_range[0] * scale)),
            max(3, round(self.pitch_range[1] * scale)),
        )
        found = []
        for label in np.flatnonzero(stats[1:, cv2.CC_STAT_AREA] >= floor) + 1:
            x, y, w, h = (int(v) for v in stats[label, :4])

            if max(w, h) / max(1, min(w, h)) > self.max_aspect:
                continue
            own = (labels[y : y + h, x : x + w] == label).astype(np.uint8)
            if count_holes(own) < self.min_holes:
                continue
            box = ink[y : y + h, x : x + w]
            if row_variation(box) > self.max_row_variation:
                continue
            pitch = line_pitch(box, lags)
            if pitch is not None and pitch > self.max_line_pitch:
                continue
            found.append(Box(x, y, w, h))
        return outermost(found)

    def apply(self, frame: Frame) -> StageOutput:
        boxes = self.figures(frame.image, frame.provenance.dpi)
        if not boxes:
            return StageOutput(frames=[frame], summary="no figures")

        masked = frame.image.copy()
        for box in boxes:
            masked[box.y : box.y + box.height, box.x : box.x + box.width] = WHITE

        area = sum(b.width * b.height for b in boxes) / (frame.width * frame.height)
        return StageOutput(
            frames=[frame.derive(masked)],
            findings=[
                Finding("figure", b, note=f"{b.width}x{b.height}") for b in boxes
            ],
            summary=f"masked {len(boxes)} figure(s), {area:.1%} of the page",
        )
