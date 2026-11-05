"""Write each column image, and one manifest row that says where it came from.

The manifest is the link between an OCR result and the physical book. A
column image alone is a picture of text. With its row, it names the PDF, the
page, the side and the column, and it records what every stage did to get it
there: the crop, the split, the deskew angle, the figures whited out, and the
head, foot and column cuts.

The file is JSON Lines, one row per line, written in reading order: page by
page, the verso before the recto, and the columns left to right. A title block
kept whole above the columns is column 0, so the column index is the reading
order inside a page. A page that drop-blank skipped gets a row too, with no
image, because the book has a page there and the manifest must account for it.
Rows are written when a page is complete, so a later commit can resume a run
by appending.

Each row looks like this, with the stages shortened:

    {"image": "p0009-recto-c1.png", "label": "p0009-recto-c1",
     "source": "part1.pdf", "page": 9, "side": "recto", "column": 0,
     "status": "column", "dpi": 300, "width": 1310, "height": 3650,
     "stages": [{"stage": "crop-border", "frame": "p0009",
                 "summary": "...", "findings": [{"kind": "frame",
                 "box": [74, 6, 5780, 4410], "note": ""}]}, ...]}

The column index is zero-based, as in Provenance, and the page is one-based,
as a PDF viewer shows it. A skipped page has "status": "blank", "image": null,
"column": null, and its ink share in "ink".

Each finding is in the coordinates of the frame that its stage was given,
named in "frame". The rows do not map a column back to pixels of the scan:
that needs every narrowing stage to record its offset and rotation, and was
left out of scope on 5 November 2026.

The findings of despeckle and band-lines are left out, and their summaries are
kept. Despeckle reports up to 300 specks a frame and band-lines about 140 line
boxes a page. Together they would make each row hundreds of times longer, and
the debug overlays already show them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import TracebackType
from typing import Any, TextIO

from recto.frames import Box, Finding, Frame, Provenance
from recto.pipeline import Stage, StageOutput
from recto.pngio import write_png
from recto.stages.blank import DropBlank

DEFAULT_OUT_DIR = Path("out")
"""Where recto run writes, one folder for each PDF. Already in .gitignore."""

MANIFEST_NAME = "manifest.jsonl"

QUIET_STAGES = frozenset({"despeckle", "band-lines"})
"""Stages whose findings stay out of the manifest. See the module docstring."""


@dataclass(frozen=True)
class _Record:
    """What one stage reported about one frame."""

    frame: str
    stage: str
    summary: str
    findings: tuple[Finding, ...]


def _page_label(provenance: Provenance) -> str:
    """Give the label of the page frame that a column frame came from.

    Args:
        provenance: The provenance of a column frame or of a page frame.

    Returns:
        The label without the column part, for example p0009-recto.
    """
    return replace(provenance, column=None).label


def _ancestors(provenance: Provenance) -> list[str]:
    """Give the labels of every frame that a frame was cut from, and its own.

    Args:
        provenance: The provenance of a column frame or of a page frame.

    Returns:
        The labels from the spread down, without repeats: for example
        p0009, p0009-recto, p0009-recto-c1.
    """
    labels: list[str] = []
    for level in (
        replace(provenance, side=None, column=None),
        replace(provenance, column=None),
        provenance,
    ):
        if level.label not in labels:
            labels.append(level.label)
    return labels


def _finding(finding: Finding) -> dict[str, Any]:
    """Convert a finding to a JSON object.

    Args:
        finding: A finding that a stage reported.

    Returns:
        An object with "kind", "note", and either "box" as [x, y, width,
        height] or "line" as [x1, y1, x2, y2].
    """
    shape = finding.shape
    if isinstance(shape, Box):
        where = {"box": [shape.x, shape.y, shape.width, shape.height]}
    else:
        where = {"line": [shape.x1, shape.y1, shape.x2, shape.y2]}
    return {"kind": finding.kind, **where, "note": finding.note}


@dataclass
class ManifestWriter:
    """Write column images and manifest rows, one page at a time.

    It is an Observer, so it sees what each stage reported without changing
    the run. Call page_done after each PDF page with the frames that the
    pipeline returned. Use it as a context manager, so that the manifest file
    is closed if a stage fails.

    Args:
        directory: The folder for the images and the manifest. It is made if
            it does not exist.
        blank: The drop-blank stage of the pipeline, which holds the pages it
            skipped. None if the pipeline has no such stage.
    """

    directory: Path
    blank: DropBlank | None = None
    rows: int = field(default=0, init=False)
    """Rows written so far, images and skipped pages together."""

    images: int = field(default=0, init=False)
    """Column images written so far."""

    _records: list[_Record] = field(default_factory=list, init=False)
    _skips_seen: int = field(default=0, init=False)
    _file: TextIO | None = field(default=None, init=False)

    @property
    def path(self) -> Path:
        """The manifest file."""
        return self.directory / MANIFEST_NAME

    def __enter__(self) -> "ManifestWriter":
        """Open the manifest for writing, and replace an old one.

        Returns:
            This writer.

        Raises:
            OSError: If the folder cannot be made or the file cannot be opened.
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("w", encoding="utf-8", newline="\n")
        if self.blank is not None:
            # Skips from an earlier run of the same stage object are not
            # this run's pages.
            self._skips_seen = len(self.blank.skipped)
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        """Close the manifest. Rows of complete pages stay in it.

        Args:
            kind: The type of the exception that ended the block, or None.
            error: The exception that ended the block, or None.
            trace: Its traceback, or None.
        """
        if self._file is not None:
            self._file.close()
            self._file = None

    def saw(
        self,
        order: int,
        stage: Stage,
        incoming: Frame,
        output: StageOutput,
    ) -> None:
        """Observer hook. Keep what the stage reported about this frame.

        Args:
            order: The position of the stage in the pipeline, from 1.
            stage: The stage that ran.
            incoming: The frame that the stage was given.
            output: What the stage returned.
        """
        findings = () if stage.name in QUIET_STAGES else tuple(output.findings)
        self._records.append(
            _Record(
                frame=incoming.provenance.label,
                stage=stage.name,
                summary=output.summary,
                findings=findings,
            )
        )

    def page_done(self, frames: list[Frame]) -> int:
        """Write the images and the rows for one PDF page.

        Args:
            frames: The frames that the pipeline returned for the page, in
                reading order.

        Returns:
            The number of rows written for the page.

        Raises:
            RuntimeError: If the writer is not open, or an image cannot be
                written.
        """
        if self._file is None:
            raise RuntimeError("ManifestWriter is not open; use it in a with block")

        skips = []
        if self.blank is not None:
            skips = self.blank.skipped[self._skips_seen :]
            self._skips_seen = len(self.blank.skipped)

        # A blank verso must come before the columns of its recto. Every page
        # frame reached drop-blank, so its first record gives its place.
        first_seen: dict[str, int] = {}
        for index, record in enumerate(self._records):
            first_seen.setdefault(record.frame, index)

        units: list[tuple[str, Frame | None, float | None, Provenance]] = []
        for frame in frames:
            page = _page_label(frame.provenance)
            units.append((page, frame, None, frame.provenance))
        for skip in skips:
            units.append((skip.provenance.label, None, skip.ink, skip.provenance))
        units.sort(key=lambda unit: first_seen.get(unit[0], len(self._records)))

        for _, frame, ink, provenance in units:
            row = self._row(provenance, frame, ink)
            if frame is not None:
                write_png(self.directory / row["image"], frame.image)
                self.images += 1
            self._file.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._file.flush()

        self._records.clear()
        self.rows += len(units)
        return len(units)

    def _row(
        self,
        provenance: Provenance,
        frame: Frame | None,
        ink: float | None,
    ) -> dict[str, Any]:
        """Build the manifest row for one column image or one skipped page.

        Args:
            provenance: Where the image or the skipped page came from.
            frame: The column frame, or None for a skipped page.
            ink: The ink share of a skipped page, or None for a column.

        Returns:
            The row as a JSON-ready dict.
        """
        lineage = _ancestors(provenance)
        stages = [
            {
                "stage": record.stage,
                "frame": record.frame,
                "summary": record.summary,
                "findings": [_finding(finding) for finding in record.findings],
            }
            for record in self._records
            if record.frame in lineage
        ]
        row: dict[str, Any] = {
            "image": f"{provenance.label}.png" if frame is not None else None,
            "label": provenance.label,
            "source": str(provenance.source),
            "page": provenance.page_number,
            "side": provenance.side,
            "column": provenance.column,
            "status": "column" if frame is not None else "blank",
            "dpi": provenance.dpi,
        }
        if frame is not None:
            row["width"] = frame.width
            row["height"] = frame.height
        else:
            row["ink"] = round(ink, 6) if ink is not None else None
        row["stages"] = stages
        return row
