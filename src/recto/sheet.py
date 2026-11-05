"""Write one HTML page that shows every stage overlay of one spread.

The debug overlays of one page are 17 PNGs in three folders, one for the
spread and one for each side. Tuning means looking at them in order and
comparing the verso with the recto at the same stage. In a file browser that
is slow. This page puts them in one scroll: the spread stages first, then the
two sides next to each other, one row for each stage, then the frames that
came out of the last stage.

The page links to the PNGs and does not hold them. One page of overlays is
about 59 MB, and in the HTML file as base64 it would be about 80 MB. So the
page is written into the debug folder of its PDF, beside the overlay folders,
and the links are relative. Moving the HTML file alone breaks the images.

The page shows only the overlays that this run wrote. Overlays that an earlier
run left in the same folders, for example from a stage that was removed, do
not appear.
"""

from __future__ import annotations

import html
import os
from pathlib import Path

STYLE = """
:root { color-scheme: dark; }
body { margin: 0; background: #1e1e1e; color: #e6e6e6;
       font: 15px/1.5 system-ui, sans-serif; }
main { padding: 16px; max-width: 1600px; margin: 0 auto; }
h1 { font-size: 20px; margin: 0 0 4px; }
h2 { font-size: 16px; margin: 28px 0 8px; color: #9fd3d9; }
p.note { color: #b0b0b0; margin: 0; }
p.error { color: #ffb3b3; background: #3a1f1f; padding: 8px 12px; }
.grid { display: grid; gap: 12px;
        grid-template-columns: repeat(auto-fill, minmax(min(100%, 460px), 1fr)); }
.pair { display: grid; gap: 12px; grid-template-columns: 1fr 1fr; }
.side { font-weight: 600; }
figure { margin: 0; background: #2a2a2a; padding: 6px; }
figure img { display: block; width: 100%; height: auto; }
figcaption { font-size: 13px; color: #c8c8c8; padding-top: 4px; }
.empty { color: #8a8a8a; font-style: italic; padding: 12px; background: #262626; }
@media (max-width: 700px) { .pair { grid-template-columns: 1fr; } }
"""


def _figure(image: Path, page: Path, caption: str) -> str:
    """Make the HTML for one image that links to its full size file.

    Args:
        image: The PNG file.
        page: The HTML file that will show it, for the relative link.
        caption: The text under the image.

    Returns:
        A figure element.
    """
    link = html.escape(Path(os.path.relpath(image, page.parent)).as_posix())
    return (
        f'<figure><a href="{link}"><img src="{link}" loading="lazy" '
        f'alt="{html.escape(caption)}"></a>'
        f"<figcaption>{html.escape(caption)}</figcaption></figure>"
    )


def _stage_of(overlay: Path) -> tuple[int, str]:
    """Read the stage order and name from an overlay file name.

    Args:
        overlay: A path such as p0009-recto/05_deskew.png.

    Returns:
        The order and the stage name, for example (5, "deskew").
    """
    order, _, name = overlay.stem.partition("_")
    return int(order), name


def write_sheet(
    path: Path,
    *,
    title: str,
    spread: str,
    overlays: list[Path],
    outputs: list[Path],
    error: str | None = None,
) -> Path:
    """Write the contact sheet of one spread.

    Args:
        path: The HTML file to write. Its folder must hold, or be above, the
            overlay folders, so that the relative links work.
        title: The heading, for example "part1.pdf, page 9".
        spread: The frame label of the spread, for example p0009. Overlays in
            the folder of that name go in the spread section.
        overlays: The overlay files that this run wrote, in the order written.
        outputs: Pictures of the frames that came out of the pipeline.
        error: The message of a stage that failed, or None.

    Returns:
        The path of the HTML file.

    Raises:
        OSError: If the file cannot be written.
    """
    groups: dict[str, list[Path]] = {}
    for overlay in overlays:
        groups.setdefault(overlay.parent.name, []).append(overlay)

    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{html.escape(title)}</title><style>{STYLE}</style></head>",
        f"<body><main><h1>{html.escape(title)}</h1>",
        '<p class="note">Each overlay shows the frame a stage was given, with '
        "what it found drawn on top and its summary in the caption. Click an "
        "image for its full size.</p>",
    ]
    if error is not None:
        parts.append(f'<p class="error">Stopped: {html.escape(error)}</p>')

    parts.append("<h2>Spread</h2>")
    own = groups.pop(spread, [])
    if own:
        parts.append('<div class="grid">')
        for overlay in own:
            order, name = _stage_of(overlay)
            parts.append(_figure(overlay, path, f"{order:02d} {name}"))
        parts.append("</div>")
    else:
        parts.append('<p class="empty">No overlay of the spread was written.</p>')

    # Pages: one row for each stage, with the sides next to each other. A side
    # that drop-blank removed has no overlay after it, so its cell says so.
    sides = list(groups)
    if sides:
        parts.append("<h2>Pages</h2>")
        stages: dict[int, str] = {}
        for side in sides:
            for overlay in groups[side]:
                order, name = _stage_of(overlay)
                stages.setdefault(order, name)
        layout = "pair" if len(sides) == 2 else "grid"
        parts.append(f'<div class="{layout}">')
        parts.extend(f'<div class="side">{html.escape(side)}</div>' for side in sides)
        for order in sorted(stages):
            for side in sides:
                found = [o for o in groups[side] if _stage_of(o)[0] == order]
                if found:
                    caption = f"{order:02d} {stages[order]}, {side}"
                    parts.append(_figure(found[0], path, caption))
                else:
                    parts.append(
                        f'<div class="empty">{order:02d} {html.escape(stages[order])}'
                        ": no frame reached this stage.</div>"
                    )
        parts.append("</div>")

    parts.append("<h2>Frames out</h2>")
    if outputs:
        parts.append('<div class="grid">')
        for output in outputs:
            parts.append(_figure(output, path, output.stem))
        parts.append("</div>")
    else:
        parts.append('<p class="empty">No frame came out of the pipeline.</p>')

    parts.append("</main></body></html>\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")
    return path
