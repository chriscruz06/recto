"""Strip the running head and folio off the top of a page.

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
the head, the folio, and whatever scanner noise sat over them.

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
"""

from __future__ import annotations

from dataclasses import dataclass

from recto.frames import Box, Finding, Frame
from recto.pipeline import StageOutput
from recto.stages.bands import Band, band_lines

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

        stripped = frame.image.copy()
        stripped[: head.cut] = WHITE

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
