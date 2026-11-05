"""Command-line entry point.

Subcommands are registered here as the pipeline grows. Each one stays a thin
wrapper: argument parsing and human-readable output live here, and the work
itself lives in the module the command calls, so every stage stays testable
without going through click.
"""

from __future__ import annotations

import time
from pathlib import Path

import click
import pypdfium2 as pdfium

from recto import __version__
from recto.config import ProfileError, load_profile
from recto.debug import DEFAULT_DEBUG_DIR, DebugWriter, draw_overlay
from recto.frames import Frame, Provenance
from recto.manifest import DEFAULT_OUT_DIR, ManifestWriter
from recto.pngio import write_png
from recto.pipeline import Observers, Pipeline, StageError
from recto.raster import (
    DEFAULT_CACHE,
    DEFAULT_DPI,
    native_dpi,
    parse_page_range,
    rasterise,
)
from recto.stages.blank import DropBlank
from recto.sheet import write_sheet
from recto.stages.registry import default_stages

# Accept -h as well as --help. Click only accepts --help by default, and
# reaching for -h out of habit and getting an error gets old quickly.
CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__, "-V", "--version", prog_name="recto")
def main() -> None:
    """Clean scanned book spreads into OCR-ready column images.

    Recto reads a scanned PDF whose page images each hold a two-page spread,
    cuts each spread at the gutter, straightens and cleans the two pages, then
    writes one image per text column together with a manifest recording the
    source page, side, and column index of every image it produced.
    """


@main.command("raster")
@click.argument(
    "pdf",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
)
@click.option(
    "--pages",
    metavar="RANGE",
    default=None,
    help=(
        "Pages to render, one-based and inclusive: 9, or 8-10, or 1,4,7-9. "
        "Defaults to every page."
    ),
)
@click.option(
    "--dpi",
    type=click.IntRange(72, 1200),
    default=DEFAULT_DPI,
    show_default=True,
    help="Render resolution.",
)
@click.option(
    "--out",
    "out_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_CACHE,
    show_default=True,
    help="Cache directory for rendered pages.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Re-render pages that are already cached.",
)
def raster_command(
    pdf: Path,
    pages: str | None,
    dpi: int,
    out_dir: Path,
    force: bool,
) -> None:
    """Render pages of a scanned PDF to greyscale PNGs.

    Rendered pages are cached, so running this a second time over the same
    pages costs a disk read rather than a re-render.
    """
    _warn_if_upsampling(pdf, dpi)

    written = 0
    try:
        for page in rasterise(pdf, pages=pages, dpi=dpi, out_dir=out_dir, force=force):
            height, width = page.image.shape
            click.echo(f"p{page.number:<5} {width:>5} x {height:<5}  {page.path}")
            written += 1
    except ValueError as exc:
        # parse_page_range raises ValueError for anything wrong with --pages.
        raise click.BadParameter(str(exc), param_hint="--pages") from exc

    click.echo(f"{written} page(s) under {out_dir}")


