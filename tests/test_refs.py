"""The branch each side is compared at has to come from one place.

RAVEN's default branch is `main` while the ledger describes `develop3`. Two
workflows need that fact, and if each states it for itself, one of them will
eventually be wrong and nobody will notice --- the run still passes, it just
compares a release branch against a development one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parity.cli import main
from parity.config import ConfigError, load_config

CONFIG = """
[pairs.demo]
ledger = "ledgers/demo.yml"

[pairs.demo.matlab]
repo = "org/DEMO"
ref = "develop3"
path = "DEMO"

[pairs.demo.python]
repo = "org/demopy"
package = "demopy"
path = "demopy"
"""


def _config(tmp_path: Path, text: str = CONFIG) -> Path:
    path = tmp_path / "parity.toml"
    path.write_text(text, encoding="utf-8")
    (tmp_path / "DEMO").mkdir()
    (tmp_path / "demopy").mkdir()
    return path


def test_ref_is_read_from_the_config(tmp_path: Path):
    config = load_config(_config(tmp_path))
    assert config.pair("demo").matlab.ref == "develop3"


def test_a_side_without_a_ref_falls_back_to_main(tmp_path: Path):
    """Not to "whatever the default branch is" --- that is the bug being closed."""
    config = load_config(_config(tmp_path))
    assert config.pair("demo").python.ref == "main"


def test_shell_format_is_consumable_by_github_output(tmp_path, capsys):
    assert main(["-c", str(_config(tmp_path)), "refs", "--format", "shell"]) == 0
    lines = capsys.readouterr().out.split()
    assert lines == [
        "demo_matlab_repo=org/DEMO",
        "demo_matlab_ref=develop3",
        "demo_python_repo=org/demopy",
        "demo_python_ref=main",
    ]


def test_shell_format_names_the_repo_too(tmp_path, capsys):
    """So a workflow can check out or `git ls-remote` a pair without hard-coding its repo
    name --- the nightly matrix needs this for whichever pair a given entry runs."""
    assert main(["-c", str(_config(tmp_path)), "refs", "--format", "shell", "--pair", "demo"]) == 0
    lines = capsys.readouterr().out.split()
    assert "demo_matlab_repo=org/DEMO" in lines
    assert "demo_python_repo=org/demopy" in lines


def test_text_format_names_the_repo_as_well_as_the_ref(tmp_path, capsys):
    assert main(["-c", str(_config(tmp_path)), "refs"]) == 0
    assert "org/DEMO@develop3" in capsys.readouterr().out


def test_unknown_pair_is_an_error_not_an_empty_list(tmp_path, capsys):
    """Silence would read as "no repos to check out" and the job would pass empty."""
    assert main(["-c", str(_config(tmp_path)), "refs", "--pair", "nope"]) == 2
