"""Straighten a page by the variance of its horizontal ink profile.

Rotate the page through a range of candidate angles and, at each one, sum the
ink in every row. When the page is straight the printed lines fall in their own
rows and the gaps between them fall in theirs, so the profile swings hard
between full rows and empty ones and its variance is high. When the page is
tilted each printed line smears across several rows, the swings flatten, and
the variance drops. The best angle is the one that maximises it. Nothing about
this needs to know what a line of type looks like, which is the point: this book
sets two columns, ragged catalogue lists, and a page of verse capitals, and all
of them make rows.

Per page, never per spread. Measured across the 76 sample spreads, the two
halves of one spread differ by a median of 0.43 degrees and by as much as 2.00.
A single rotation for the whole spread would straighten one page and bend the
other by that much.

Measurements behind the constants, over all 152 halves of the sample, and for
SEARCH and CAP over the 555 page frames of all four parts:

    SEARCH. The skew in the sample runs from -1.70 to +1.80 degrees, median
    magnitude 0.55, and only 12 halves of 152 are already straight, so this
    stage earns its cost on 92 percent of the book. The held-out parts go
    further: three consecutive rectos in part 2, p69 to p71, lean +2.75, +2.75
    and +3.15, between neighbours at +2.20 and +2.25. Searching 4.5 either way
    clears the steepest of them by 1.35 degrees and the cap by one coarse step,
    which matters because the fine pass reaches only one coarse step past the
    search: a page leaning further comes back as that edge value, and the edge
    has to be past the cap so it is refused rather than rotated by the wrong
    amount. The coarse pass is 37 rotations rather than 25. SEARCH stays a
    multiple of COARSE, so the wider grid keeps every point the old one had,
    and across all 555 page frames of the four parts the estimate at 4.5 is
    identical to the one at 3.0, apart from the three pages above.

    SCORE_DPI. Scoring is the expensive part, and it does not need the full
    page. Scored at half resolution the chosen angle differs from the full
    resolution answer by at most 0.10 degrees across a dozen halves spanning
    the range, at a third of the time. At a quarter it starts to drift, 0.45
    degrees out on the catalogue page.

    CAP. An estimate past the cap is not taken as a tilted page but as a page
    whose profile has no line structure to find, because a large rotation
    applied to a page that was straight is worse than no correction at all.
    The cap was 2.5, and it refused the three part 2 rectos above, whose
    estimates are right: a 6 degree search returns the same three values, and
    left tilted their lines merge two to four to a band. Before raising it,
    every page frame of the four parts was estimated with a 6 degree search.
    No page lands past 3.15, not even the flattest curves: the title page, the
    openings of both indexes and of In Apocalypsim, and the tailpiece pages all
    come back within 1.85 of straight. On the title page and the opening of
    the Index rerum, the best angle beyond 3.5 still scores 12 and 13 percent
    below the true peak. So the book offers no wrong answer to set the cap
    against, and 4.0 leaves 0.85 degrees over the steepest real tilt.

    DEADBAND. The fine step is 0.05 degrees, so an estimate below that is not
    distinguishable from zero and the rotation is skipped: a resampling pass
    over a 12 megapixel page costs something and buys nothing.

The canvas grows to fit the rotated page rather than holding its size. Rotating
inside the original bounds moves the corners of the content by up to 50 px on
the worst page in the sample, and the outer edges of a recto carry scanner noise
right up to the border, so something would be clipped. I could not separate that
noise from type by measurement, and the cost of growing the canvas is a strip of
white on two corners, so the page grows and nothing is lost.

The scoring mask is thresholded, so it is rotated with nearest-neighbour: there
is nothing to interpolate between black and white and the cheaper filter is the
honest one. The page itself is rotated with a linear filter, because the page is
what OCR eventually reads and nearest-neighbour rotation leaves glyph edges
stepped.
"""

from __future__ import annotations

import cv2
import numpy as np

from recto.frames import Finding, Frame, Line
from recto.pipeline import StageOutput

SEARCH = 4.5
"""Widest angle considered, in degrees either side of straight."""

COARSE = 0.25
"""First pass step, in degrees."""

FINE = 0.05
"""Second pass step, in degrees, over one coarse interval either side."""

CAP = 4.0
"""An estimate beyond this is treated as a failed estimate, not a tilted page."""

DEADBAND = 0.05
"""Below this the page is left alone. Matches FINE: nothing smaller is resolved."""

SCORE_DPI = 150
"""Resolution the angle is scored at."""

INK_BELOW = 200
"""Pixels darker than this count as ink."""

WHITE = 255