@main.command("run")
@click.argument(
    "pdf",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
)
@click.option(
    "--pages",
    metavar="RANGE",
    default=None,
    help=(
        "Pages to process, one-based and inclusive: 9, or 8-10, or 1,4,7-9. "
        "Defaults to every page."
    ),
)
@click.option(
    "--dpi",
    type=click.IntRange(72, 1200),
    default=DEFAULT_DPI,
    show_default=True,
    help="Render resolution.",
)
@click.option(
    "--cache",
    "cache_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_CACHE,
    show_default=True,
    help="Cache directory for rendered pages.",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Write one overlay image per stage showing what that stage found.",
)
@click.option(
    "--debug-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_DEBUG_DIR,
    show_default=True,
    help="Where debug overlays are written.",
)
@click.option(
    "--out",
    "out_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_OUT_DIR,
    show_default=True,
    help=(
        "Where column images and manifest.jsonl are written, in a folder "
        "named after the PDF. A manifest from an earlier run is replaced."
    ),
)
@click.option(
    "--resume",
    is_flag=True,
    help=(
        "Keep the pages that an earlier run finished and do only the rest. "
        "Pages that failed are done again. Use the same --dpi and --profile."
    ),
)
@click.option(
    "--profile",
    "profile_path",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=None,
    help=(
        "TOML file with the stage constants for a book. "
        "Without it, the values measured on the Jammy edition apply."
    ),
)
def run_command(
    pdf: Path,
    pages: str | None,
    dpi: int,
    cache_dir: Path,
    debug: bool,
    debug_dir: Path,
    out_dir: Path,
    resume: bool,
    profile_path: Path | None,
) -> None:
    """Run the processing pipeline over the selected pages.

    Each page starts as one frame holding the whole spread. Stages narrow it,
    so the frame count reported per page grows as splitting stages are added
    and shrinks when a page turns out to be blank.

    Each column frame is written as a PNG, with one row in manifest.jsonl that
    names its page, side and column and what each stage did to it. If a stage
    fails on a page, the page gets an error row, the run goes on, and the
    command exits with status 1 at the end.
    """
    try:
        profile = load_profile(profile_path) if profile_path is not None else None
    except ProfileError as exc:
        raise click.BadParameter(str(exc), param_hint="--profile") from exc
    pipeline = Pipeline(default_stages(profile))
    writer = DebugWriter(root=debug_dir) if debug else None
    blank = next((s for s in pipeline.stages if isinstance(s, DropBlank)), None)
    manifest = ManifestWriter(
        directory=out_dir / pdf.stem, blank=blank, resume=resume
    )
    observer = Observers([manifest] if writer is None else [manifest, writer])

    selected = _selected_pages(pdf, pages)
    produced = 0
    started = time.monotonic()
    with manifest:
        # Finished pages are taken out before rendering, so a resumed run does
        # not read their cached images again.
        todo = [index for index in selected if index + 1 not in manifest.done]
        if resume:
            click.echo(
                f"resume: {len(selected) - len(todo)} page(s) already done "
                f"in {manifest.path}, {len(todo)} to do"
            )
        # rasterise takes one-based page numbers, as --pages does.
        spec = ",".join(str(index + 1) for index in todo)
        # An empty spec would mean every page, so no pages to do means no call.
        rendered = (
            rasterise(pdf, pages=spec, dpi=dpi, out_dir=cache_dir) if todo else []
        )
        for count, page in enumerate(rendered, start=1):
            frame = Frame(
                image=page.image,
                provenance=Provenance(source=pdf, page_index=page.index, dpi=dpi),
            )
            tick = time.monotonic()
            try:
                results = pipeline.run(frame, observer=observer)
            except StageError as exc:
                # One bad page must not stop a run of hundreds. The error row
                # keeps the message, and --resume does the page again.
                manifest.page_failed(frame.provenance, str(exc))
                click.echo(f"p{page.number:<5} FAILED: {exc}", err=True)
                continue
            manifest.page_done(results)
            produced += len(results)
            click.echo(
                f"p{page.number:<5} {len(results)} frame(s) out  "
                f"[{count}/{len(todo)}, {time.monotonic() - tick:.1f} s]"
            )

    click.echo(
        f"{produced} frame(s) from {len(pipeline.stages)} stage(s) "
        f"in {time.monotonic() - started:.0f} s"
    )
    click.echo(
        f"{manifest.images} image(s) and {manifest.rows} manifest row(s) "
        f"written under {manifest.directory}"
    )
    if manifest.failed:
        click.echo(
            f"{manifest.failed} page(s) failed. Their rows in {manifest.path} "
            "give the error. Run again with --resume to do them again.",
            err=True,
        )
        raise SystemExit(1)
    if writer is not None:
        click.echo(f"{len(writer.written)} overlay(s) under {debug_dir}")


