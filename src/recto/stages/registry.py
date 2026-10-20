"""Which stages run, and in what order.

This lives in its own module rather than in stages/__init__.py so that adding
a stage never means editing a file called __init__.py. There is already one of
those at src/recto/__init__.py holding the package version, and two files with
the same name and different jobs is a mistake waiting to happen.
"""

from __future__ import annotations

from recto.pipeline import Stage
from recto.stages.bands import BandLines
from recto.stages.blank import DropBlank
from recto.stages.border import CropBorder
from recto.stages.despeckle import Despeckle
from recto.stages.deskew import Deskew
from recto.stages.figures import MaskFigures
from recto.stages.furniture import StripFoot, StripHead
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

    StripHead runs on the masked page, because it finds the head in the line
    bands and a woodcut left in place would be banded as a block of very dark
    lines. It calls band_lines itself.

    StripFoot runs after StripHead. It reads the same line bands, and it must
    not mistake the running head for a line of text.

    BandLines only measures. It draws the lines of type that the column split
    will get, and it passes the page on unchanged.
    """
    return [
        CropBorder(),
        Despeckle(),
        SplitSpread(),
        DropBlank(),
        Deskew(),
        MaskFigures(),
        StripHead(),
        StripFoot(),
        BandLines(),
    ]
