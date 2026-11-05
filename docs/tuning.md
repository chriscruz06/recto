# Tuning a profile

A profile sets the constants of the stages. This file describes each key in
`profiles/jammy-1651.toml`, in the same order. Each value in that file is the
default in the code. Each default was measured on the Jammy edition, Lyons 1651,
Operum Tomus Undecimus, at 300 dpi.

Use a profile with:

```powershell
recto run book.pdf --profile profiles\my-book.toml
```

A profile can name only the keys that it changes. The code gives the default for
every key that the profile does not name. A wrong section, key or type stops the
run, and the message lists the correct ones.

## How to read this file

- Lengths and areas are pixels at 300 dpi. The stages scale them to the
  resolution of each page.
- Angles are degrees. Fractions are from 0 to 1.
- **Lower** and **Higher** give what happened when the value was moved and the
  pages were measured again. All of it comes from the docstring of the module
  named over each section, or from the comment on the constant.
- **Not measured** means that no docstring records a run at another value. Do
  not guess the effect from the name of the key.
- **Measured** gives the facts that set the default, where they exist.

Two sections are shared. `[bands]` is read by band-lines, strip-head, strip-foot
and split-columns, because they must find lines the same way. `[whole]` is read
by strip-head, strip-foot and split-columns.

Three constants are not in profiles: `REFERENCE_DPI` and `INK_BELOW`, which set
units, and the cap on specks that despeckle draws in the debug overlay.

## `[crop-border]`

Module: `src/recto/stages/border.py`.

### `run_fraction = 0.15`

A border line must hold one unbroken ink run of at least this share of its
length.

- **Measured:** The longest run in the body text of the sample is 348 px. At
  0.15 the threshold is 888 px. A run test alone cut 539 px off the right edge
  of the title page, so `dark_fraction` must also pass.
- **Lower, higher:** Not measured.

### `dark_fraction = 0.5`

At least this share of a border line must be ink.

- **Measured:** Without this test, the title page lost 539 px at its right
  edge, through the final I of ALBERTI. Dense speckle there has long runs but
  thin ink. With both tests, that page crops 74 px like the other pages.
- **Lower, higher:** Not measured.

### `search_fraction = 0.15`

The stage looks this far in from each edge. This also limits how much the crop
can remove.

- **Measured:** The border is about 74 px on the left, 57 to 101 px on the
  right, 25 to 62 px at the bottom and 4 to 11 px at the top.
- **Lower, higher:** Not measured.

### `inset = 8`

The crop removes this many more pixels past each detected edge, for the fringe.

- **Lower, higher:** Not measured. No docstring records a measurement for this
  value.

## `[despeckle]`

Module: `src/recto/stages/despeckle.py`.

### `min_area = 16`

The stage removes each connected component smaller than this area.

- **Lower:** In a blank margin window, the removable speckle drops from 20
  marks to 3 as the threshold rises to 15. Below 15, more speckle stays.
- **Higher:** Above 15, no more speckle goes. At 60 the dots over i start to
  go, so "principio" reads "prıncıpıo". At 90 commas go too.
- **Measured:** At 16 the stage removes 40 percent of the components on page 9
  and 1.1 percent of its ink. A lost comma cannot be recovered later, so the
  default is near the bottom of the safe band.

## `[split-spread]`

Modules: `src/recto/stages/split.py`, and `src/recto/stages/gutter.py` for
`search_fraction` and `smooth_width`.

### `inset = 32`

The split removes this many pixels past each edge of the gutter band, because
the shadow of the fold fades past the band.

- **Lower:** The fringe reaches 11 px past the band on the median edge and
  32 px on the worst of 152 edges. The default is 32 so that every edge of the
  sample clears it.
- **Higher:** Not measured as a run. The docstring of split.py says that a
  wider inset starts to remove margins. At 32, the median white before the
  nearest ink is 247 px, and the smallest is 22 px, on page 74.

### `search_fraction = 0.12`

The stage looks for the gutter within this share of the width either side of
the centre.

