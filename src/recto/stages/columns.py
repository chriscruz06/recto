"""Split a page into its text columns.

Body pages set two columns. OCR reads straight across the page, so it must get
each column as a separate image. This stage finds the cut between the columns
and makes one frame for each column. A single-column page, such as the title
page, comes out as one frame.

The cut is a straight line, but it can slant. On In Apocalypsim in part 4, one
column often leans against the other by up to 30 px for each 1,000 rows. Over a
page, the gap then moves about 90 px, but it is only about 40 px wide. Thus no
vertical cut fits. Deskew cannot correct this, because it turns the whole page.

The search does not use the printed column rule. The rule is clear on most
pages of Super Iohannem, but In Apocalypsim has a narrow gap and often no rule.
It uses the letter ink from bands.letter_ink, which ignores long thin strokes
such as the rule. For each line of type from band_lines, it records if letters
lie within CLEAR px of a column. Then it tries each slant up to SLANT, in steps
of SLANT_STEP, and each position within REACH of the middle of the text block.
The best cut crosses the fewest lines. Ties go to the widest clear gap, and
then to the smallest slant. The cut goes through the centre of that gap.

Single or two columns. The stage counts the share of lines that the best cut
crosses. Measured on all 555 page frames of the four parts, two-column pages
give 0.17 or less, and single-column pages give 0.41 or more. SPLIT_MAX is
between the two. Most crossings on two-column pages are not words that the cut
divides. They are commas and pieces of a broken rule within CLEAR of the cut.

Titles across both columns. An opening page has a title in large type above
the two columns, for example D. ALBERTI MAGNI on p11 recto. A cut through it
divides each title line. Thus the stage keeps a title block as one frame above
the columns. A title block starts when one of the first TITLE_FIRST lines is at
least TITLE_TALL px tall and crosses the cut. It ends at the last crossing line
before TITLE_CLEAN lines in a row that do not cross. The tall line is
necessary: on some In Apocalypsim pages the cut touches the ends of the first
body lines, and those lines are body size.

Measured on all four parts, every cut looked at:

    540 page frames split in two and 15 stay whole. The 15 are the title page,
    the catalogue, the privilege, the dedication and the other single-column
    front matter of part 1, and five single-column pages of part 3.

    Ten frames get a title block: the catalogue, PROLOGI S. HIERONYMI on p8
    verso and D. ALBERTI MAGNI on p11 recto in part 1, and the openings of the
    indexes and of the In Apocalypsim prologue in parts 3 and 4.

    The opening of the Index rerum, part 3 p37 recto, fails. Speckle round its
    headpiece moves the cut 125 px from the middle. The title and both columns
    are cut wrongly.

The cut keeps the full width of the clear gap white in both columns. Thus a
printed rule in the gap goes, and the columns keep no ink of each other. If
pieces of a broken rule count as letters, the gap is beside the rule, and the
rule stays at the edge of one column.

Moving each constant one way and then the other, over all four parts: REACH
at 100, SLANT at 0.03 and SPLIT_MAX at 0.2 each change only part 3 p37 recto.
REACH at 200, SLANT at 0.05 and SPLIT_MAX at 0.4 change nothing. SLANT_STEP at
0.001 moves three cuts by more than 10 px. CLEAR is the tightest constant. At
4 px it changes three title blocks and moves 12 cuts by more than 10 px. At
8 px it moves seven cuts in part 4.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from recto.frames import Box, Finding, Frame, Line
from recto.pipeline import StageOutput
from recto.stages.bands import Tuning, band_lines, letter_ink, text_block

REACH = 150
"""Furthest the cut may be from the middle of the text block, in px."""

CLEAR = 6
"""A line crosses the cut if letter ink is this near to it, in px."""

SLANT = 0.04
"""Largest slant of the cut, in px across for each px down."""

SLANT_STEP = 0.002
"""Step between the slants that the search tries."""

SPLIT_MAX = 0.3
"""Above this share of crossed lines, the page is one column."""

TITLE_FIRST = 4
"""A title block must start in this many first lines."""

TITLE_TALL = 40
"""Shortest crossing line, in px, that starts a title block."""

TITLE_CLEAN = 8
"""This many uncrossed lines in a row end a title block."""

REFERENCE_DPI = 300
"""The resolution every length above is measured at."""

WHITE = 255


@dataclass(frozen=True)
class Cut:
    """A straight cut between two columns: x = x0 + slope * (y - y0)."""

    x0: float
    y0: float
    slope: float
    gap: int
    """Width in px of the clear gap round the cut."""

    crossed: float
    """Share of lines that the cut crosses."""

    def x(self, y: np.ndarray | float) -> np.ndarray | float:
        """Give the column of the cut at row y.

        Args:
            y: One row or an array of rows.

        Returns:
            The column of the cut at each row, not rounded.
        """
        return self.x0 + self.slope * (np.asarray(y) - self.y0)


def find_cut(
    lines: list[tuple[int, int]],
    letters: np.ndarray,
    middle: int,
    *,
    reach: int,
    clear: int,
    slant: float,
    slant_step: float,
) -> tuple[Cut, np.ndarray]:
    """Find the straight cut that crosses the fewest lines.

    Args:
        lines: Top and bottom row of each line of type, top to bottom.
        letters: Letter ink mask of the page.
        middle: Column at the middle of the text block.
        reach: Furthest the cut may be from middle, in px.
        clear: A line crosses if letter ink is this near to the cut, in px.
        slant: Largest slant to try.
        slant_step: Step between slants.

    Returns:
        The cut, and for each line True if the cut crosses it.

    Raises:
        ValueError: If lines is empty.
    """
    if not lines:
        raise ValueError("find_cut needs at least one line of type")

    # The window must hold the cut at every row, so it is wider than reach by
    # the most that the slant can move the cut over the page.
    span = reach + int(np.ceil(slant * letters.shape[0])) + clear + 2
    a = max(0, middle - span)
    b = min(letters.shape[1], middle + span)
    inked = np.stack([letters[top:bottom, a:b].any(axis=0) for top, bottom in lines])
    padded = np.pad(inked, ((0, 0), (clear, clear)))
    near = np.lib.stride_tricks.sliding_window_view(padded, 2 * clear + 1, axis=1)
    near = near.any(axis=2)

    rows = np.array([(top + bottom) / 2 for top, bottom in lines])
    centre = float(rows.mean())
    starts = np.arange(middle - reach, middle + reach) - a
    index = np.arange(len(lines))[:, None]

    best = None
    for s in np.arange(-slant, slant + 1e-9, slant_step):
        shift = np.round(s * (rows - centre)).astype(int)
        cols = starts[None, :] + shift[:, None]
        inside = (cols >= 0) & (cols < near.shape[1])
        hit = np.where(inside, near[index, np.clip(cols, 0, near.shape[1] - 1)], True)
        count = hit.sum(axis=0)
        fewest = int(count.min())
        width, run = max((r1 - r0, (r0, r1)) for r0, r1 in _runs(count == fewest))
        key = (fewest, -width, abs(s))
        if best is None or key < best[0]:
            k = (run[0] + run[1] - 1) // 2
            best = (key, starts[k] + a, float(s), hit[:, k].copy(), width)

    (fewest, _, _), x0, s, hit, width = best
    cut = Cut(
        x0=float(x0),
        y0=centre,
        slope=s,
        gap=int(width) + 2 * clear,
        crossed=fewest / len(lines),
    )
    return cut, hit


def title_lines(
    hit: np.ndarray,
    lines: list[tuple[int, int]],
    *,
    first: int,
    tall: int,
    clean: int,
) -> int:
    """Count the lines of a title block above the columns.

    Args:
        hit: For each line, True if the cut crosses it.
        lines: Top and bottom row of each line, top to bottom.
        first: The title must start in this many first lines.
        tall: Shortest crossing line, in px, that starts a title.
        clean: This many uncrossed lines in a row end the title.

    Returns:
        The number of lines in the title block, 0 if there is none.
    """
    early = range(min(first, len(lines)))
    if not any(hit[i] and lines[i][1] - lines[i][0] >= tall for i in early):
        return 0

    last, run = -1, 0
    for i, crossed in enumerate(hit):
        if crossed:
            last, run = i, 0
        else:
            run += 1
            if run >= clean:
                break
    return last + 1


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Find the runs of True in a 1D mask.

    Args:
        mask: A 1D boolean array.

    Returns:
        The start and one past the end of each run.
    """
    edges = np.diff(np.r_[0, mask.astype(np.int8), 0])
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))


