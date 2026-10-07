"""Find the lines of type on a page, as horizontal bands of rows.

The next two stages strip a page's furniture, and both define it by where the
lines are: the running head is what sits above the first wide gap, and the
catchword is the short line under the last one. This module finds the lines and
nothing more. It does not decide which line is which, and the stage it provides
draws what it found and passes the page on untouched.

Per half, not per page. The two columns of a page usually share one grid of
lines: in 88 percent of 2,326 windows of ten lines, measured across the 148
pages of the sample, the columns sit within 4 px of each other. But a lemma set
in the larger type keeps a grid of its own, and wherever one column carries
one, a profile taken across both smears the two grids together and breaks lines
into slivers. So the text block is cut at its middle and each half is banded on
its own. That cut is not the column split, which is a later stage's job. It
only has to land between the columns, and it does: the printed rule between
them, where it shows, sits within 7 px of the text block's midpoint on
90 percent of pages, median 1 px, and type resumes about 32 px either side of
it. Each half stops half a pitch short of the midpoint, and runs half a pitch
past the outer edge of the block, because catchwords overhang their column by
up to 15 px.

The text block is the widest run of pixel columns holding at least a quarter of
the page's 95th percentile column ink, gaps under 150 px bridged. The gap that
gets bridged is the one between the columns. What is left out is the margin,
and the speckled strip down the outer edge of many rectos, which can be as dark
as a sparse column but always sits a few hundred px of near white away.

Letters only. The profile counts ink in connected components of at least 90 px,
the size above which the despeckle measurements found letters rather than
punctuation and speckle. The speckle despeckle rightly keeps raises every row a
little and grows bands in empty margins, which is where the next two stages
look. Counting letters only removed 85 percent of the bands with a run under
20 px, every one sampled a speck or a fragment, and left the number of full
lines nearly unchanged, 19,582 against 19,637. Components taller than two
pitches and four times taller than wide are left out as well. No letter has
that shape, but the edge of the leaf does, and one such stroke 357 px tall on
p15 recto was growing bands under the catchword.

Which rows are a line. A row belongs to a line when its ink rises at least
halfway from the gap level near it towards the peak near it. The gap level is
the lowest row within one pitch, which always reaches a gap; the peak is the
highest row within 16 px. Measuring from the gap rather than from the average
is what finds short lines. The last word of a paragraph, or a catchword,
carries a fraction of a full line's ink and never rises above the local
average, but it rises well clear of the white under it.

The peak reach is the tight constant. At 12 px the running head's large type
breaks into pieces on twice as many pages. At 20 px the descenders of the last
full line count as the catchword's peak, and one of the ten catchwords used to
check this is lost; at 24 px two are, and twice as many heads split as at
16 px.

Putting large type back together. Type bigger than the body has structure of
its own: the tops of its capitals form a band, and so do the loops of its
descenders. Three rules reassemble it. Bands closer than 12 px merge, which no
two body lines are: over 17,306 gaps between them the 1st percentile is 21 px,
and at 6 px body lines start to split. A band under 14 px tall folds into the
nearest line within 30 px. And a band under 40 percent of a neighbour's height,
and closer to it than 30 percent of that height, is part of that neighbour.
That last rule keeps the running head whole, and its 30 percent is held down by
the first body line, which typically sits 37 to 40 px under a head 80 to 110 px
tall. At 40 percent the first body line merges into the head on 54 of 260 half
pages, and would be stripped with it. The rule runs once over the bands as
first found, because a band that grows by taking in a piece must not then reach
for the next.

What is text. A band is kept only if its letters hold a horizontal run of at
least 30 px, gaps under 10 px bridged: about two letters. On 37 bands at the
foot of body pages, labelled by eye, the shortest real foot row was the
signature C 3 at 35 px, and the noise, specks and blots and short strokes, ran
under 30 apart from one blot at 36 px and two long pen strokes. At 20 px nine
of those noise bands come back; at 40, five of the ten catchwords are lost.
Without the bridging, a catchword like "in" is two runs of one letter each.

Then bands are grouped wherever they sit within two pitches of each other, and
a group survives only with at least two bands, one of them a full line, a run
of 100 px. Noise far from the text is a group of its own: on body pages every
band more than 100 px from a full line was noise, and the two long thin pen
strokes in the sample, which pass the run test, are each alone. At 72 px real
running heads separate from the text and are lost; at 120 px, noise under the
foot row starts to join it.

Known behaviour, over the 130 body pages of the sample:

    The running head comes out as two bands on 11 of 260 half pages, where the
    tops of its capitals make a band more than 40 percent the size of the rest.
    The stage that strips the head takes everything above the head's gap, so
    both pieces go.

    An ink blot 73 px under the last line of p21 recto is kept. Its run is
    36 px.

    A catchword that is one narrow glyph, an ampersand on its own, would run
    under 30 px and be lost. The one ampersand catchword in the sample shares
    its row with the signature G 3 and survives.

Banding a page costs about 0.15 s, most of it the connected component pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

import cv2
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from recto.frames import Box, Finding, Frame
from recto.pipeline import StageOutput

REFERENCE_DPI = 300
"""The resolution every length in Tuning is measured at."""

INK_BELOW = 200
"""Pixels darker than this count as ink."""


@dataclass(frozen=True)
class Tuning:
    """Every constant band_lines uses. Lengths are pixels at REFERENCE_DPI.

    Sixteen constants are too many to pass one at a time, the way the other
    stages take theirs, so they travel together. The module docstring gives the
    measurement behind each one.
    """

    letter_area: int = 90
    """Smallest component counted as type, in square pixels."""

    stroke_aspect: float = 4
    """A component taller than two pitches and this many times taller than it
    is wide is a stroke, not type."""

    pitch: int = 48
    """Body line pitch. The gap level is looked for one pitch either side,
    groups break at two pitches, and each half of the text block keeps half a
    pitch clear of the middle and runs half a pitch past the outer edge."""

    smooth: int = 5
    """Box filter over the row profile."""

    peak_reach: int = 16
    """How far either side a row's peak is looked for."""

    rise: float = 0.5
    """How far from the gap level towards the peak a row must rise."""

    merge_gap: int = 12
    """Bands closer than this are one line."""

    sliver: int = 14
    """A band shorter than this is a piece of a line, never a line."""

    fold_reach: int = 30
    """How far a sliver may sit from the line it folds into."""

    piece_height: float = 0.4
    """A band under this share of a neighbour's height can be a piece of it."""

    piece_gap: float = 0.3
    """It is one when closer to the neighbour than this share of its height."""

    min_run: int = 30
    """Shortest run of letters, across the band, that makes it text."""

    bridge: int = 10
    """Gaps narrower than this do not break a run."""

    full_run: int = 100
    """The run of a full line. A group of bands needs one to be text."""

    block_fraction: float = 0.25
    """Share of the 95th percentile column ink that marks the text block."""

    block_gap: int = 150
    """Gaps narrower than this inside the text block are bridged."""


