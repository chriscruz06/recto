"""Command-line entry point.

Subcommands are registered here as the pipeline grows. For now this exists so
the package ships a working console script from the first commit, which keeps
every later commit testable by hand from the terminal.
"""

from __future__ import annotations

import click

from recto import __version__

# Accept -h as well as --help. The default click behaviour only accepts --help,
# and reaching for -h out of habit and getting an error gets old quickly.
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


if __name__ == "__main__":
    main()
