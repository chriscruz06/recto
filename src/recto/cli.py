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
from recto.raster import DEFAULT_CACHE, DEFAULT_DPI, native_dpi, rasterise

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
