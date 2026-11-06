"""Strip the running head off the top of a page, and the foot row off the bottom.

Every body page of this book opens with one printed line in large type: the
running head, with the folio number at its outer end. Versos read "D. Alberti
Magni, Ord. Praed.", rectos "in Euang. D.Ioan. Cap. XV.", and the prologues,
In Apocalypsim and the indexes carry heads of their own. OCR would read each one
into the text, once a page, so the head is whited out here, together with
everything above it.

The head is found in the line bands, from band_lines, never by a gap alone. On
the left of p18 recto the first band is a stroke along the top edge of the leaf,
219 px tall, and a rule that took everything above the first wide gap would
take the stroke and leave the head behind. What marks the head is three things
together.

    It is tall. A body line bands at 21 to 27 px, 5th to 95th percentile, on
    the body pages of part 1, and a head at 45 px or more: 111 px at the
    median, over the 1,067 halves of the four parts where one was found.
    HEAD_MIN sits between the two.

    It is on top. No body line sits above it. One stray band is allowed,
    because a row of specks bands like a short line, as on the left of part 2
    p24 recto; two are a paragraph.

    Body follows. Under the head, within GAP_MAX, is a band the height of a
    body line, LINE_MIN to LINE_MAX. That is what keeps the title pages: BEATI
    on page 2 is tall and on top, but what follows it is more display type.
    The gap measures 22 to 87 px on the body pages of part 1, 39 at the
    median, and is under 80 px for 99 percent of heads in all four parts.

The head is one line across the whole page, but it is banded in two halves, and
each half sees only part of it. So it is enough for one half to pass all three
tests, as long as the other half agrees: either it has a tall band at the same
rows, or it has no band at all that high. The second case is the chapter
opening, where one half holds a rule and CAPVT under the head, and the head's
own end in that half is too short for banding to keep. A half that has an
ordinary line beside the head, as on the privilege on p4 verso, disagrees, and
nothing is stripped. Where both halves pass at different heights, the higher is
the head: the lower is a CAPVT heading on four chapter openings, and a large
index letter Q on part 3 p53 verso.

Banding sometimes cuts the head into pieces: the tops of its capitals, the rest,
and the tails of its descenders. Pieces within PIECE of each other are one head
if they are slivers under LINE_MIN, or taller than every piece before them,
which is the body of the head under its capital tops. On the left of p18 recto
the head is three bands, 287 to 338, 352 to 407 and 428 to 444, and the first
body line starts at 472. A band that is neither, like the 42 px first line
22 px under the head on the right of p54 verso, ends the head.

The cut is one row for the whole page, halfway between the head's last band and
the band under it, taken in whichever half gives the higher row. Per page,
because in 62 of 555 page frames one half bands the head and the first body
line as one band, 273 to 444 on the left of p28 verso, while the other half
keeps them apart. The half that keeps them apart puts the cut above the first
line in both. Everything above the cut is whited out across the full width:
the head, the folio, and whatever scanner noise sat over them. A letter that
the cut crosses is kept or removed whole, by stages/whole.py (commit 17a).

On three In Apocalypsim rectos of part 4, p4, p12 and p22, both halves band
the head and the first body line as one band. A cut under that band whites out
the first line. Over the 539 frames with a head, the shorter of the two head
spans is at most 140 px, on part 2 p53 verso, where a ring over the O of Ord.
reaches high. On the three pages it is 159 to 164 px. Thus at HEAD_TALL in
both halves the cut goes up: to the row with the least letter ink from one
pitch to LINE_MIN above the bottom of the band. On all three pages that row is
in the white between the head and the first line (commit 17b).

Measured on all four parts, 555 page frames, every one looked at:

    part 1 finds a head on all 130 body pages and on the ten front matter
    pages that carry one, pages 5 to 10 with p8 recto, and on none of the
    eight that do not: the catalogue, the title page, the privilege, and the
    openings on pages 4, 8 and 11. The held-out parts find one on 399 of 407.
    Of the eight without, six carry no head: three INDEX openings under a
    headpiece, and three In Apocalypsim rectos with a folio and nothing else
    (part 3 p56, p61, p63 and p65 recto; part 4 p71 and p75 recto). Those
    three folios stay on the page. The other two are misses: on part 3 p51
    recto and p57 verso the index's head sits over a large index letter or a
    book name, which is not a body line. Index pages are outside Super
    Iohannem, so they are left.

    On part 3 p37 recto, the Index rerum opening, a fleuron band left by
    mask-figures is taken as the head. The cut falls above it, so only the
    noise over the fleurons goes.

Moving each constant one way and then the other, the cut changes on: HEAD_MIN
at 30, two front matter pages, and at 50, fourteen pages, mostly index pages,
whose heads are set smaller and band at 45 to 50 px; LINE_MIN at 15 or 21, two
or three pages; LINE_MAX from 30 to 40, none; GAP_MAX at 70, four pages, and at
60, thirty-one; PIECE at 20 or 40, p18 recto or two index pages.

The foot row (commit 15). Under the last line of a body page, the printer sets
one more row. On a signed recto it holds the direction line "D. Alberti Magni,
in Euang. D.Ioan." at the left, the signature, such as C 3, in the middle, and
the catchword at the right. A verso holds the catchword only. The catchword
repeats the first word of the next page. If OCR reads it, the translation gets
that word two times, and no later step finds the error. So the stage removes
the row, and all ink under it. A letter that the cut crosses stays or goes
whole, by stages/whole.py (commit 17a).

The foot row starts away from the left edge of its column. A body line starts
at the column edge, except the last line of a paragraph and an indented first
line. Thus the stage examines the right half of the text block from the bottom
up. A band is text when letter ink covers START_INK of the first START px of
its column. The foot row is the first band in the run of non-text bands at the
bottom. The column edge is the median left edge of bands wider than
COLUMN_WIDE, which only full lines are.

A band in that run is the foot row only if no text band of the left half is
fully below it. This condition rejects the last lines of a chapter that ends
early in the right column. On those pages the left column runs on, and the
foot row is the band level with its last line. A horizontal cut cannot remove
that row without the last line of the left column. On such a page the stage
uses its fallback, below.

The cut is halfway between the foot row and the lowest band above it. But the
cut stays at least LINE_DEPTH under the top of each band that starts more than
ABOVE over the foot row. Some last lines band together with the white under
them, and a midpoint cut can then go into their descenders.

Measured on all four parts, 555 page frames, every cut looked at:

    The stage finds a foot row on 528 frames. In part 1 the cut is above all
    ten foot rows that were labelled by eye in commit 13. It is also above the
    blot on p21 recto and the library stamp on p31 recto, so they go too.

    The 27 frames without a cut are front matter, index ends, blank ends, the
    FINIS page, and chapter ends where the left column runs on. The fallback
    works on these 27 frames only.

    The foot row sits 0 to 71 px under the band above it, 24 at the median.

The fallback cuts each column by itself. It looks for two things.

A catchword in the right column. Here the bands cannot be used: on some
pages the foot row is too far from a full line, and banding drops it as noise,
and on others the descenders of the last line touch it, and it bands with that
line. So the letters under the last full line of the right column are grouped
into lines by their centres. The foot line is the lowest line that is not a
text line, ends within FLUSH of the right edge of the column, and holds
LETTERS letters at least LINE_MIN tall. A catchword is set flush right. A
body line starts at the column edge, and the centred last lines of a chapter
end far from the right edge. A component more than UPRIGHT times taller than
wide is a piece of a rule and does not count as a letter. Everything in the
right column from the cut down goes, with the signature on the same row.

A direction line at the foot of the left column, such as "D. Alb. Mag. in
Apocalypsim." It is the lowest band of the left half, at least half a full
line wide, starts INDENT or more in from the column edge, and ends SHORT or
more short of the right edge. A paragraph's first line is indented but runs to
the right edge, and its last line starts at the edge. Everything in the left
column from its cut down goes.

Measured on the 27 frames, every result looked at:

    The fallback removes 18 catchwords and 7 direction lines on 19 frames.
    Ten catchwords are on the chapter ends of parts 2 and 4, among them CAPVT,
    VISIO, Sicut and Et. Eight are on index and front matter pages, such as
    INDEX, PROLOGI and Iacob. The direction lines are on part 1 p55 recto, part
    2 p21 recto, and part 4 p8, p36, p48, p55 and p71 recto. No text line goes:
    the centred last lines of the chapters, such as "tute." on part 4 p12
    recto, and the last line over a merged catchword, such as "21. & 19." on
    part 2 p48 recto, stay.

    Run over all four parts, 1,105 column images, only the columns of these
    19 frames change. On five of them the column cut moves 1 to 23 px, because
    the cleared ink under the text changes the best cut. The cut stays in the
    white of the gap.

    Known: the signature P 3 on part 2 p21 recto stays, because that page has
    no catchword to find it by.

    The catchwords end 15 px inside to 32 px outside the right edge of their
    column. The direction lines start 79 to 137 px in from the column edge and
    end 112 to 194 px short of the right edge.

Moving each fallback constant one way and then the other, on the 27 frames:
FLUSH from 40 to 90 changes nothing. At 20 or 30 one cut moves 5 px. At 150
the signature on part 2 p21 recto is found, but a speck line below Tauri on
part 3 p54 verso is taken, and Tauri stays. LETTERS at 1 counts specks:
the cut goes under the real catchword on four frames, it moves 224 px up on
part 3 p63 verso, and cuts appear on the title page and on part 1 p4 verso.
At 3, Et on part 2 p70 verso stays. INDENT
from 30 to 70 and SHORT from 30 to 100 change nothing. INDENT at 80 keeps the
direction line of part 4 p8 recto, and SHORT at 120 that of part 2 p21 recto.
UPRIGHT at 1.5 keeps Et on part 2 p70 verso, and at 3.0 changes nothing.

Moving each constant one way and then the other: COLUMN_WIDE from 500 to 700
changes no cut. START at 200 or 400 changes four or two frames. START_INK at
0.03 or 0.08 changes three or four. ABOVE at 10 or 30 changes one or three.
LINE_DEPTH at 30 or 40 moves the cut by 1 to 5 px on many pages, but the cut
never passes the edge of a band.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import cv2
import numpy as np

from recto.frames import Box, Finding, Frame
from recto.pipeline import StageOutput
from recto.stages.bands import Band, Tuning, band_lines, letter_ink
from recto.stages.whole import TALLEST, UPRIGHT, whole_letters

HEAD_MIN = 40
"""Shortest band, in px, that can be the running head."""

LINE_MIN = 18
"""Shortest band, in px, that counts as a line of body text."""

LINE_MAX = 35
"""Tallest band, in px, that counts as a line of body text."""

GAP_MAX = 100
"""Furthest the first body line may sit under the head, in px."""

PIECE = 30
"""Pieces of one head sit no further apart than this, in px."""

HEAD_TALL = 150
"""If the head is this tall, in px, in both halves, it holds the first line."""

COLUMN_WIDE = 600
"""A band wider than this, in px, is a full line. Its left edge is the column edge."""

START = 300
"""Width in px, from the column edge, that tells a text line from the foot row."""

START_INK = 0.05
"""Share of letter ink in that width that makes a band a text line."""

LINE_DEPTH = 35
"""The foot cut stays this far, in px, under the top of each line above it."""

ABOVE = 20
"""A band that starts this far, in px, over the foot row is a line above it."""

FLUSH = 60
"""A catchword ends this far, in px, from the right edge of its column or nearer."""

LETTERS = 2
"""A foot line holds at least this many letters as tall as LINE_MIN."""

INDENT = 50
"""A direction line starts at least this far, in px, in from the column edge."""

SHORT = 60
"""A direction line ends at least this far, in px, short of the column's right edge."""

