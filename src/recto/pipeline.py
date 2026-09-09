"""The stage protocol and the runner that drives it.

A stage takes one frame and returns zero or more frames, plus whatever it
found in the frame it was given. That signature is deliberately not
image-in-image-out, because most of this pipeline is not: splitting a spread
turns one frame into two, splitting columns turns each of those into two more,
and dropping a blank page turns one into none. Making every stage a one-to-many
function is what lets a single runner handle all three without special cases.

Findings always describe the frame the stage was given, never the frames it
returned. That is what makes the debug overlay meaningful: you see the gutter
drawn on the spread it was found in, not on the halves it produced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from recto.frames import Finding, Frame


@dataclass
class StageOutput:
    """What a stage hands back."""

    frames: list[Frame]
    """Zero or more frames to pass on. Order is reading order."""

    findings: list[Finding] = field(default_factory=list)
    """What the stage located in its input frame."""

    summary: str = ""
    """One line on what the stage did, for the debug caption.

    Findings are often capped for legibility, so the number drawn is not the
    number found. This is where a stage says what actually happened: how many
    components it removed, what angle it corrected, how many columns it saw.
    """


class Stage(Protocol):
    """A single step in the pipeline.

    Stages are objects rather than plain functions so that their tuning
    constants can be constructor arguments. That keeps the call signature free
    of a parameter bag, and means the move to profile files later changes only
    how stages are built, not how they are run.
    """

    name: str

    def apply(self, frame: Frame) -> StageOutput: ...


class StageError(RuntimeError):
    """A stage failed on a specific frame.

    Raised in place of whatever the stage raised, with the stage name and the
    frame label attached, because "list index out of range" on page 412 of a
    900 page run is not a useful thing to read.
    """


@dataclass
class Pipeline:
    """Runs stages in order over a frame, fanning out as stages split it."""

    stages: list[Stage]

    def run(self, frame: Frame, observer: "Observer | None" = None) -> list[Frame]:
        """Run every stage in order, returning whatever frames survive.

        The result can be empty. A page the blank detector drops produces no
        frames at all, and that is a correct outcome rather than a failure.
        """
        frames = [frame]

        for order, stage in enumerate(self.stages, start=1):
            produced: list[Frame] = []

            for incoming in frames:
                try:
                    output = stage.apply(incoming)
                except Exception as exc:
                    raise StageError(
                        f"stage {stage.name!r} failed on {incoming.provenance.label}: {exc}"
                    ) from exc

                if observer is not None:
                    observer.saw(order, stage, incoming, output)

                for outgoing in output.frames:
                    outgoing.history.append(stage.name)
                produced.extend(output.frames)

            frames = produced

        return frames


class Observer(Protocol):
    """Watches every stage application without affecting the result.

    The debug writer is the only implementation for now. Keeping it a protocol
    rather than wiring the writer straight into Pipeline means a normal run
    carries no debug machinery at all, and a future progress bar or profiler
    can hook the same point.
    """

    def saw(
        self,
        order: int,
        stage: Stage,
        incoming: Frame,
        output: StageOutput,
    ) -> None: ...