@dataclass(frozen=True)
class Band:
    """One line of type: the rows it occupies and how far its letters reach."""

    top: int
    bottom: int
    """One past the last row."""

    left: int
    right: int
    """One past the last column."""

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def width(self) -> int:
        return self.right - self.left


def letter_ink(
    image: np.ndarray,
    *,
    area: int,
    stroke_height: int,
    stroke_aspect: float,
) -> np.ndarray:
    """Ink belonging to components the size of a letter, strokes left out."""
    ink = (image < INK_BELOW).astype(np.uint8)
    _, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)

    wide = stats[:, cv2.CC_STAT_WIDTH]
    tall = stats[:, cv2.CC_STAT_HEIGHT]
    stroke = (tall > stroke_height) & (tall > stroke_aspect * wide)

    keep = (stats[:, cv2.CC_STAT_AREA] >= area) & ~stroke
    keep[0] = False
    return keep[labels]


def text_block(letters: np.ndarray, *, fraction: float, bridge: int) -> tuple[int, int]:
    """The widest run of inked pixel columns, as start and one past the end."""
    column = letters.mean(axis=0)
    level = fraction * float(np.percentile(column, 95))
    inked = np.flatnonzero(column >= level) if level > 0 else np.array([], int)
    if inked.size == 0:
        return 0, letters.shape[1]

    starts, ends = _stretches(inked, bridge)
    widest = int(np.argmax(ends - starts))
    return int(starts[widest]), int(ends[widest])


def band_lines(
    image: np.ndarray,
    dpi: int,
    tuning: Tuning = Tuning(),
) -> tuple[list[Band], list[Band]]:
    """The lines of type on a page, top to bottom, for each half of its text block.

    A plain function rather than a method, so the stages that strip the running
    head and the catchword can call it without building a BandLines first.
    """
    t = tuning
    scale = dpi / REFERENCE_DPI

    def px(length: float) -> int:
        return max(1, round(length * scale))

    pitch = px(t.pitch)
    letters = letter_ink(
        image,
        area=max(1, round(t.letter_area * scale**2)),
        stroke_height=2 * pitch,
        stroke_aspect=t.stroke_aspect,
    )

    left, right = text_block(letters, fraction=t.block_fraction, bridge=px(t.block_gap))
    middle, margin = (left + right) // 2, pitch // 2
    halves = (
        (max(0, left - margin), middle - margin),
        (middle + margin, min(letters.shape[1], right + margin)),
    )

    left_half, right_half = (_band_half(letters[:, a:b], a, t, px) for a, b in halves)
    return left_half, right_half


