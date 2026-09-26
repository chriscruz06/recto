"""Which stages run, and in what order.

This lives in its own module rather than in stages/__init__.py so that adding
a stage never means editing a file called __init__.py. There is already one of
those at src/recto/__init__.py holding the package version, and two files with
the same name and different jobs is a mistake waiting to happen.
"""

from __future__ import annotations

from recto.pipeline import Stage
from recto.stages.blank import DropBlank
from recto.stages.border import CropBorder
from recto.stages.despeckle import Despeckle
from recto.stages.deskew import Deskew
from recto.stages.figures import MaskFigures
from recto.stages.split import SplitSpread


def default_stages() -> list[Stage]:
    """Build the pipeline as it currently stands.

    CropBorder runs first because everything after it measures ink, and the
    black scanner border is more ink than the text is. Despeckle runs second
    for the same reason: every projection profile from here on is counting ink,
    and a speck is ink. SplitSpread runs third, on the first image clean enough
    for its column profile to mean anything, and is the last stage that sees a
    whole spread. Everything after it works on one page at a time, starting with
    Deskew, which has to run per page because the two halves of one spread are
    tilted by different amounts.

    DropBlank goes in front of Deskew rather than after it. A blank page gives
    the angle search nothing to maximise, and deskew pads the canvas, which
    would dilute the ink ratio the blank check reads.

    MaskFigures runs on the straightened page and before anything that reads
    columns, because a headpiece spans both columns and fills the whitespace
    valley the column split looks for.
    """
    return [
        CropBorder(),
        Despeckle(),
        SplitSpread(),
        DropBlank(),
        Deskew(),
        MaskFigures(),
    ]
