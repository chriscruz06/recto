"""What moves through the pipeline, and what stages report about it.

A frame is one image plus the record of where in the physical book it came
from. Stages consume frames and produce frames. A frame that starts life as a
scanned spread becomes two page frames, then four column frames, and the
provenance is what lets the last of those still name its printed page.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

VERSO = "verso"
RECTO = "recto"


@dataclass(frozen=True)
class Provenance:
    """Where a frame came from, in the physical document's own terms."""

    source: Path
    """The PDF this ultimately came out of."""

    page_index: int
    """Zero-based index of the PDF page holding the spread."""

    dpi: int = 300
    """Resolution the page was rendered at.

    Carried because several stages have thresholds measured in pixels, and a
    pixel means something different at 600 dpi. A stage that hardcodes a pixel
    count fails quietly when the resolution changes: it keeps running and stops
    working.
    """

    side: str | None = None
    """VERSO or RECTO once the spread has been split, None before that."""

    column: int | None = None
    """Zero-based column index once the page has been split, None before."""

    @property
    def page_number(self) -> int:
        """One-based PDF page number, matching what a viewer shows."""
        return self.page_index + 1

    @property
    def label(self) -> str:
        """Short identifier, safe to use in a filename and stable to sort.

        Reads as p0009, then p0009-verso, then p0009-verso-c1 as the frame is
        cut down, so a directory listing follows the pipeline.
        """
        parts = [f"p{self.page_number:04d}"]
        if self.side is not None:
            parts.append(self.side)
        if self.column is not None:
            parts.append(f"c{self.column + 1}")
        return "-".join(parts)


@dataclass(frozen=True)
class Box:
    """An axis-aligned rectangle in image coordinates."""

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class Line:
    """A straight line in image coordinates."""

    x1: int
    y1: int
    x2: int
    y2: int


Shape = Box | Line


@dataclass(frozen=True)
class Finding:
    """Something a stage located in the frame it was given.

    Findings exist for two reasons. In the short term they are what the debug
    overlay draws, which is the only way to tell whether a stage is doing what
    you think. Later they become manifest entries, so the record of what was
    cut off a page survives past the run that cut it.
    """

    kind: str
    """What was found: gutter, speck, figure, running-head, and so on."""

    shape: Shape
    """Where it was found, in the coordinates of the frame given to the stage."""

    note: str = ""
    """Optional detail, for example a measured angle or a confidence."""


@dataclass
class Frame:
    """One image in flight, with its provenance and its history."""

    image: np.ndarray
    """Greyscale uint8 array, shape (height, width)."""

    provenance: Provenance

    history: list[str] = field(default_factory=list)
    """Names of the stages that have already run on this frame, in order."""

    @property
    def height(self) -> int:
        return int(self.image.shape[0])

    @property
    def width(self) -> int:
        return int(self.image.shape[1])

    def derive(
        self,
        image: np.ndarray,
        *,
        side: str | None = None,
        column: int | None = None,
    ) -> "Frame":
        """Make a new frame from this one, carrying provenance and history.

        Stages that narrow a frame call this rather than building a Frame by
        hand, so nothing can lose track of which page it came off. Passing side
        or column refines the provenance; leaving them out keeps what is there.
        """
        provenance = self.provenance
        if side is not None or column is not None:
            provenance = replace(
                provenance,
                side=side if side is not None else provenance.side,
                column=column if column is not None else provenance.column,
            )
        return Frame(image=image, provenance=provenance, history=list(self.history))