class SplitColumns:
    """Cut a page into a title block, if any, and its columns."""

    name = "split-columns"

    def __init__(
        self,
        *,
        reach: int = REACH,
        clear: int = CLEAR,
        slant: float = SLANT,
        slant_step: float = SLANT_STEP,
        split_max: float = SPLIT_MAX,
        title_first: int = TITLE_FIRST,
        title_tall: int = TITLE_TALL,
        title_clean: int = TITLE_CLEAN,
    ) -> None:
        """Keep the constants for the search.

        Args:
            reach: Furthest the cut may be from the middle, in px at 300 dpi.
            clear: Distance in px at 300 dpi at which letter ink crosses.
            slant: Largest slant of the cut.
            slant_step: Step between slants.
            split_max: Above this share of crossed lines, keep one column.
            title_first: A title must start in this many first lines.
            title_tall: Shortest crossing line in px at 300 dpi for a title.
            title_clean: This many uncrossed lines in a row end a title.
        """
        self.reach = reach
        self.clear = clear
        self.slant = slant
        self.slant_step = slant_step
        self.split_max = split_max
        self.title_first = title_first
        self.title_tall = title_tall
        self.title_clean = title_clean

    def apply(self, frame: Frame) -> StageOutput:
        """Split one page into frames, in reading order.

        Args:
            frame: A page with figures masked and head and foot removed.

        Returns:
            One frame for a single-column page. Otherwise a frame for the
            title block, if there is one, then the left and the right column.
        """
        dpi = frame.provenance.dpi
        scale = dpi / REFERENCE_DPI

        def px(length: float) -> int:
            return max(1, round(length * scale))

        # The same mask that band_lines uses, so that a line and its letters
        # agree. A mask with speckle would put ink in every gap.
        tuning = Tuning()
        letters = letter_ink(
            frame.image,
            area=max(1, round(tuning.letter_area * scale**2)),
            stroke_height=2 * px(tuning.pitch),
            stroke_aspect=tuning.stroke_aspect,
        )
        halves = band_lines(frame.image, dpi, tuning)
        lines = sorted({(b.top, b.bottom) for half in halves for b in half})
        if not lines:
            return self._whole(frame, "no lines of type, kept as one column")

        left, right = text_block(
            letters, fraction=tuning.block_fraction, bridge=px(tuning.block_gap)
        )
        cut, hit = find_cut(
            lines,
            letters,
            (left + right) // 2,
            reach=px(self.reach),
            clear=px(self.clear),
            slant=self.slant,
            slant_step=self.slant_step,
        )
        if cut.crossed > self.split_max:
            return self._whole(
                frame,
                f"one column, best cut crosses {cut.crossed:.0%} of lines",
            )

        n = title_lines(
            hit,
            lines,
            first=self.title_first,
            tall=px(self.title_tall),
            clean=self.title_clean,
        )
        top = (lines[n - 1][1] + lines[n][0]) // 2 if 0 < n < len(lines) else 0
        return self._split(frame, cut, top)

    def _whole(self, frame: Frame, summary: str) -> StageOutput:
        """Pass the page on as its only column.

        Args:
            frame: The page.
            summary: The caption for the debug overlay.

        Returns:
            One frame, marked as column 0.
        """
        only = frame.derive(frame.image, column=0)
        return StageOutput(frames=[only], summary=summary)

    def _split(
        self,
        frame: Frame,
        cut: Cut,
        top: int,
    ) -> StageOutput:
        """Make the title frame, if any, and the two column frames.

        Args:
            frame: The page.
            cut: The cut between the columns.
            top: First row under the title block, 0 if there is none.

        Returns:
            The frames in reading order, with findings and a summary.
        """
        image = frame.image
        height, width = image.shape
        rows = np.arange(top, height)
        edge = cut.x(rows)
        half = cut.gap / 2
        cols = np.arange(width)[None, :]

        # Each column keeps nothing from the gap. The gap has no letters on
        # any line, so this removes only the rule and noise in it.
        body = image[top:]
        left = np.where(cols < (edge - half)[:, None], body, WHITE).astype(np.uint8)
        right = np.where(cols > (edge + half)[:, None], body, WHITE).astype(np.uint8)
        left_end = int(np.ceil((edge - half).max()))
        right_start = int(np.floor((edge + half).min()))

        frames, findings = [], []
        index = 0
        if top > 0:
            frames.append(frame.derive(image[:top].copy(), column=index))
            findings.append(Finding("column", Box(0, 0, width, top), note="title"))
            index += 1
        frames.append(frame.derive(left[:, : max(1, left_end)].copy(), column=index))
        frames.append(frame.derive(right[:, right_start:].copy(), column=index + 1))

        findings.append(
            Finding(
                "column",
                Line(
                    int(round(cut.x(top))),
                    top,
                    int(round(cut.x(height - 1))),
                    height - 1,
                ),
                note=f"slope {cut.slope * 1000:+.0f} per 1000 rows",
            )
        )

        title = ", title block above" if top > 0 else ""
        summary = (
            f"two columns{title}, cut slants {cut.slope * 1000:+.0f} px per 1000 "
            f"rows, gap {cut.gap} px, crosses {cut.crossed:.0%} of lines"
        )
        return StageOutput(frames=frames, findings=findings, summary=summary)
