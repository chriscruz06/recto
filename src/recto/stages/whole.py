"""Keep each letter whole when a cut passes through it.

Three stages cut a page and white one side of the cut: strip-head whites all
rows above its cut, strip-foot all rows under its cut, and split-columns the gap
between the columns. A straight cut can go through a letter. Then one part of
the letter goes and the other stays. On the last line of a page this takes the
tail off a p or a q, and OCR can read the rest as o or a. This module finds the
letters that a cut touches, and gives each one whole to the side that it reaches
further into.

The letters are the components of bands.letter_ink, the same mask that the
three stages use to find lines.

Why reach and not ink. The foot cut can be near the baseline of the last line.
Then most of the ink of a p is under the cut, but its bowl reaches 25 px above
the cut and its tail 12 px under it. A capital of the foot row that rises over
the cut reaches about 6 px above it and 30 px under it. A rule that counted ink
removed a whole word, cap., on part 2 p35 recto, and the p of pro on part 3 p6
verso. A rule that leaned to keeping did not help: where the cut is near the
foot row, a capital of a catchword reaches 10 to 15 px over it and 20 px under
it, and whole catchwords stayed.

What moves. Most letters a cut touches are under 60 px tall. Over that are
pieces that are not one letter: words fused to the line under them, the
speckled strip at the edge of the leaf, strokes, and woodcut curves. Moved
whole, a fused piece takes text with it. The two fused lines seen measure 74
to 77 px: cap. with the direction line under it, 74; pro with the catchword
fectu, 75; 303 with Veritas, 76. Single fused words, such as sumam and esse,
measure 61 to 69 px. TALLEST is 60, so none of these moves, and they are cut
as before.

At the column gap, pieces of the printed rule touch the gap too. They are thin
and upright. 222 thin upright pieces touch the gap on the four parts, and of the
48 sampled and examined, 47 were the rule and one was a bracket. They stay as the gap
leaves them: UPRIGHT. The gap itself has no fixed width, so the window round it
must hold the widest letter that reaches into it. Of the 472 components that
touch the gap on the four parts, 99 percent are under 190 px wide. Three are
wider, 350 to 870 px, and all three are fused text on speckled pages. WIDEST
is 300 px, so those three stay as the gap leaves them.

Measured on all four parts, 555 page frames, against the stages before this
module, as pieces of ink that come back or go:

    No cut row, column cut, title block or frame count changes.

    Head: 240 pieces on 127 frames come back, mostly the tops of first line
    letters, and 142 pieces on 91 frames go, mostly the descenders of the
    head and the tails of its folio digits.

    Foot: 1,686 pieces on 471 frames come back, the tails of the last line,
    and 810 pieces on 284 frames go, the tops of the foot row. Inside the
    columns of the foot row, the top of the foot row decides, and not the
    cut, which can go through a catchword.

    Columns: 506 pieces come back: letters at the end of a column line,
    hyphens, and letters on the few lines that the cut crosses, which the gap
    whited out before. 8 pieces go, on speckled pages. A column frame grows
    by a few px to hold a letter on 71 frames.

Known behaviour. A word fused to the line under it, and a fused word over
60 px, are cut as before. The boundary between a title block and the columns
is not covered. On part 2 p66 recto the catchword est sits between the last
line and the foot row that strip-foot finds, so it stays, as it did before.

The three stages cost about 0.25 s more a page.
"""

from __future__ import annotations

import cv2
import numpy as np

TALLEST = 60
"""Tallest component, in px at 300 dpi, that a cut keeps whole. The two fused
lines seen measure 74 px and up."""

WIDEST = 300
"""How far, in px at 300 dpi, the column gap's window reaches on each side.
99 percent of the letters that touch the gap are under 190 px wide."""

UPRIGHT = 2.0
"""At the column gap, a component this many times taller than wide is a piece
of the rule, and is left as the cut leaves it."""

REFERENCE_DPI = 300
"""The resolution TALLEST and WIDEST are measured at."""


def whole_letters(
    letters: np.ndarray,
    offset: np.ndarray,
    whited: np.ndarray,
    dpi: int,
    *,
    tallest: int = TALLEST,
    upright: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Find the letters that a cut touches, and the side that each one goes to.

    The caller can give a window of the page and not the whole page, because a
    letter that moves is small. A component that touches the edge of the
    window can go on outside it, so it does not move.

    Args:
        letters: Letter ink mask of the image, from bands.letter_ink.
        offset: For each pixel, its distance in px past the cut. It is less
            than zero on the first side of the cut.
        whited: True for each pixel that the cut makes white. Only letters
            with ink here move.
        dpi: Resolution of the image.
        tallest: Tallest component, in px at REFERENCE_DPI, that moves.
        upright: If given, a component this many times taller than wide does
            not move.

    Returns:
        Two masks of the same shape as letters. The first holds the ink of the
        letters that go whole to the first side, and the second the ink of the
        letters that go whole to the other side. A letter that reaches the same
        distance into both sides goes to the first side.
    """
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        letters.astype(np.uint8), connectivity=8
    )
    width = stats[:, cv2.CC_STAT_WIDTH]
    height = stats[:, cv2.CC_STAT_HEIGHT]

    moves = height <= max(1, round(tallest * dpi / REFERENCE_DPI))
    if upright is not None:
        moves &= height < upright * width
    left, top = stats[:, cv2.CC_STAT_LEFT], stats[:, cv2.CC_STAT_TOP]
    rows, cols = letters.shape
    inside = (left > 0) & (top > 0) & (left + width < cols) & (top + height < rows)
    moves &= inside
    touched = np.zeros(count, dtype=bool)
    touched[np.unique(labels[whited & letters])] = True
    moves &= touched
    moves[0] = False

    # Only the pixels of letters that can move are read, because a page holds
    # some thousands of letters and a cut touches a few hundred of them.
    ink = moves[labels]
    first_reach = np.full(count, -np.inf)
    second_reach = np.full(count, -np.inf)
    np.maximum.at(first_reach, labels[ink], -offset[ink])
    np.maximum.at(second_reach, labels[ink], offset[ink])

    to_first = moves & (first_reach >= second_reach)
    to_second = moves & ~to_first
    return to_first[labels], to_second[labels]