- **Lower:** Not measured. The gutter centre is at most 104 px from the middle
  of the image, 1.8 percent of the width, and 16 px at the median.
- **Higher:** At 0.40, with no smoothing, the stage finds the same band on all
  76 pages.

### `smooth_width = 16`

The width of the box filter over the column ink profile.

- **Lower:** Any width from 1 to 45 px moves no gutter centre by more than
  3 px. With no smoothing and a window of 0.40, the band is the same on all 76
  pages.
- **Higher:** At 60 the title page breaks. Its band grows from 24 px to 377 px
  and its centre moves 496 px. A wider filter also widens every band, and the
  split removes the band: the title page band is 24 px at 16 and 34 px at 30.
- **Measured:** The smoothing keeps the printed column rules low. At 16 px the
  rule measured on page 76 falls to 0.30 ink, against 1.00 for the fold.

## `[drop-blank]`

Module: `src/recto/stages/blank.py`.

### `max_ink = 0.01`

A page with this share of ink or less is blank, and the stage skips it.

- **Measured:** The blank pages of the sample measure 0.25 to 0.42 percent. The
  sparsest printed page measures 5.51 percent. A kept blank page costs one junk
  image. A dropped printed page loses text. So the default is 2.5 times the
  inkiest blank and 5.5 times under the sparsest printed page.
- **Lower, higher:** Not measured.

### `edge_area = 2000`

A component of this area or more that touches the frame is fold residue, and
the stage does not count its ink.

- **Measured:** The largest piece of real type on these pages is a drop cap of
  about 1,200 px. This trim takes the blank page 11 verso from 1.55 percent to
  0.42 percent. Printed pages lose 0.05 percentage points or less.
- **Lower, higher:** Not measured.

## `[deskew]`

Module: `src/recto/stages/deskew.py`.

### `search = 4.5`

The widest angle tried, either side of straight.

- **Lower:** At 3.0, the estimate is the same on all 555 page frames of the
  four parts, apart from part 2 p69 to p71 recto, which lean up to +3.15.
- **Higher:** Not measured. The coarse pass is 37 rotations at 4.5 and 25 at
  3.0.
- **Keep:** `search` a multiple of `coarse`, and at least one coarse step past
  `cap`. A page that leans past the search comes back as the edge value. That
  edge must be past the cap, so the page is refused and not turned by the
  wrong angle.

### `coarse = 0.25`

The step of the first pass.

- **Lower, higher:** Not measured.

### `fine = 0.05`

The step of the second pass, over one coarse step either side of the best
coarse angle.

- **Lower, higher:** Not measured.

### `cap = 4.0`

The stage refuses an estimate past this angle, and leaves the page as it is.

- **Lower:** At 2.5 the stage refused part 2 p69, p70 and p71 recto. They lean
  +2.75, +2.75 and +3.15, and those estimates are correct. Left tilted, two to
  four of their lines merge into one band.
- **Higher:** Not measured. With a 6 degree search, no page of the four parts
  comes back past 3.15. On the title page and the Index rerum opening, the best
  angle past 3.5 scores 12 and 13 percent under the true peak.

### `deadband = 0.05`

The stage does not turn a page whose estimate is under this angle.

- **Measured:** It is equal to `fine`, which is the smallest angle that the
  search can resolve.
- **Lower, higher:** Not measured.

### `score_dpi = 150`

The resolution at which the stage scores each angle.

- **Lower:** At a quarter of full resolution the angle drifts, by up to 0.45
  degrees on the catalogue page.
- **Higher:** At full resolution, the angle is at most 0.10 degrees from the
  angle at 150, over a dozen halves. Each estimate takes three times as long.

## `[mask-figures]`

Module: `src/recto/stages/figures.py`. A component is a figure only when it
passes all five tests below. Each test was measured on 48 hand labelled
components over 15,000 px on eleven pages, then checked on the full volume.

### `min_area = 15000`

The smallest component that the stage considers.