@main.command("debug")
@click.argument(
    "pdf",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
)
@click.option(
    "--page",
    type=click.IntRange(min=1),
    required=True,
    help="The page to show, one-based, as a PDF viewer numbers it.",
)
@click.option(
    "--dpi",
    type=click.IntRange(72, 1200),
    default=DEFAULT_DPI,
    show_default=True,
    help="Render resolution.",
)
@click.option(
    "--cache",
    "cache_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_CACHE,
    show_default=True,
    help="Cache directory for rendered pages.",
)
@click.option(
    "--debug-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_DEBUG_DIR,
    show_default=True,
    help="Where the overlays and the HTML page are written.",
)
@click.option(
    "--profile",
    "profile_path",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=None,
    help=(
        "TOML file with the stage constants for a book. "
        "Without it, the values measured on the Jammy edition apply."
    ),
)
@click.option(
    "--no-open",
    is_flag=True,
    help="Write the HTML page but do not open it in the browser.",
)
def debug_command(
    pdf: Path,
    page: int,
    dpi: int,
    cache_dir: Path,
    debug_dir: Path,
    profile_path: Path | None,
    no_open: bool,
) -> None:
    """Show every stage of one spread on one HTML page.

    Runs the pipeline over one page with overlays on, then writes an HTML page
    beside the overlays that shows the spread stages, the verso and the recto
    next to each other stage by stage, and the frames that came out. Column
    images and the manifest are not written.
    """
    try:
        profile = load_profile(profile_path) if profile_path is not None else None
    except ProfileError as exc:
        raise click.BadParameter(str(exc), param_hint="--profile") from exc
    (index,) = _selected_pages(pdf, str(page), hint="--page")
    pipeline = Pipeline(default_stages(profile))
    writer = DebugWriter(root=debug_dir)

    (raster,) = rasterise(pdf, pages=str(page), dpi=dpi, out_dir=cache_dir)
    frame = Frame(
        image=raster.image,
        provenance=Provenance(source=pdf, page_index=index, dpi=dpi),
    )
    folder = debug_dir / pdf.stem
    error = None
    results: list[Frame] = []
    try:
        results = pipeline.run(frame, observer=writer)
    except StageError as exc:
        # The overlays written before the failure are what shows where the page
        # went wrong, so the sheet is still written.
        error = str(exc)

    outputs = []
    for result in results:
        label = result.provenance.label
        picture = draw_overlay(
            result.image,
            [],
            captions=(f"out {label}", f"{result.width}x{result.height}"),
            max_width=writer.max_width,
        )
        path = folder / f"{label}.png"
        write_png(path, picture)
        outputs.append(path)

    sheet = write_sheet(
        folder / f"{frame.provenance.label}.html",
        title=f"{pdf.name}, page {page}",
        spread=frame.provenance.label,
        overlays=writer.written,
        outputs=outputs,
        error=error,
    )
    click.echo(f"{len(writer.written)} overlay(s) and {len(outputs)} frame(s) out")
    click.echo(f"contact sheet: {sheet}")
    if not no_open:
        click.launch(str(sheet.resolve()))
    if error is not None:
        click.echo(f"FAILED: {error}", err=True)
        raise SystemExit(1)


def _selected_pages(
    source: Path, pages: str | None, hint: str = "--pages"
) -> list[int]:
    """Give the zero-based indices of the pages that a page option selects.

    Args:
        source: The PDF.
        pages: The option value, or None for every page.
        hint: The option name to give in an error message.

    Returns:
        The indices, sorted.

    Raises:
        click.BadParameter: If the value is not valid for this PDF.
    """
    pdf = pdfium.PdfDocument(source)
    try:
        count = len(pdf)
    finally:
        pdf.close()
    if pages is None:
        return list(range(count))
    try:
        return parse_page_range(pages, count)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint=hint) from exc


def _warn_if_upsampling(source: Path, dpi: int) -> None:
    """Say something when the requested resolution exceeds the scan's own.

    Rendering a 300 dpi scan at 600 dpi cannot recover detail that was never
    captured. It quadruples the file and softens every glyph edge, which makes
    the connected-component stages later on measurably worse. Worth a note
    rather than an error, since there are reasons to upsample deliberately.
    """
    pdf = pdfium.PdfDocument(source)
    try:
        native = native_dpi(pdf[0])
    finally:
        pdf.close()

    if native is None or dpi <= native * 1.05:
        return

    click.echo(
        f"note: the scan on page 1 is about {native:.0f} dpi, and you asked for "
        f"{dpi}. Rendering above the native resolution adds size, not detail.",
        err=True,
    )


if __name__ == "__main__":
    main()
