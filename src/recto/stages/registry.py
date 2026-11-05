"""Which stages run, and in what order.

This lives in its own module rather than in stages/__init__.py so that adding
a stage never means editing a file called __init__.py. There is already one of
those at src/recto/__init__.py holding the package version, and two files with
the same name and different jobs is a mistake waiting to happen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from recto.pipeline import Stage
from recto.stages.bands import BandLines, Tuning
from recto.stages.blank import DropBlank
from recto.stages.columns import SplitColumns
from recto.stages.border import CropBorder
from recto.stages.despeckle import Despeckle
from recto.stages.deskew import Deskew
from recto.stages.figures import MaskFigures
from recto.stages.furniture import StripFoot, StripHead
from recto.stages.split import SplitSpread

if TYPE_CHECKING:
    # Only for the annotation: config imports the stage modules, so an import
    # at run time would go in a circle.
    from recto.config import Profile


def default_stages(profile: Profile | None = None) -> list[Stage]:
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

    SplitColumns runs last. It must get a page with no head and no foot row,
    because those lines go across both columns.

    Args:
        profile: Values that change the defaults, from config.load_profile.
            Without one, every stage keeps its defaults, which are the values
            measured on the Jammy edition.

    Returns:
        The stages, in the order they run.
    """

    def own(name: str) -> dict:
        """Give the values the profile sets in one section.

        Args:
            name: The section name.

        Returns:
            A new dict, empty if there is no profile or it sets nothing there.
        """
        return profile.section(name) if profile is not None else {}

    tuning = Tuning(**own("bands"))
    whole = own("whole")
    tallest = {key: value for key, value in whole.items() if key == "tallest"}
    return [
        CropBorder(**own("crop-border")),
        Despeckle(**own("despeckle")),
        SplitSpread(**own("split-spread")),
        DropBlank(**own("drop-blank")),
        Deskew(**own("deskew")),
        MaskFigures(**own("mask-figures")),
        StripHead(**own("strip-head"), tuning=tuning, **tallest),
        StripFoot(**own("strip-foot"), tuning=tuning, **tallest),
        BandLines(tuning),
        SplitColumns(**own("split-columns"), tuning=tuning, **whole),
    ]