- **Measured:** The smallest real figure is the decorated V on page 1, at
  20,592 px. Under 15,000 there is no figure, only pieces of figures.
- **Lower, higher:** Not measured.

### `max_aspect = 16.0`

A component with a longer side over a shorter side above this is a rule, not a
figure.

- **Measured:** The printed column rules measure 33 or more. No figure measures
  over 8. The rules must stay, for the column split.
- **Lower, higher:** Not measured.

### `min_holes = 40`

A figure must enclose at least this many white regions, because hatching holds
white.

- **Measured:** The smallest figure has 59 holes, and the title woodcut 5,570.
  The display capitals on the title page have 6 to 25.
- **Lower, higher:** Not measured.

### `max_row_variation = 0.35`

A component whose row ink varies more than this inside its box is text.

- **Measured:** Figures measure 0.06 to 0.30. Fused text measures 0.41 to 0.52.
- **Lower, higher:** Not measured.

### `max_line_pitch = 0.42`

A component whose row ink repeats at the line pitch more than this is text.

- **Measured:** Figures measure 0.05 to 0.36. Fused blocks tall enough to hold
  three lines measure 0.47 to 0.84. The fused block on page 12 measures 0.84.
- **Lower, higher:** Not measured.

### `pitch_range = [35, 75]`

The lags, in pixels, at which the stage looks for a line pitch. Give two
integers.

- **Lower, higher:** Not measured.

### `body_fraction = 0.2`

The stage trims each figure box until its edge line holds this share of the
median line ink of the figure.

- **Lower:** 0.15 is the first level at which no piece of type loses ink. Under
  0.15, welded letter tops keep the box edge in the type below the figure.
- **Higher:** Not measured. At 0.20, at most 0.75 percent of a figure's ink
  stays outside its box as slivers.

### `edge_trim = 0.1`

The share of rows at the top and the bottom of a box that the row variation
and line pitch tests ignore, because an ornament's outline tapers there.

- **Lower, higher:** Not measured.

## `[bands]`

Module: `src/recto/stages/bands.py`, the `Tuning` dataclass.

### `letter_area = 90`

The smallest component that banding counts as type.

- **Measured:** On page 9, components of 90 px and more are letters, and
  smaller ones are punctuation and speckle. Letters only removed 85 percent of
  the bands with a run under 20 px. Full lines stayed nearly the same, 19,582
  against 19,637.
- **Lower, higher:** Not measured.

### `stroke_aspect = 4.0`

A component taller than two pitches and this many times taller than wide is a
stroke, not type. Banding ignores it.

- **Measured:** No letter has that shape. A stroke 357 px tall on p15 recto
  made bands under the catchword.
- **Lower, higher:** Not measured.

### `pitch = 48`

The body line pitch. The gap level is the lowest row within one pitch. Groups of
bands break at two pitches. Each half of the text block keeps half a pitch clear
of the middle and runs half a pitch past the outer edge. A stroke is taller than
two pitches.

- **Lower:** Groups break at two pitches, and that distance was measured at
  72 px, a pitch of 36. Real running heads separate from the text and are lost.
- **Higher:** At a group distance of 120 px, a pitch of 60, noise under the
  foot row starts to join the text.
- **Not measured:** The other uses of the pitch.

### `smooth = 5`

The width of the box filter over the row profile.

- **Lower:** With no smoothing, two lines of p12 recto merge. At 1 or 3 px the
  head splits on 13 halves, against 11 at 5.
- **Higher:** At 7 and 9 px, every count is as good as at 5. From 1 to 9 px, no
  noise band comes back and no foot row is lost.

### `peak_reach = 16`

How far either side of a row the stage looks for the peak of its line.

- **Lower:** At 12 the large type of the running head breaks into pieces on two
  times as many pages.
- **Higher:** At 20 the descenders of the last full line count as the peak of
  the catchword, and one of the ten checked catchwords is lost. At 24 two are
  lost, and two times as many heads split as at 16.

### `rise = 0.5`