def score_mask(image: np.ndarray, dpi: int, score_dpi: int = SCORE_DPI) -> np.ndarray:
    """Binary ink mask, shrunk to the resolution the angle is scored at."""
    ink = (image < INK_BELOW).astype(np.uint8)
    if dpi <= score_dpi:
        return ink

    factor = dpi / score_dpi
    small = cv2.resize(
        ink * 255,
        (max(1, round(ink.shape[1] / factor)), max(1, round(ink.shape[0] / factor))),
        interpolation=cv2.INTER_AREA,
    )
    # INTER_AREA averages, so a shrunk mask comes back grey. Anything with a
    # quarter of its area inked is ink again.
    return (small > 60).astype(np.uint8)


def profile_variance(mask: np.ndarray, angle: float) -> float:
    """How sharply the horizontal ink profile swings at this angle."""
    height, width = mask.shape
    turn = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    turned = cv2.warpAffine(
        mask, turn, (width, height), flags=cv2.INTER_NEAREST, borderValue=0
    )
    return float(turned.sum(axis=1, dtype=np.float64).var())


def estimate_angle(
    mask: np.ndarray,
    *,
    search: float = SEARCH,
    coarse: float = COARSE,
    fine: float = FINE,
) -> float:
    """Best angle for this mask, coarse pass then fine pass around the winner.

    Coarse to fine rather than one fine sweep because the variance curve has a
    single broad maximum: 37 coarse steps land inside the right interval and 11
    fine ones finish the job, against 181 steps for the same answer.
    """
    grid = np.arange(-search, search + 1e-9, coarse)
    best = float(grid[int(np.argmax([profile_variance(mask, a) for a in grid]))])

    around = np.arange(best - coarse, best + coarse + 1e-9, fine)
    return float(around[int(np.argmax([profile_variance(mask, a) for a in around]))])


def rotate(image: np.ndarray, angle: float) -> np.ndarray:
    """Rotate about the centre onto a canvas grown to hold the whole page."""
    height, width = image.shape
    turn = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)

    reach = np.abs(turn[:, :2])
    grown_w = int(height * reach[0, 1] + width * reach[0, 0])
    grown_h = int(height * reach[1, 1] + width * reach[1, 0])
    turn[0, 2] += grown_w / 2 - width / 2
    turn[1, 2] += grown_h / 2 - height / 2

    return cv2.warpAffine(
        image,
        turn,
        (grown_w, grown_h),
        flags=cv2.INTER_LINEAR,
        borderValue=WHITE,
    )


class Deskew:
    """Straighten one page."""

    name = "deskew"

    def __init__(
        self,
        *,
        search: float = SEARCH,
        coarse: float = COARSE,
        fine: float = FINE,
        cap: float = CAP,
        deadband: float = DEADBAND,
        score_dpi: int = SCORE_DPI,
    ) -> None:
        self.search = search
        self.coarse = coarse
        self.fine = fine
        self.cap = cap
        self.deadband = deadband
        self.score_dpi = score_dpi

    def apply(self, frame: Frame) -> StageOutput:
        mask = score_mask(frame.image, frame.provenance.dpi, self.score_dpi)
        angle = estimate_angle(
            mask, search=self.search, coarse=self.coarse, fine=self.fine
        )

        findings = [self._drawn(frame, angle)]

        if abs(angle) > self.cap:
            return StageOutput(
                frames=[frame],
                findings=findings,
                summary=(
                    f"estimate {angle:+.2f} deg is past the "
                    f"{self.cap} deg cap, left as is"
                ),
            )

        if abs(angle) < self.deadband:
            return StageOutput(
                frames=[frame],
                findings=findings,
                summary=f"already straight within {self.deadband} deg, left as is",
            )

        straightened = rotate(frame.image, angle)
        summary = (
            f"rotated {angle:+.2f} deg, "
            f"{frame.width}x{frame.height} to "
            f"{straightened.shape[1]}x{straightened.shape[0]}"
        )
        return StageOutput(
            frames=[frame.derive(straightened)],
            findings=findings,
            summary=summary,
        )

    def _drawn(self, frame: Frame, angle: float) -> Finding:
        """The tilt, as a line through the middle of the page at that angle.

        Against the horizontal edge of the overlay it reads as the amount the
        page is off, which is the one thing worth seeing here: an angle printed
        in a caption tells you nothing about whether it is the right angle.
        """
        half = frame.width // 2
        drop = round(half * np.tan(np.radians(angle)))
        middle = frame.height // 2
        return Finding(
            kind="text-line",
            shape=Line(0, middle + drop, frame.width, middle - drop),
            note=f"{angle:+.2f} deg",
        )
