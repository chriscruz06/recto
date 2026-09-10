"""Command-line entry point.

Subcommands are registered here as the pipeline grows. Each one stays a thin
wrapper: argument parsing and human-readable output live here, and the work
itself lives in the module the command calls, so every stage stays testable
without going through click.
"""

from __future__ import annotations

from pathlib import Path

import click
import pypdfium2 as pdfium

from recto import __version__
from recto.debug import DEFAULT_DEBUG_DIR, DebugWriter
from recto.frames import Frame, Provenance
from recto.pipeline import Pipeline
from recto.raster import DEFAULT_CACHE, DEFAULT_DPI, native_dpi, rasterise
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
def run_command(
    pdf: Path,
    pages: str | None,
    dpi: int,
    cache_dir: Path,
    debug: bool,
    debug_dir: Path,
) -> None:
    """Run the processing pipeline over the selected pages.

    Each page starts as one frame holding the whole spread. Stages narrow it,
    so the frame count reported per page grows as splitting stages are added
    and shrinks when a page turns out to be blank.
    """
    pipeline = Pipeline(default_stages())
    writer = DebugWriter(root=debug_dir) if debug else None

    produced = 0
    try:
        for page in rasterise(pdf, pages=pages, dpi=dpi, out_dir=cache_dir):
            frame = Frame(
                image=page.image,
                provenance=Provenance(source=pdf, page_index=page.index, dpi=dpi),
            )
            results = pipeline.run(frame, observer=writer)
            click.echo(f"p{page.number:<5} {len(results)} frame(s) out")
            produced += len(results)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="--pages") from exc

    click.echo(f"{produced} frame(s) from {len(pipeline.stages)} stage(s)")
    if writer is not None:
        click.echo(f"{len(writer.written)} overlay(s) under {debug_dir}")


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
