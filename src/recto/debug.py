"""Drawing what each stage found, on the frame it found it in.

This is the most important non-processing code in the project. A vision
pipeline you cannot see into is a guessing game: when the output is wrong, the
question is which of eleven stages made it wrong, and no amount of reading the
code answers that as fast as looking at one picture per stage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from recto.frames import Box, Finding, Frame, Line
from recto.pipeline import Stage, StageOutput
from recto.pngio import write_png

DEFAULT_DEBUG_DIR = Path("work/debug")

# Overlays get looked at, not processed, so they are written small. A full
# resolution overlay is 26 MB, and eleven of them per page would make the debug
# folder larger than the book.
DEFAULT_MAX_WIDTH = 2000

# OpenCV takes colours as BGR, not RGB. Kinds not listed here fall back to
# magenta, which is loud enough that an unlabelled finding is obvious.
_COLOURS: dict[str, tuple[int, int, int]] = {
    "bounds": (200, 200, 200),
    "ink": (0, 200, 255),
    "gutter": (0, 0, 255),
    "frame": (0, 165, 255),
    "speck": (255, 0, 255),
    "figure": (0, 165, 255),
    "text-line": (255, 160, 0),
    "running-head": (0, 255, 255),
    "catchword": (0, 255, 255),
    "column": (0, 255, 0),
}
_FALLBACK_COLOUR = (255, 0, 255)

_CAPTION_HEIGHT = 30
_CAPTION_BACKGROUND = (28, 22, 26)
_CAPTION_TEXT = (238, 238, 238)


def draw_overlay(
    image: np.ndarray,
    findings: list[Finding],
    *,
    caption: str | None = None,
    max_width: int = DEFAULT_MAX_WIDTH,
) -> np.ndarray:
    """Draw findings over a greyscale image and return a viewable BGR copy.

    Shapes are drawn at full resolution and the result is downscaled after, so
    line weight is picked relative to the real image and still survives the
    reduction. The caption goes on afterwards, at the size it will be read at.
    """
    canvas = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    # A 2 pixel line is invisible on a 6000 pixel wide page, and unreadable
    # once the overlay is scaled down. Scale the weight with the image.
    thickness = max(3, canvas.shape[1] // 500)

    for finding in findings:
        colour = _COLOURS.get(finding.kind, _FALLBACK_COLOUR)
        shape = finding.shape

        if isinstance(shape, Box):
            cv2.rectangle(
                canvas,
                (shape.x, shape.y),
                (shape.x + shape.width, shape.y + shape.height),
                colour,
                thickness,
            )
        elif isinstance(shape, Line):
            cv2.line(
                canvas,
                (shape.x1, shape.y1),
                (shape.x2, shape.y2),
                colour,
                thickness,
            )

    if canvas.shape[1] > max_width:
        scale = max_width / canvas.shape[1]
        canvas = cv2.resize(
            canvas,
            (max_width, max(1, round(canvas.shape[0] * scale))),
            interpolation=cv2.INTER_AREA,
        )

    if caption:
        cv2.rectangle(
            canvas, (0, 0), (canvas.shape[1], _CAPTION_HEIGHT), _CAPTION_BACKGROUND, -1
        )
        cv2.putText(
            canvas,
            caption,
            (10, 21),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            _CAPTION_TEXT,
            1,
            cv2.LINE_AA,
        )

    return canvas


@dataclass
class DebugWriter:
    """Writes one overlay per stage application, into a sortable layout.

    Files land at debug/<pdf stem>/<frame label>/NN_<stage>.png, so a directory
    listing for one page reads down the pipeline in order and shows exactly
    where a page stopped looking right.
    """

    root: Path = DEFAULT_DEBUG_DIR
    max_width: int = DEFAULT_MAX_WIDTH
    written: list[Path] = field(default_factory=list)

    def saw(
        self,
        order: int,
        stage: Stage,
        incoming: Frame,
        output: StageOutput,
    ) -> None:
        """Observer hook. Draws the stage's findings on the frame it was given."""
        label = incoming.provenance.label
        directory = self.root / incoming.provenance.source.stem / label
        path = directory / f"{order:02d}_{stage.name}.png"

        caption = (
            f"{order:02d} {stage.name}   {label}   "
            f"{incoming.width}x{incoming.height}   "
            f"{len(output.findings)} finding(s)   "
            f"-> {len(output.frames)} frame(s)"
        )

        overlay = draw_overlay(
            incoming.image,
            output.findings,
            caption=caption,
            max_width=self.max_width,
        )
        write_png(path, overlay)
        self.written.append(path)
