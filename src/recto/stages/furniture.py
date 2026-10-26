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

Known failure, found in commit 17a: on three In Apocalypsim rectos of part 4,
p4, p12 and p22, both halves band the head and the first body line as one
band, and the cut falls under the first line, so that line is whited out.

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
that row without the last line of the left column, so the stage keeps it. Six
pages in parts 2 and 4 have this layout, with CAPVT or VISIO as catchword.

The cut is halfway between the foot row and the lowest band above it. But the
cut stays at least LINE_DEPTH under the top of each band that starts more than
ABOVE over the foot row. Some last lines band together with the white under
them, and a midpoint cut can then go into their descenders.

Measured on all four parts, 555 page frames, every cut looked at:

    The stage finds a foot row on 528 frames. In part 1 the cut is above all
    ten foot rows that were labelled by eye in commit 13. It is also above the
    blot on p21 recto and the library stamp on p31 recto, so they go too.

    The 27 frames without a cut are front matter, index ends, blank ends, the
    FINIS page, and the six chapter ends above. On part 2 p21 recto and part 4
    p8 recto, the direction line in the left half is the lowest band, and the
    right half has no band at that level. Their catchwords stay.

    The foot row sits 0 to 71 px under the band above it, 24 at the median.

Moving each constant one way and then the other: COLUMN_WIDE from 500 to 700
changes no cut. START at 200 or 400 changes four or two frames. START_INK at
0.03 or 0.08 changes three or four. ABOVE at 10 or 30 changes one or three.
LINE_DEPTH at 30 or 40 moves the cut by 1 to 5 px on many pages, but the cut
never passes the edge of a band.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from recto.frames import Box, Finding, Frame
from recto.pipeline import StageOutput
from recto.stages.bands import Band, Tuning, band_lines, letter_ink
from recto.stages.whole import TALLEST, whole_letters

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


def _window(cut: int, height: int, dpi: int) -> tuple[int, int]:
    """Find the rows round a row cut that can hold a letter the cut crosses.

    Args:
        cut: The row of the cut.
        height: Height of the page.
        dpi: Resolution of the page.

    Returns:
        The first row of the window and one past its last row.
    """
    reach = max(1, round(TALLEST * dpi / REFERENCE_DPI)) + 1
    return max(0, cut - reach), min(height, cut + reach)


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
    ) -> None:
        self.head_min = head_min
        self.line_min = line_min
        self.line_max = line_max
        self.gap_max = gap_max
        self.piece = piece

    def apply(self, frame: Frame) -> StageOutput:
        halves = band_lines(frame.image, frame.provenance.dpi)
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

        # The head cut can go through the ascenders of the first body line
        # and the descenders of the head. Each such letter is kept or removed
        # whole, by the side of the cut it reaches further into.
        tuning = Tuning()
        scale = frame.provenance.dpi / REFERENCE_DPI
        letters = letter_ink(
            frame.image,
            area=max(1, round(tuning.letter_area * scale**2)),
            stroke_height=2 * max(1, round(tuning.pitch * scale)),
            stroke_aspect=tuning.stroke_aspect,
        )
        a, b = _window(head.cut, frame.height, frame.provenance.dpi)
        rows = head.cut - 0.5 - np.arange(a, b, dtype=float)[:, None]
        offset = np.broadcast_to(rows, (b - a, frame.width))
        kept, gone = whole_letters(
            letters[a:b], offset, offset > 0, frame.provenance.dpi
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
            left = min(b.left for b in pieces)
            right = max(b.right for b in pieces)
            findings.append(
                Finding("text-line", Box(left, top, right - left, bottom - top))
            )

        sides = "both halves" if all(head.halves) else "one half"
        return StageOutput(
            frames=[frame.derive(stripped)],
            findings=findings,
            summary=f"running head stripped, rows 0 to {head.cut}, banded in {sides}",
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
    ) -> None:
        """Keep the constants for find_foot.

        Args:
            column_wide: Width in px at REFERENCE_DPI of a full line.
            start: Width in px at REFERENCE_DPI to examine from the column edge.
            start_ink: Share of letter ink that makes a band a text line.
            line_depth: Clearance in px at REFERENCE_DPI under each line top.
            above: Distance in px at REFERENCE_DPI that makes a band a line above.
        """
        self.column_wide = column_wide
        self.start = start
        self.start_ink = start_ink
        self.line_depth = line_depth
        self.above = above

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
        tuning = Tuning()
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
            return StageOutput(
                frames=[frame], summary="no foot row found, left as is"
            )

        cut, foot = found
        # On most pages the descenders of the last line and the tops of the
        # foot row share rows, so no row cut can separate them. Each letter
        # that the cut touches stays or goes whole, by the side of the cut it
        # reaches further into. Not by its ink: the cut can be near the
        # baseline of the last line, and then most of a p is under it. Where
        # the foot row is known, its top decides and not the cut. The cut can
        # go through a catchword, and the long s of a catchword such as est
        # reaches far above it.
        a, b = _window(cut, frame.height, dpi)
        rows = np.arange(a, b, dtype=float)[:, None]
        offset = np.repeat(rows - cut + 0.5, frame.width, axis=1)
        offset[:, foot.left : foot.right] = rows - foot.top + 0.5
        whited = np.broadcast_to(rows >= cut, offset.shape)
        kept, gone = whole_letters(letters[a:b], offset, whited, dpi)

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
