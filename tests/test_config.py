"""Cover for profiles: loading, checking, and reaching the stages.

The shipped profile sets every value to its default in the code. These tests
keep the two the same. If a stage gets a new constant, or a default changes,
the profile must change with it, or a test here fails.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from conftest import pages_of, spread
from recto.config import ProfileError, defaults, load_profile
from recto.frames import RECTO
from recto.stages.registry import default_stages

JAMMY = Path(__file__).parent.parent / "profiles" / "jammy-1651.toml"


def written(text: str) -> Path:
    """Write a profile to a new temporary file.

    Args:
        text: The TOML text.

    Returns:
        The path of the file. The operating system removes it later.
    """
    folder = Path(tempfile.mkdtemp())
    path = folder / "profile.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_shipped_profile_sets_every_default() -> None:
    """Check that the Jammy profile names every key, at its value in the code."""
    assert load_profile(JAMMY).values == defaults()


def test_no_profile_keeps_the_defaults() -> None:
    """Check that the stages without a profile have the same values as with it."""
    plain = default_stages()
    jammy = default_stages(load_profile(JAMMY))
    for a, b in zip(plain, jammy):
        assert vars(a) == vars(b), a.name


def test_profile_values_reach_the_stages() -> None:
    """Check that a value in each kind of section gets to its stage."""
    profile = load_profile(
        written(
            "[deskew]\ncap = 1\n"
            "[split-spread]\nsmooth_width = 20\n"
            "[bands]\npitch = 50\n"
            "[whole]\ntallest = 70\nwidest = 200\n"
        )
    )
    stages = {stage.name: stage for stage in default_stages(profile)}

    assert stages["deskew"].cap == 1.0
    assert stages["split-spread"].smooth_width == 20
    for name in ("band-lines", "strip-head", "strip-foot", "split-columns"):
        assert stages[name].tuning.pitch == 50, name
    assert stages["strip-head"].tallest == 70
    assert stages["strip-foot"].tallest == 70
    assert stages["split-columns"].tallest == 70
    assert stages["split-columns"].widest == 200


def test_profile_changes_what_a_stage_does() -> None:
    """Check that a profile value changes the result, not only an attribute.

    p74 recto needs a correction of about 1.2 degrees. With a cap of 0.5 from
    the profile, deskew must refuse it, as test_deskew does with the argument.
    """
    profile = load_profile(written("[deskew]\ncap = 0.5\n"))
    deskew = {stage.name: stage for stage in default_stages(profile)}["deskew"]
    frame = pages_of(spread(74))[RECTO]

    output = deskew.apply(frame)
    assert output.frames == [frame]
    assert "cap" in output.summary


@pytest.mark.parametrize(
    "text, words",
    [
        ("[deskwe]\ncap = 1.0\n", "no section [deskwe]"),
        ("[deskew]\ncapp = 1.0\n", "has no key capp"),
        ("[deskew]\ncap = \"1\"\n", "must be float"),
        ("[deskew]\nscore_dpi = 150.5\n", "must be int"),
        ("[deskew]\nscore_dpi = true\n", "must be int"),
        ("[split-spread]\nsingle = 1\n", "must be bool"),
        ("[split-spread]\nodd_side = 1\n", "must be str"),
        ("[mask-figures]\npitch_range = [35]\n", "must be tuple[int, int]"),
        ("deskew = 1\n", "must be a [deskew] table"),
        ("[deskew\n", "not valid TOML"),
    ],
)
def test_bad_profile_is_refused(text: str, words: str) -> None:
    """Check that a mistake in a profile stops the run with a clear message.

    Args:
        text: The TOML text of the profile.
        words: Words the error message must hold.
    """
    with pytest.raises(ProfileError, match=words.replace("[", r"\[")):
        load_profile(written(text))


def test_single_page_keys_reach_the_split() -> None:
    """Check that the bool and str keys of split-spread are read and passed on."""
    profile = load_profile(written('[split-spread]\nsingle = true\nodd_side = "recto"\n'))
    split = {stage.name: stage for stage in default_stages(profile)}["split-spread"]
    assert split.single is True
    assert split.odd_side == "recto"