REFERENCE_DPI = 300
"""The resolution every length above is measured at."""

WHITE = 255


@dataclass(frozen=True)
class Head:
    """Where the running head is, and where the page is cut under it."""

    cut: int
    """Rows above this are the head and whatever is over it."""

    halves: tuple[tuple[int, int] | None, tuple[int, int] | None]
    """Top and bottom of the head in each half, or None where it left no band."""


def find_head(
    halves: tuple[list[Band], list[Band]],
    dpi: int,
    *,
    head_min: int = HEAD_MIN,
    line_min: int = LINE_MIN,
    line_max: int = LINE_MAX,
    gap_max: int = GAP_MAX,
    piece: int = PIECE,
    reference_dpi: int = REFERENCE_DPI,
) -> Head | None:
    """The running head in the bands of both halves, or None if there is none."""
    scale = dpi / reference_dpi
    head_min, line_min, line_max, gap_max, piece = (
        max(1, round(v * scale)) for v in (head_min, line_min, line_max, gap_max, piece)
    )

    def is_line(b: Band) -> bool:
        return line_min <= b.height <= line_max

    def on_top(bands: list[Band], i: int) -> bool:
        """At most one body line above band i, not counting pieces just over it."""
        above = [b for b in bands[:i] if bands[i].top - b.bottom > piece]
        return sum(is_line(b) for b in above) < 2

    def extent(bands: list[Band], i: int) -> int:
        """Index of the head's last piece, starting from band i."""
        j, tallest = i, bands[i].height
        while j + 1 < len(bands):
            after = bands[j + 1]
            if after.top - bands[j].bottom > piece:
                break
            if after.height < line_min or after.height > tallest:
                j, tallest = j + 1, max(tallest, after.height)
            else:
                break
        return j

    def passes(bands: list[Band]) -> tuple[int, int] | None:
        """The head in one half, if it is tall, on top, and has body under it."""
        for i, b in enumerate(bands):
            if b.height >= head_min and on_top(bands, i):
                j = extent(bands, i)
                if j + 1 == len(bands):
                    return None
                after = bands[j + 1]
                close = after.top - bands[j].bottom <= gap_max
                return (i, j) if is_line(after) and close else None
        return None

    def beside(bands: list[Band], top: int, bottom: int) -> tuple[int, int] | None:
        """A tall band on top at the head's rows, in the other half."""
        for i, b in enumerate(bands):
            level = b.top < bottom and top < b.bottom
            if b.height >= head_min and level and on_top(bands, i):
                return i, extent(bands, i)
        return None

    found = [passes(bands) for bands in halves]
    rows = [
        (halves[h][f[0]].top, halves[h][f[1]].bottom) if f else None
        for h, f in enumerate(found)
    ]

    if found[0] and found[1]:
        (a_top, a_bottom), (b_top, b_bottom) = rows
        if a_top < b_bottom and b_top < a_bottom:
            pieces = found
        else:
            pieces = _with_other(halves, found, 0 if a_top < b_top else 1, rows, beside)
    elif found[0] or found[1]:
        pieces = _with_other(halves, found, 0 if found[0] else 1, rows, beside)
    else:
        return None
    if pieces is None:
        return None

    cuts, spans = [], []
    for bands, ij in zip(halves, pieces):
        if ij is None:
            spans.append(None)
            continue
        i, j = ij
        if j + 1 < len(bands):
            under = bands[j + 1].top
        else:
            under = bands[j].bottom + 2 * line_max
        cuts.append((bands[j].bottom + under) // 2)
        spans.append((bands[i].top, bands[j].bottom))
    return Head(cut=min(cuts), halves=(spans[0], spans[1]))


def _window(cut: int, height: int, dpi: int, tallest: int) -> tuple[int, int]:
    """Find the rows round a row cut that can hold a letter the cut crosses.

    Args:
        cut: The row of the cut.
        height: Height of the page.
        dpi: Resolution of the page.
        tallest: Tallest letter that moves, in px at REFERENCE_DPI.

    Returns:
        The first row of the window and one past its last row.
    """
    reach = max(1, round(tallest * dpi / REFERENCE_DPI)) + 1
    return max(0, cut - reach), min(height, cut + reach)


def _first_line_gap(
    letters: np.ndarray, bottom: int, dpi: int, pitch: int, line_min: int
) -> int:
    """Find the row between the head and the first body line, in one joined band.

    The first line is the last line of the band, so the search runs from one
    line pitch to line_min above the bottom of the band.

    Args:
        letters: Letter ink mask of the page.
        bottom: One past the last row of the band.
        dpi: Resolution of the page.
        pitch: Body line pitch, in px at REFERENCE_DPI.
        line_min: Shortest body line, in px at REFERENCE_DPI.

    Returns:
        The row with the least letter ink. If more rows have that ink, the
        middle of the first run of them.
    """
    scale = dpi / REFERENCE_DPI
    top = max(0, bottom - max(1, round(pitch * scale)))
    end = max(top + 1, bottom - max(1, round(line_min * scale)))
    ink = letters[top:end].sum(axis=1)
    first = last = int(np.argmin(ink))
    while last + 1 < ink.size and ink[last + 1] == ink[first]:
        last += 1
    return top + (first + last) // 2


def _with_other(halves, found, h, rows, beside):
    """The head found in half h, checked against the other half."""
    top, bottom = rows[h]
    other = halves[1 - h]
    if any(b.top < bottom for b in other):
        match = beside(other, top, bottom)
        if match is None:
            return None
    else:
        match = None
    return [found[0], match] if h == 0 else [match, found[1]]


class StripHead:
    """White out the running head, the folio, and everything above them."""

    name = "strip-head"

    def __init__(
        self,
        *,
        head_min: int = HEAD_MIN,
        line_min: int = LINE_MIN,
        line_max: int = LINE_MAX,
        gap_max: int = GAP_MAX,
        piece: int = PIECE,
        head_tall: int = HEAD_TALL,
        tuning: Tuning = Tuning(),
        tallest: int = TALLEST,
    ) -> None:
        """Keep the constants for find_head and the cut.

        Args:
            head_min: Shortest band, in px, that can be the head.
            line_min: Shortest band, in px, that is a body line.
            line_max: Tallest band, in px, that is a body line.
            gap_max: Furthest the first body line sits under the head, in px.
            piece: Furthest apart, in px, two pieces of one head sit.
            head_tall: Head height, in px, in both halves, that holds the
                first line.
            tuning: The constants for band_lines.
            tallest: Tallest letter, in px, that the cut keeps whole.
        """
        self.head_min = head_min
        self.line_min = line_min
        self.line_max = line_max
        self.gap_max = gap_max
        self.piece = piece
        self.head_tall = head_tall
        self.tuning = tuning
        self.tallest = tallest

    def apply(self, frame: Frame) -> StageOutput:
        halves = band_lines(frame.image, frame.provenance.dpi, self.tuning)
        head = find_head(
            halves,
            frame.provenance.dpi,
            head_min=self.head_min,
            line_min=self.line_min,
            line_max=self.line_max,
            gap_max=self.gap_max,
            piece=self.piece,
        )
        if head is None:
            return StageOutput(
                frames=[frame], summary="no running head found, left as is"
            )

        tuning = self.tuning
        scale = frame.provenance.dpi / REFERENCE_DPI
        letters = letter_ink(
            frame.image,
            area=max(1, round(tuning.letter_area * scale**2)),
            stroke_height=2 * max(1, round(tuning.pitch * scale)),
            stroke_aspect=tuning.stroke_aspect,
        )

        # When both halves band the head and the first body line together, the
        # cut under that band would white out the first line. Then the cut goes
        # up to the gap between the head and the line.
        tall = max(1, round(self.head_tall * scale))
        joined = all(span and span[1] - span[0] >= tall for span in head.halves)
        if joined:
            bottom = max(span[1] for span in head.halves)
            gap = _first_line_gap(
                letters, bottom, frame.provenance.dpi, tuning.pitch, self.line_min
            )
            head = replace(head, cut=gap)

        # The head cut can go through the ascenders of the first body line
        # and the descenders of the head. Each such letter is kept or removed
        # whole, by the side of the cut it reaches further into.
        a, b = _window(head.cut, frame.height, frame.provenance.dpi, self.tallest)
        rows = head.cut - 0.5 - np.arange(a, b, dtype=float)[:, None]
        offset = np.broadcast_to(rows, (b - a, frame.width))
        kept, gone = whole_letters(
            letters[a:b],
            offset,
            offset > 0,
            frame.provenance.dpi,
            tallest=self.tallest,
        )

        stripped = frame.image.copy()
        stripped[: head.cut] = WHITE
        window = stripped[a:b]
        window[kept] = frame.image[a:b][kept]
        window[gone] = WHITE

        findings = [
            Finding(
                "running-head",
                Box(0, 0, frame.width, head.cut),
                note=f"cut at {head.cut}",
            )
        ]
        for bands, span in zip(halves, head.halves):
            if span is None:
                continue
            top, bottom = span
            pieces = [b for b in bands if b.top < bottom and top < b.bottom]
            if joined:
                # Draw the head only, and not the first line that it holds.
                bottom = head.cut
            left = min(b.left for b in pieces)
            right = max(b.right for b in pieces)
            findings.append(
                Finding("text-line", Box(left, top, right - left, bottom - top))
            )

        sides = "both halves" if all(head.halves) else "one half"
        moved = ", cut moved up over the first line" if joined else ""
        return StageOutput(
            frames=[frame.derive(stripped)],
            findings=findings,
            summary=(
                f"running head stripped, rows 0 to {head.cut}, "
                f"banded in {sides}{moved}"
            ),
        )


def find_foot(
    halves: tuple[list[Band], list[Band]],
    letters: np.ndarray,
    dpi: int,
    *,
    column_wide: int = COLUMN_WIDE,
    start: int = START,
    start_ink: float = START_INK,
    line_depth: int = LINE_DEPTH,
    above: int = ABOVE,
    reference_dpi: int = REFERENCE_DPI,
) -> tuple[int, Band] | None:
    """Find the foot row and the row to cut the page at.

    Args:
        halves: Line bands of the left and right half, from band_lines.
        letters: Letter ink mask of the same page, from letter_ink.
        dpi: Resolution of the page.
        column_wide: Width in px at REFERENCE_DPI of a full line.
        start: Width in px at REFERENCE_DPI to examine from the column edge.
        start_ink: Share of letter ink that makes a band a text line.
        line_depth: Clearance in px at REFERENCE_DPI under each line top.
        above: Distance in px at REFERENCE_DPI that makes a band a line above.
        reference_dpi: Resolution the px values are given at.

    Returns:
        The cut row and the foot row band, or None if the page has no foot row
        that a horizontal cut can remove.
    """
    scale = dpi / reference_dpi
    column_wide, start, line_depth, above = (
        max(1, round(v * scale)) for v in (column_wide, start, line_depth, above)
    )

    def column_edge(bands: list[Band]) -> int | None:
        edges = [b.left for b in bands if b.width > column_wide]
        return int(np.median(edges)) if edges else None

    def is_text(b: Band, edge: int) -> bool:
        window = letters[b.top : b.bottom, edge : edge + start]
        return window.size > 0 and float(window.mean()) >= start_ink

    left, right = halves
    left_edge, right_edge = column_edge(left), column_edge(right)
    if right_edge is None:
        return None

    first = len(right)
    while first > 0 and not is_text(right[first - 1], right_edge):
        first -= 1

    text_left = [b for b in left if left_edge is not None and is_text(b, left_edge)]
    for foot in right[first:]:
        if any(b.top >= foot.bottom for b in text_left):
            continue
        bottoms = [b.bottom for bands in halves for b in bands if b.bottom <= foot.top]
        if not bottoms:
            return None
        cut = (max(bottoms) + foot.top) // 2
        floors = [
            b.top + line_depth
            for bands in halves
            for b in bands
            if b.top < foot.top - above
        ]
        return min(foot.top, max([cut, *floors])), foot
    return None


@dataclass(frozen=True)
class Region:
    """Rows from a cut row to the foot of the page, between two columns of px."""

    cut: int
    left: int
    right: int


def _edges(bands: list[Band], column_wide: int) -> tuple[int, int] | None:
    """Give the left and right edge of a column from its full lines.

    Args:
        bands: Line bands of one half.
        column_wide: Width in px of a full line, at the page's resolution.

    Returns:
        The median left and median right edge of the bands wider than
        column_wide, or None if the half has no such band.
    """
    full = [b for b in bands if b.width > column_wide]
    if not full:
        return None
    lefts = [b.left for b in full]
    rights = [b.right for b in full]
    return int(np.median(lefts)), int(np.median(rights))


def _letter_lines(
    letters: np.ndarray,
    top: int,
    left: int,
    right: int,
    join: int,
    tall: int,
    upright: float,
) -> list[tuple[int, int, int, int, int]]:
    """Group the letters of a region into lines by their vertical centres.

    Rows of white cannot separate the lines here: on some pages the
    descenders of the last line touch the foot row. The centres of the
    letters stay a line apart.

    Args:
        letters: Letter ink mask of the page.
        top: First row of the region.
        left: First column of the region.
        right: Column after the last one of the region.
        join: A letter joins a line if its centre is this near, in px, to the
            mean centre of the line.
        tall: Height in px of a letter that counts.
        upright: A component more than this many times taller than wide is a
            piece of a rule, not a letter, and does not count.

    Returns:
        One tuple for each line, from the top: top, bottom, left, right, and
        the number of its letters that count.
    """
    region = letters[top:, left:right].astype(np.uint8)
    count, _, stats, centres = cv2.connectedComponentsWithStats(region, connectivity=8)
    found = sorted((centres[i][1], i) for i in range(1, count))
    groups: list[list[tuple[float, int]]] = []
    for centre, i in found:
        if groups and centre - np.mean([c for c, _ in groups[-1]]) <= join:
            groups[-1].append((centre, i))
        else:
            groups.append([(centre, i)])
    lines = []
    for group in groups:
        boxes = [stats[i] for _, i in group]
        lines.append(
            (
                top + min(int(b[1]) for b in boxes),
                top + max(int(b[1] + b[3]) for b in boxes),
                left + min(int(b[0]) for b in boxes),
                left + max(int(b[0] + b[2]) for b in boxes),
                sum(1 for b in boxes if b[3] >= tall and b[3] <= upright * b[2]),
            )
        )
    return lines


def find_flush_foot(
    halves: tuple[list[Band], list[Band]],
    letters: np.ndarray,
    dpi: int,
    *,
    column_wide: int = COLUMN_WIDE,
    start: int = START,
    start_ink: float = START_INK,
    line_depth: int = LINE_DEPTH,
    above: int = ABOVE,
    line_min: int = LINE_MIN,
    flush: int = FLUSH,
    letters_min: int = LETTERS,
    upright: float = UPRIGHT,
    pitch: int = 48,
    reference_dpi: int = REFERENCE_DPI,
) -> tuple[Region, tuple[int, int, int, int]] | None:
    """Find a catchword in the right column, for a page that find_foot refused.

    Args:
        halves: Line bands of the left and right half, from band_lines.
        letters: Letter ink mask of the same page, from letter_ink.
        dpi: Resolution of the page.
        column_wide: Width in px at REFERENCE_DPI of a full line.
        start: Width in px at REFERENCE_DPI to examine from the column edge.
        start_ink: Share of letter ink that makes a line a text line.
        line_depth: Clearance in px at REFERENCE_DPI under each line top.
        above: Distance in px at REFERENCE_DPI that makes a line a line above.
        line_min: Height in px at REFERENCE_DPI of a letter that counts.
        flush: Greatest distance in px at REFERENCE_DPI from the end of a
            catchword to the right edge of its column.
        letters_min: Fewest letters of line_min height in a foot line.
        upright: A component more than this many times taller than wide is a
            piece of a rule, not a letter.
        pitch: Body line pitch in px at REFERENCE_DPI.
        reference_dpi: Resolution the px values are given at.

    Returns:
        The region to white out, from the cut row down in the right column,
        and the box of the foot line as top, bottom, left, right. None if the
        right column has no catchword.
    """
    scale = dpi / reference_dpi
    column_wide, start, line_depth, above, line_min, flush, pitch = (
        max(1, round(v * scale))
        for v in (column_wide, start, line_depth, above, line_min, flush, pitch)
    )
    left, right = halves
    right_edges = _edges(right, column_wide)
    if right_edges is None:
        return None
    edge, end = right_edges
    top = max(b.top for b in right if b.width > column_wide)

    # A third of the pitch is wider than the spread of letter centres in one
    # line, and narrower than half the distance between two lines.
    lines = _letter_lines(
        letters, top, edge, end + flush, pitch // 3, line_min, upright
    )
    foot = None
    for line in reversed(lines):
        line_top, line_bottom, _, line_right, tall = line
        window = letters[line_top:line_bottom, edge : edge + start]
        is_text = window.size > 0 and float(window.mean()) >= start_ink
        if not is_text and line_right >= end - flush and tall >= letters_min:
            foot = line
            break
    if foot is None:
        return None

    foot_top = foot[0]
    over = [ln for ln in lines if ln[1] <= foot_top and ln[4] >= letters_min]
    cut = (over[-1][1] + foot_top) // 2 if over else foot_top
    floors = [ln[0] + line_depth for ln in lines if ln[0] < foot_top - above]
    cut = min(foot_top, max([cut, *floors]))

    left_edges = _edges(left, column_wide)
    start_x = (left_edges[1] + edge) // 2 if left_edges is not None else edge
    return Region(cut, start_x, letters.shape[1]), foot[:4]


def find_direction(
    halves: tuple[list[Band], list[Band]],
    dpi: int,
    *,
    column_wide: int = COLUMN_WIDE,
    line_depth: int = LINE_DEPTH,
    indent: int = INDENT,
    short: int = SHORT,
    reference_dpi: int = REFERENCE_DPI,
) -> tuple[Region, Band] | None:
    """Find a direction line at the foot of the left column.

    Args:
        halves: Line bands of the left and right half, from band_lines.
        dpi: Resolution of the page.
        column_wide: Width in px at REFERENCE_DPI of a full line.
        line_depth: Clearance in px at REFERENCE_DPI under each line top.
        indent: Least distance in px at REFERENCE_DPI from the column edge to
            the start of a direction line.
        short: Least distance in px at REFERENCE_DPI from the end of a
            direction line to the right edge of its column.
        reference_dpi: Resolution the px values are given at.

    Returns:
        The region to white out, from the cut row down in the left column,
        and the band of the direction line. None if the lowest band of the
        left half is not a direction line.
    """
    scale = dpi / reference_dpi
    column_wide, line_depth, indent, short = (
        max(1, round(v * scale)) for v in (column_wide, line_depth, indent, short)
    )
    left, right = halves
    left_edges = _edges(left, column_wide)
    if left_edges is None or not left:
        return None
    edge, end = left_edges
    lowest = max(left, key=lambda b: b.bottom)
    # A paragraph's last line starts at the edge, and its first line runs to
    # the right edge. Half a full line keeps out specks banded on their own.
    if not (
        lowest.left - edge >= indent
        and end - lowest.right >= short
        and lowest.width >= column_wide // 2
    ):
        return None

    over = [b for b in left if b.bottom <= lowest.top]
    cut = (max(b.bottom for b in over) + lowest.top) // 2 if over else lowest.top
    floors = [b.top + line_depth for b in over]
    cut = min(lowest.top, max([cut, *floors]))
    right_edges = _edges(right, column_wide)
    end_x = (end + right_edges[0]) // 2 if right_edges is not None else end
    return Region(cut, 0, end_x), lowest


class StripFoot:
    """White out the foot row and everything under it."""

    name = "strip-foot"

    def __init__(
        self,
        *,
        column_wide: int = COLUMN_WIDE,
        start: int = START,
        start_ink: float = START_INK,
        line_depth: int = LINE_DEPTH,
        above: int = ABOVE,
        flush: int = FLUSH,
        letters: int = LETTERS,
        indent: int = INDENT,
        short: int = SHORT,
        tuning: Tuning = Tuning(),
        tallest: int = TALLEST,
        upright: float = UPRIGHT,
    ) -> None:
        """Keep the constants for find_foot and its fallbacks.

        Args:
            column_wide: Width in px at REFERENCE_DPI of a full line.
            start: Width in px at REFERENCE_DPI to examine from the column edge.
            start_ink: Share of letter ink that makes a band a text line.
            line_depth: Clearance in px at REFERENCE_DPI under each line top.
            above: Distance in px at REFERENCE_DPI that makes a band a line above.
            flush: Greatest distance in px at REFERENCE_DPI from the end of a
                catchword to the right edge of its column.
            letters: Fewest letters of LINE_MIN height in a foot line.
            indent: Least indent in px at REFERENCE_DPI of a direction line.
            short: Least distance in px at REFERENCE_DPI from the end of a
                direction line to the right edge of its column.
            tuning: The constants for band_lines.
            tallest: Tallest letter, in px, that the cut keeps whole.
            upright: A component more than this many times taller than wide
                is a piece of a rule. It does not count as a catchword letter.
        """
        self.column_wide = column_wide
        self.start = start
        self.start_ink = start_ink
        self.line_depth = line_depth
        self.above = above
        self.flush = flush
        self.upright = upright
        self.letters = letters
        self.indent = indent
        self.short = short
        self.tuning = tuning
        self.tallest = tallest

    def apply(self, frame: Frame) -> StageOutput:
        """Remove the foot row from one page.

        Args:
            frame: A straightened page with figures masked and the head removed.

        Returns:
            The page with every row from the cut down made white, or the page
            unchanged if it has no foot row.
        """
        dpi = frame.provenance.dpi
        # The letter mask must match the one band_lines uses, so the same
        # Tuning gives the area and stroke limits. A different mask would
        # count speckle that banding ignores.
        tuning = self.tuning
        scale = dpi / REFERENCE_DPI
        letters = letter_ink(
            frame.image,
            area=max(1, round(tuning.letter_area * scale**2)),
            stroke_height=2 * max(1, round(tuning.pitch * scale)),
            stroke_aspect=tuning.stroke_aspect,
        )
        halves = band_lines(frame.image, dpi, tuning)
        found = find_foot(
            halves,
            letters,
            dpi,
            column_wide=self.column_wide,
            start=self.start,
            start_ink=self.start_ink,
            line_depth=self.line_depth,
            above=self.above,
        )
        if found is None:
            return self._fallback(frame, halves, letters)

        cut, foot = found
        # On most pages the descenders of the last line and the tops of the
        # foot row share rows, so no row cut can separate them. Each letter
        # that the cut touches stays or goes whole, by the side of the cut it
        # reaches further into. Not by its ink: the cut can be near the
        # baseline of the last line, and then most of a p is under it. Over
        # the foot row, the row halfway between it and the line above decides,
        # and not the cut. The cut can go through a catchword, and the band of
        # the foot row starts at the x-height, so the long s of a catchword
        # such as est reaches far above the top of the band.
        a, b = _window(cut, frame.height, dpi, self.tallest)
        rows = np.arange(a, b, dtype=float)[:, None]
        offset = np.repeat(rows - cut + 0.5, frame.width, axis=1)
        over = [
            band.bottom
            for bands in halves
            for band in bands
            if band.bottom <= foot.top
            and band.left < foot.right
            and foot.left < band.right
        ]
        middle = (max(over, default=foot.top) + foot.top) / 2
        offset[:, foot.left : foot.right] = rows - middle
        whited = np.broadcast_to(rows >= cut, offset.shape)
        kept, gone = whole_letters(
            letters[a:b], offset, whited, dpi, tallest=self.tallest
        )

        stripped = frame.image.copy()
        stripped[cut:] = WHITE
        window = stripped[a:b]
        window[kept] = frame.image[a:b][kept]
        window[gone] = WHITE

        findings = [
            Finding(
                "catchword",
                Box(0, cut, frame.width, frame.height - cut),
                note=f"cut at {cut}",
            ),
            Finding("text-line", Box(foot.left, foot.top, foot.width, foot.height)),
        ]
        return StageOutput(
            frames=[frame.derive(stripped)],
            findings=findings,
            summary=f"foot row stripped, rows {cut} to {frame.height}",
        )

    def _fallback(
        self,
        frame: Frame,
        halves: tuple[list[Band], list[Band]],
        letters: np.ndarray,
    ) -> StageOutput:
        """Remove a catchword and a direction line that no row cut can reach.

        On these pages the left column runs below the foot row, so a cut across
        the whole page would take its last lines. Each region is cut by itself:
        the right column under its catchword, and the left column under its
        direction line.

        Args:
            frame: The page that find_foot found no foot row on.
            halves: Its line bands, from band_lines.
            letters: Its letter ink mask, from letter_ink.

        Returns:
            The page with each region made white, or the page unchanged if it
            has neither a catchword nor a direction line.
        """
        dpi = frame.provenance.dpi
        flush = find_flush_foot(
            halves,
            letters,
            dpi,
            column_wide=self.column_wide,
            start=self.start,
            start_ink=self.start_ink,
            line_depth=self.line_depth,
            above=self.above,
            flush=self.flush,
            letters_min=self.letters,
            upright=self.upright,
            pitch=self.tuning.pitch,
        )
        direction = find_direction(
            halves,
            dpi,
            column_wide=self.column_wide,
            line_depth=self.line_depth,
            indent=self.indent,
            short=self.short,
        )
        if flush is None and direction is None:
            return StageOutput(frames=[frame], summary="no foot row found, left as is")

        stripped = frame.image.copy()
        findings = []
        parts = []
        if flush is not None:
            region, (top, bottom, left, right) = flush
            self._white(frame, stripped, letters, region)
            findings += [
                Finding(
                    "catchword",
                    Box(region.left, region.cut, region.right - region.left,
                        frame.height - region.cut),
                    note=f"cut at {region.cut}",
                ),
                Finding("text-line", Box(left, top, right - left, bottom - top)),
            ]
            parts.append(f"catchword stripped, right column rows {region.cut} down")
        if direction is not None:
            region, band = direction
            self._white(frame, stripped, letters, region)
            findings += [
                Finding(
                    "catchword",
                    Box(region.left, region.cut, region.right - region.left,
                        frame.height - region.cut),
                    note=f"direction line, cut at {region.cut}",
                ),
                Finding("text-line", Box(band.left, band.top, band.width, band.height)),
            ]
            parts.append(f"direction line stripped, left column rows {region.cut} down")
        return StageOutput(
            frames=[frame.derive(stripped)],
            findings=findings,
            summary="; ".join(parts),
        )

    def _white(
        self,
        frame: Frame,
        stripped: np.ndarray,
        letters: np.ndarray,
        region: Region,
    ) -> None:
        """White out one region, and keep each letter that its cut crosses whole.

        A letter that crosses the cut row stays or goes whole, by the side it
        reaches further into, as in the full-width cut.

        Args:
            frame: The page as it was before any region was made white.
            stripped: The copy of the page to change, in place.
            letters: The letter ink mask of the page.
            region: The cut row and the columns to make white.
        """
        dpi = frame.provenance.dpi
        a, b = _window(region.cut, frame.height, dpi, self.tallest)
        rows = np.arange(a, b, dtype=float)[:, None]
        offset = np.repeat(rows - region.cut + 0.5, frame.width, axis=1)
        inside = np.zeros(frame.width, dtype=bool)
        inside[region.left : region.right] = True
        whited = (rows >= region.cut) & inside[None, :]
        kept, gone = whole_letters(
            letters[a:b], offset, whited, dpi, tallest=self.tallest
        )
        stripped[region.cut :, region.left : region.right] = WHITE
        window = stripped[a:b]
        window[kept & inside[None, :]] = frame.image[a:b][kept & inside[None, :]]
        window[gone & inside[None, :]] = WHITE
