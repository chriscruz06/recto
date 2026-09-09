"""The processing stages, and the order they run in.

Stages are registered in default_stages below as they get written. That order
is the runtime order, which is deliberately not the order the commits arrive
in: the build works outward from the most visible result, while the runtime
order is fixed by what each stage needs its input to already be.
"""

from __future__ import annotations

from recto.pipeline import Stage
from recto.stages.despeckle import Despeckle
from recto.stages.probe import Probe

__all__ = ["Despeckle", "Probe", "default_stages"]


def default_stages() -> list[Stage]:
    """Build the pipeline as it currently stands."""
    return [Probe(), Despeckle()]