How far from the gap level towards the peak a row must rise to be part of a
line.

- **Lower:** At 0.4 or 0.45, four lines of the dark, fused p12 recto merge into
  one band. At 0.4, three lines near the foot of the left half of p74 recto
  also merge.
- **Higher:** At 0.55 the head splits on 14 halves instead of 11, and at 0.6 on
  16.
- **Measured:** From 0.4 to 0.6, no noise band comes back and no foot row is
  lost.

### `merge_gap = 12`

Bands closer than this are one line.

- **Lower:** At 6 body lines start to split.
- **Higher:** Not measured. Over 17,306 gaps between body lines, the 1st
  percentile is 21 px.

### `sliver = 14`

A band shorter than this is a piece of a line. It folds into the nearest line
within `fold_reach`.

- **Lower, higher:** Not measured.

### `fold_reach = 30`

How far a sliver can be from the line that it folds into.

- **Lower, higher:** Not measured.

### `piece_height = 0.4`

A band under this share of the height of a neighbour can be a piece of that
neighbour.

- **Lower, higher:** Not measured.

### `piece_gap = 0.3`

That band is a piece when it is closer to the neighbour than this share of the
neighbour's height. This rule keeps the running head whole.

- **Lower:** Not measured.
- **Higher:** At 0.4 the first body line merges into the head on 48 of 260 half
  pages, and strip-head would remove it with the head.
- **Measured:** The first body line is usually 37 to 40 px under a head of 80
  to 110 px.

### `min_run = 30`

A band is text only if its letters hold a horizontal run of this length, about
two letters.

- **Lower:** At 20, nine of the 27 labelled noise bands come back.
- **Higher:** At 40, five of the ten catchwords are lost.
- **Measured:** The shortest real foot row is the signature C 3, at 35 px. A
  catchword narrower than 30 px is lost.

### `bridge = 10`

Gaps narrower than this do not break a run.

- **Lower:** Without bridging, a catchword such as "in" is two runs of one
  letter each.
- **Higher:** Not measured.

### `full_run = 100`

The run of a full line. A group of bands is text only when it holds at least
two bands, and one of them has this run.

- **Lower, higher:** Not measured.

### `block_fraction = 0.25`

The text block is the widest run of pixel columns that hold at least this share
of the 95th percentile column ink.

- **Lower, higher:** Not measured.

### `block_gap = 150`

Gaps narrower than this inside the text block are bridged. The gap between the
columns is the one that this bridges.

- **Measured:** The speckled strip down the outer edge of many rectos is always
  a few hundred px of near white away from the text, so it stays out.
- **Lower, higher:** Not measured.

## `[strip-head]`

Module: `src/recto/stages/furniture.py`, the running head.

### `head_min = 40`

The shortest band that can be the running head.

- **Lower:** At 30 the cut changes on two front matter pages.
- **Higher:** At 50 the cut changes on fourteen pages. Most are index pages,
  whose heads are smaller and band at 45 to 50 px.

### `line_min = 18`

The shortest band that is a line of body text.

- **Lower, higher:** At 15 or 21 the cut changes on two or three pages, in that
  order.

### `line_max = 35`

The tallest band that is a line of body text.

- **Lower, higher:** From 30 to 40, no cut changes.

### `gap_max = 100`

The furthest that the first body line can be under the head.

- **Lower:** At 70 the cut changes on four pages, and at 60 on thirty-one.
- **Higher:** Not measured.
- **Measured:** The gap is 22 to 87 px on the body pages of part 1, and under
  80 px for 99 percent of heads in the four parts.

### `piece = 30`

Pieces of one head are no further apart than this.

- **Lower, higher:** At 20 or 40, the cut changes on p18 recto or on two index
  pages, in that order.

### `head_tall = 150`

When the head band is this tall in both halves, it holds the first body line,
and the cut moves up into the white above that line.

- **Measured:** Over 539 frames with a head, the shorter of the two head spans
  is at most 140 px. On part 4 p4, p12 and p22 recto, where the head and the
  first line band together, it is 159 to 164 px.