def _band_half(letters, offset: int, t: Tuning, px) -> list[Band]:
    """Every rule in the module docstring, applied to one half of the block."""
    profile = letters.mean(axis=1)
    k = px(t.smooth)
    if k > 1:
        profile = np.convolve(profile, np.ones(k) / k, mode="same")

    gap_level = _running(profile, px(t.pitch), np.min)
    peak = _running(profile, px(t.peak_reach), np.max)
    rows = (profile > gap_level + t.rise * (peak - gap_level)) & (profile > 0)

    bands: list[list[int]] = []
    for top, bottom in _runs(rows):
        if bands and top - bands[-1][1] < px(t.merge_gap):
            bands[-1][1] = bottom
        else:
            bands.append([top, bottom])

    bands = _fold_slivers(bands, px(t.sliver), px(t.fold_reach))
    bands = _fold_pieces(bands, t.piece_height, t.piece_gap)

    texty = []
    for top, bottom in bands:
        inked = np.flatnonzero(letters[top:bottom].any(axis=0))
        starts, ends = _stretches(inked, px(t.bridge))
        run = int((ends - starts).max()) if inked.size else 0
        if run >= px(t.min_run):
            left, right = offset + int(inked[0]), offset + int(inked[-1]) + 1
            texty.append((top, bottom, run, left, right))

    groups: list[list[tuple]] = []
    for band in texty:
        if groups and band[0] - groups[-1][-1][1] <= 2 * px(t.pitch):
            groups[-1].append(band)
        else:
            groups.append([band])

    return [
        Band(top, bottom, left, right)
        for group in groups
        if len(group) >= 2 and any(run >= px(t.full_run) for _, _, run, _, _ in group)
        for top, bottom, _, left, right in group
    ]


def _fold_slivers(bands: list[list[int]], sliver: int, reach: int) -> list[list[int]]:
    """Fold each band shorter than sliver into the nearest full band within reach."""
    full = [band for band in bands if band[1] - band[0] >= sliver]
    for piece in (band for band in bands if band[1] - band[0] < sliver):
        distances = [(_gap(piece, band), i) for i, band in enumerate(full)]
        nearest = min(distances, default=None)
        if nearest is not None and nearest[0] <= reach:
            host = full[nearest[1]]
            host[0], host[1] = min(host[0], piece[0]), max(host[1], piece[1])
    return full


def _fold_pieces(bands: list[list[int]], height: float, gap: float) -> list[list[int]]:
    """Fold a band into a much taller neighbour it sits close to.

    Decided once over the bands as they stand, so a band that grows here cannot
    go on to take in the next one. A band whose chosen host is itself folded
    elsewhere is left where it is.
    """
    host = list(range(len(bands)))
    for i, band in enumerate(bands):
        best = None
        for j in (i - 1, i + 1):
            if not 0 <= j < len(bands):
                continue
            size, distance = bands[j][1] - bands[j][0], _gap(band, bands[j])
            fits = band[1] - band[0] < height * size and distance < gap * size
            if fits and (best is None or distance < best[0]):
                best = (distance, j)
        if best is not None:
            host[i] = best[1]

    merged = [list(band) for band in bands]
    for i, j in enumerate(host):
        if j != i and host[j] == j:
            merged[j][0] = min(merged[j][0], bands[i][0])
            merged[j][1] = max(merged[j][1], bands[i][1])
    return [
        merged[i]
        for i in range(len(bands))
        if host[i] == i or host[host[i]] != host[i]
    ]


def _gap(a, b) -> int:
    """Rows between two bands, zero if they touch or overlap."""
    if b[0] >= a[1]:
        return b[0] - a[1]
    if a[0] >= b[1]:
        return a[0] - b[1]
    return 0


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Start and one past the end of every run of True."""
    edges = np.diff(np.r_[False, mask, False].astype(np.int8))
    starts = np.flatnonzero(edges == 1).tolist()
    ends = np.flatnonzero(edges == -1).tolist()
    return list(zip(starts, ends))


def _stretches(inked: np.ndarray, bridge: int) -> tuple[np.ndarray, np.ndarray]:
    """Where sorted indices form unbroken stretches, gaps under bridge ignored."""
    if inked.size == 0:
        return np.array([0]), np.array([0])
    breaks = np.flatnonzero(np.diff(inked) > bridge)
    starts = np.r_[inked[0], inked[breaks + 1]]
    ends = np.r_[inked[breaks], inked[-1]] + 1
    return starts, ends


def _running(profile: np.ndarray, reach: int, reduce) -> np.ndarray:
    """Running minimum or maximum over reach rows either side."""
    padded = np.pad(profile, reach, mode="edge")
    return reduce(sliding_window_view(padded, 2 * reach + 1), axis=1)


class BandLines:
    """Draw the lines of type on a page and pass the page on unchanged."""

    name = "band-lines"

    def __init__(self, tuning: Tuning = Tuning()) -> None:
        self.tuning = tuning

    def apply(self, frame: Frame) -> StageOutput:
        halves = band_lines(frame.image, frame.provenance.dpi, self.tuning)

        findings = [
            Finding("text-line", Box(b.left, b.top, b.width, b.height))
            for half in halves
            for b in half
        ]
        spacings = [
            later.top + later.bottom - earlier.top - earlier.bottom
            for half in halves
            for earlier, later in zip(half, half[1:])
        ]
        pitch = f"{median(spacings) / 2:.0f} px" if spacings else "none"

        return StageOutput(
            frames=[frame],
            findings=findings,
            summary=(
                f"{len(findings)} bands, {len(halves[0])} left and "
                f"{len(halves[1])} right, median line spacing {pitch}"
            ),
        )
