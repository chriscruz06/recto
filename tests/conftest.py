"""Loading the committed page fixtures.

One place that knows how a fixture filename is put together, so the tests can
say "give me the pages" and nothing else has to care that the dpi is encoded in
the name or that a fixture is a third of the size of the page it came from.

Fixtures are downsampled, so anything a test measures in fixture pixels means
nothing on its own. FixturePage.scale converts to source pixels at 300 dpi,
which is where the expected values in the tests are recorded and the only
coordinate system in which a tolerance can be compared against a measurement of
the real scan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from recto.frames import Frame, Provenance
from recto.pngio import read_png

FIXTURE_DIR = Path(__file__).parent / "fixtures"

SOURCE_DPI = 300
"""The resolution the scan is at, and the one expected values are recorded in."""

_FILENAME = re.compile(r"^p(\d{4})@(\d+)dpi\.png$")


@dataclass(frozen=True)
class FixturePage:
    """One committed page, and what is needed to read it in context."""

    path: Path
    page_number: int
    dpi: int

    @property
    def scale(self) -> float:
        """Source pixels per fixture pixel."""
        return SOURCE_DPI / self.dpi

    def to_source(self, pixels: float) -> int:
        """Convert a fixture measurement to source pixels at 300 dpi."""
        return round(pixels * self.scale)

    def frame(self) -> Frame:
        """A fresh frame holding this page.

        Fresh every time: stages return new frames but the pipeline appends to
        the history list in place, so handing the same Frame to two tests would
        let one test see the other's history.
        """
        return Frame(
            image=read_png(self.path),
            provenance=Provenance(
                source=self.path,
                page_index=self.page_number - 1,
                dpi=self.dpi,
            ),
        )

    def __str__(self) -> str:
        return f"p{self.page_number:04d}"


def load_fixtures() -> list[FixturePage]:
    """Every fixture on disk, in page order.

    A module-level function rather than only a pytest fixture, because
    parametrising a test over the pages needs them at collection time.
    """
    found = []
    for path in sorted(FIXTURE_DIR.glob("*.png")):
        match = _FILENAME.match(path.name)
        if match is None:
            raise ValueError(
                f"{path.name} is not a fixture name. Expected p0009@100dpi.png, "
                "which is what tests/make_fixtures.py writes."
            )
        found.append(
            FixturePage(path=path, page_number=int(match[1]), dpi=int(match[2]))
        )
    return found


@pytest.fixture(scope="session")
def fixture_pages() -> list[FixturePage]:
    """Every fixture on disk, for tests that want the whole set at once."""
    pages = load_fixtures()
    if not pages:
        pytest.skip(
            "no fixtures under tests/fixtures. "
            "Run: python tests/make_fixtures.py <path to the scan>"
        )
    return pages