- **Lower, higher:** Not measured.

## `[strip-foot]`

Module: `src/recto/stages/furniture.py`, the foot row.

### `column_wide = 600`

A band wider than this is a full line. The median left edge of these bands is
the column edge.

- **Lower, higher:** From 500 to 700, no cut changes.

### `start = 300`

The width, from the column edge, in which letter ink tells a text line from the
foot row.

- **Lower:** At 200, four frames change.
- **Higher:** At 400, two frames change.

### `start_ink = 0.05`

A band with this share of letter ink in the first `start` pixels is a text
line.

- **Lower:** At 0.03, three frames change.
- **Higher:** At 0.08, four frames change.

### `line_depth = 35`

The foot cut stays at least this far under the top of each line above it.

- **Lower, higher:** At 30 or 40 the cut moves 1 to 5 px on many pages. The cut
  never passes the edge of a band.

### `above = 20`

A band that starts this far over the foot row is a line above it.

- **Lower:** At 10, one frame changes.
- **Higher:** At 30, three frames change.

## `[split-columns]`

Module: `src/recto/stages/columns.py`.

### `reach = 150`

The furthest that the cut can be from the middle of the text block.

- **Lower:** At 100, only part 3 p37 recto changes.
- **Higher:** At 200, nothing changes.

### `clear = 6`

A line crosses the cut when letter ink is this near to the cut. This is the
tightest constant of the stage.

- **Lower:** At 4, three title blocks change and 12 cuts move more than 10 px.
- **Higher:** At 8, seven cuts in part 4 move.

### `slant = 0.04`

The largest slant of the cut, in pixels across for each pixel down.

- **Lower:** At 0.03, only part 3 p37 recto changes.
- **Higher:** At 0.05, nothing changes.
- **Measured:** On In Apocalypsim, one column leans against the other by up to
  30 px for each 1,000 rows.

### `slant_step = 0.002`

The step between the slants that the search tries.

- **Lower:** At 0.001, three cuts move more than 10 px.
- **Higher:** Not measured.

### `split_max = 0.3`

Above this share of crossed lines, the page is one column.

- **Lower:** At 0.2, only part 3 p37 recto changes.
- **Higher:** At 0.4, nothing changes.
- **Measured:** Two-column pages measure 0.17 or less. Single-column pages
  measure 0.41 or more.

### `title_first = 4`

A title block must start in one of this many first lines.

- **Lower, higher:** Not measured.

### `title_tall = 40`

The shortest crossing line that starts a title block.

- **Measured:** A tall line is necessary. On some In Apocalypsim pages the cut
  touches the ends of the first body lines, and those lines are body size.
- **Lower, higher:** Not measured.

### `title_clean = 8`

This many lines in a row that do not cross the cut end a title block.

- **Lower, higher:** Not measured.

## `[whole]`

Module: `src/recto/stages/whole.py`. A letter that a cut touches goes whole to
the side that it reaches further into.

### `tallest = 60`

The tallest component that a cut keeps whole. A cut goes straight through a
taller one.

- **Measured:** Most letters that a cut touches are under 60 px. Single fused
  words measure 61 to 69 px, and two fused lines 74 to 77 px. A fused piece
  that moves whole takes text with it.
- **Lower, higher:** Not measured.

### `widest = 300`

How far the window round the column gap reaches on each side.

- **Measured:** Of the 472 components that touch the gap in the four parts,
  99 percent are under 190 px wide. Three are 350 to 870 px wide, all fused
  text on speckled pages, and stay as the gap leaves them.
- **Lower, higher:** Not measured.

### `upright = 2.0`

At the column gap, a component this many times taller than wide is a piece of
the rule. The stage leaves it as the cut leaves it.

- **Measured:** 222 thin upright pieces touch the gap in the four parts. Of 48
  sampled, 47 were the rule and one was a bracket.
- **Lower, higher:** Not measured.
