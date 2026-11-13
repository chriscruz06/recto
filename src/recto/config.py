"""Load a profile: the constants of the stages, for one book.

Every constant was measured on the Jammy edition of 1651, and the measurement
is in the docstring of its stage module. Another book needs other values. A
profile is a TOML file that sets them, so that a new book does not need a
change to the code.

The code keeps the defaults. A profile sets only the values that it names, and
the stages keep their defaults for all others. The defaults are the measured
values for Jammy, and profiles/jammy-1651.toml sets every value to its default,
so it shows each name and section that a new profile can use.

One section for each stage, named as the stage, for example [deskew] and
[strip-head]. The keys are the names of the constructor arguments of that
stage. Two sections are shared:

    [bands] holds the constants of bands.Tuning. Four stages band lines, and
    they must band them the same way, so these values go to all four.

    [whole] holds the limits of whole.whole_letters, for the head, foot and
    column cuts.

Some constructor arguments are not in a profile. REFERENCE_DPI and INK_BELOW
set the units in which the other values are given. Despeckle's max_findings
only sets how many specks the debug overlay draws.

TOML and not YAML, because Python reads TOML with tomllib from version 3.11, so
a profile adds no dependency.
"""

from __future__ import annotations

import inspect
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from recto.stages.bands import Tuning
from recto.stages.blank import DropBlank
from recto.stages.border import CropBorder
from recto.stages.columns import SplitColumns
from recto.stages.deskew import Deskew
from recto.stages.despeckle import Despeckle
from recto.stages.figures import MaskFigures
from recto.stages.furniture import StripFoot, StripHead
from recto.stages.split import SplitSpread

STAGES = (
    CropBorder,
    Despeckle,
    SplitSpread,
    DropBlank,
    Deskew,
    MaskFigures,
    StripHead,
    StripFoot,
    SplitColumns,
)
"""The stages that have a section of their own, in pipeline order."""

WHOLE = ("tallest", "widest", "upright")
"""The keys of the [whole] section."""

LEFT_OUT = {"reference_dpi", "ink_below", "max_findings", "skipped", "tuning", *WHOLE}
"""Constructor arguments that are not keys of a stage's own section."""


class ProfileError(ValueError):
    """A profile that cannot be read, or that sets a value the stages do not have."""


@dataclass(frozen=True)
class Profile:
    """The values that one profile sets, by section."""

    values: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Section name to key to value. Only the values that the file sets."""

    def section(self, name: str) -> dict[str, Any]:
        """Give the values that the profile sets in one section.

        Args:
            name: The section name, for example "deskew" or "bands".

        Returns:
            A new dict of key to value, empty if the profile sets none.
        """
        return dict(self.values.get(name, {}))


def _known() -> dict[str, dict[str, tuple[Any, str]]]:
    """Give every key that a profile can set, with its default and its type.

    Both come from the stages themselves, so a new constructor argument becomes
    a profile key with no change here.

    Returns:
        Section name to key to the default and the declared type, as written
        in the code, for example "float".
    """
    found: dict[str, dict[str, tuple[Any, str]]] = {}
    for stage in STAGES:
        found[stage.name] = {
            name: (parameter.default, str(parameter.annotation))
            for name, parameter in inspect.signature(stage).parameters.items()
            if name not in LEFT_OUT and parameter.default is not inspect.Parameter.empty
        }
    found["bands"] = {f.name: (f.default, str(f.type)) for f in fields(Tuning)}
    columns = inspect.signature(SplitColumns).parameters
    found["whole"] = {
        name: (columns[name].default, str(columns[name].annotation)) for name in WHOLE
    }
    return found


def defaults() -> dict[str, dict[str, Any]]:
    """Give every value that a profile can set, with its default in the code.

    Returns:
        Section name to key to default value.
    """
    return {
        section: {key: default for key, (default, _) in keys.items()}
        for section, keys in _known().items()
    }


def load_profile(path: Path) -> Profile:
    """Read a profile and check every value in it against the stages.

    Args:
        path: The TOML file.

    Returns:
        The profile.

    Raises:
        ProfileError: If the file cannot be read or is not TOML, or if it has
            a section or a key that the stages do not have, or a value of the
            wrong type.
    """
    try:
        with path.open("rb") as file:
            raw = tomllib.load(file)
    except OSError as error:
        raise ProfileError(f"cannot read profile {path}: {error}") from error
    except tomllib.TOMLDecodeError as error:
        raise ProfileError(f"profile {path} is not valid TOML: {error}") from error

    known = _known()
    values: dict[str, dict[str, Any]] = {}
    for section, table in raw.items():
        if section not in known:
            raise ProfileError(
                f"{path}: no section [{section}]. "
                f"The sections are: {', '.join(sorted(known))}"
            )
        if not isinstance(table, dict):
            raise ProfileError(f"{path}: {section} must be a [{section}] table")
        values[section] = {}
        for key, value in table.items():
            if key not in known[section]:
                raise ProfileError(
                    f"{path}: [{section}] has no key {key}. "
                    f"The keys are: {', '.join(sorted(known[section]))}"
                )
            values[section][key] = _checked(
                value, known[section][key][1], f"{path}: [{section}] {key}"
            )
    return Profile(values=values)


def _checked(value: Any, kind: str, where: str) -> Any:
    """Check that a value has the type the stage declares, and convert it.

    TOML has no tuples, and it writes a float with no point as an integer. So a
    list becomes a tuple, and an integer becomes a float where the stage takes
    a float.

    Args:
        value: The value read from the profile.
        kind: The declared type: "int", "float", "bool", "str" or
            "tuple[int, int]".
        where: The file, section and key, for the error message.

    Returns:
        The value, with the declared type.

    Raises:
        ProfileError: If the value does not have the declared type.
    """
    # bool is a subclass of int in Python, so it is refused by name.
    numbers = isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "float" and numbers:
        return float(value)
    if kind == "int" and numbers and isinstance(value, int):
        return value
    if kind == "bool" and isinstance(value, bool):
        return value
    if kind == "str" and isinstance(value, str):
        return value
    if kind == "tuple[int, int]" and isinstance(value, list) and len(value) == 2:
        if all(isinstance(v, int) and not isinstance(v, bool) for v in value):
            return tuple(value)
    raise ProfileError(f"{where} must be {kind}, not {value!r}")
