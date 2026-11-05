"""Compare Tesseract word confidence on raw spreads and on recto's columns.

This is a smoke check, not an accuracy measure. Tesseract gives each word a
confidence from 0 to 100. If the column images give a higher mean confidence
than the raw spreads, the cleaning helps Tesseract. A confident word can still
be wrong, and only a hand transcription can measure accuracy.

The raw spread is read with page segmentation mode 3, fully automatic, so
Tesseract can find the columns by itself. The comparison is then fair to the
raw page: it asks whether recto does better than Tesseract's own layout
analysis. Each column image is read with mode 4, one column of text.

Tesseract runs as a separate program, found on PATH, so recto has no new
dependency. Each image goes to it as a PNG file in a temporary folder, because
pngio already writes PNG safely on Windows.
"""

from __future__ import annotations

import csv
import io
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from recto.pngio import write_png

RAW_PSM = 3
"""Fully automatic page segmentation, for the whole spread."""

COLUMN_PSM = 4
"""One column of text of variable sizes, for each column image."""


class TesseractError(RuntimeError):
    """Tesseract is missing, or it failed on an image."""


def find_tesseract() -> str:
    """Find the tesseract program on PATH.

    Returns:
        The full path of the program.

    Raises:
        TesseractError: If tesseract is not on PATH.
    """
    found = shutil.which("tesseract")
    if found is None:
        raise TesseractError(
            "tesseract is not on PATH. Install it, add its folder to PATH, "
            "and open a new terminal."
        )
    return found


def word_confidences(
    image: np.ndarray,
    *,
    tesseract: str,
    lang: str,
    psm: int,
    dpi: int,
    workdir: Path,
) -> list[float]:
    """Read one image with Tesseract and give the confidence of each word.

    Args:
        image: The greyscale image.
        tesseract: The path of the tesseract program.
        lang: The Tesseract language, for example "lat".
        psm: The page segmentation mode.
        dpi: The resolution of the image. Tesseract uses it to scale its
            expectations of letter size.
        workdir: A folder for the temporary PNG file.

    Returns:
        One confidence from 0 to 100 for each word that Tesseract read.

    Raises:
        TesseractError: If Tesseract fails, for example because the language
            data is not installed.
    """
    path = workdir / "image.png"
    write_png(path, image)
    command = [tesseract, str(path), "stdout", "-l", lang]
    command += ["--psm", str(psm), "--dpi", str(dpi), "tsv"]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or f"exit status {result.returncode}"
        raise TesseractError(message)

    # Level 5 rows are words. Rows with conf -1 are layout rows without text.
    reader = csv.DictReader(
        io.StringIO(result.stdout), delimiter="\t", quoting=csv.QUOTE_NONE
    )
    # Without its tsv config file, Tesseract prints plain text and still exits
    # with 0. Counting that as no words would hide the fault.
    if reader.fieldnames is None or "conf" not in reader.fieldnames:
        raise TesseractError(
            "tesseract did not give TSV output; check that its tessdata "
            "folder holds configs/tsv"
        )
    confidences = []
    for row in reader:
        if row.get("level") != "5" or not (row.get("text") or "").strip():
            continue
        conf = float(row["conf"])
        if conf >= 0:
            confidences.append(conf)
    return confidences


@dataclass
class Score:
    """Word confidences of one page, read raw and read as columns."""

    raw: list[float] = field(default_factory=list)
    columns: list[float] = field(default_factory=list)


def mean(values: list[float]) -> float | None:
    """Give the mean of a list.

    Args:
        values: The numbers.

    Returns:
        The mean, or None if the list is empty.
    """
    return sum(values) / len(values) if values else None
