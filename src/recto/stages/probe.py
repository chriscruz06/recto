"""A stage that changes nothing and measures two things.

This exists to prove the wiring: registry, runner, observer and overlay writer
all exercised end to end before a single real transform is written. It also
answers a question worth having an answer to before commit 04, which is how
much of each scan is page and how much is black scanner frame.

Expect to delete this once the pipeline has real stages in it.
"""

from __future__ import annotations

import numpy as np

from recto.frames import Box, Finding, Frame
from recto.pipeline import StageOutput

# Anything darker than this counts as ink. The scans are bitonal, so almost
# every pixel is 0 or 255 and the exact cut hardly matters, but rendering
# introduces a few intermediate values at glyph edges.
INK_BELOW = 200


class Probe:
    """Passes the frame through untouched, reporting its extent."""

    name = "probe"

    def __init__(self, ink_below: int = INK_BELOW) -> None:
        self.ink_below = ink_below

    def apply(self, frame: Frame) -> StageOutput:
        findings = [
            Finding(
                kind="bounds",
                shape=Box(0, 0, frame.width, frame.height),
                note=f"{frame.width}x{frame.height}",
            )
        ]

        ink = frame.image < self.ink_below
        rows = np.flatnonzero(ink.any(axis=1))
        columns = np.flatnonzero(ink.any(axis=0))

        # A page with no ink at all is possible: the sample has a blank verso.
        if rows.size and columns.size:
            top, bottom = int(rows[0]), int(rows[-1])
            left, right = int(columns[0]), int(columns[-1])
            coverage = float(ink.mean())
            findings.append(
                Finding(
                    kind="ink",
                    shape=Box(left, top, right - left + 1, bottom - top + 1),
                    note=f"{coverage:.1%} of pixels are ink",
                )
            )

        return StageOutput(frames=[frame], findings=findings)
