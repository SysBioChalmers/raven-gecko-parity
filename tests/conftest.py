"""Synthetic two-sided fixtures.

The tests build tiny fake repos rather than reading the real RAVEN/GECKO checkouts, so they
say something about this tool rather than about whatever those repos happen to contain today.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parity.config import MatlabSide, Pair, PythonSide  # noqa: E402


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def fake_pair(tmp_path: Path) -> Pair:
    matlab_root = tmp_path / "FAKE"
    python_root = tmp_path / "fakepy"

    write(matlab_root / "core" / "addRxns.m", "function model = addRxns(model)\nend\n")
    write(matlab_root / "core" / "predictLocalization.m", "function out = predictLocalization(m)\nend\n")
    write(matlab_root / "io" / "exportModel.m", "function exportModel(m)\nend\n")
    # Must be ignored: vendored code, tests, and MATLAB's private/ convention.
    write(matlab_root / "software" / "vendored.m", "function vendored()\nend\n")
    write(matlab_root / "testing" / "testAddRxns.m", "function testAddRxns()\nend\n")
    write(matlab_root / "core" / "private" / "helper.m", "function helper()\nend\n")

    write(
        python_root / "src" / "fakepy" / "__init__.py",
        "from fakepy.manipulation import add_reactions\n__all__ = ['add_reactions']\n",
    )
    write(
        python_root / "src" / "fakepy" / "manipulation" / "__init__.py",
        "from fakepy.manipulation.add import add_reactions\n"
        "from fakepy.manipulation.export import export_model\n"
        "__all__ = ['add_reactions', 'export_model']\n",
    )
    write(python_root / "src" / "fakepy" / "manipulation" / "add.py", "def add_reactions():\n    pass\n")
    write(python_root / "src" / "fakepy" / "manipulation" / "export.py", "def export_model():\n    pass\n")
    # No __all__ anywhere in here, so nothing from it is public API.
    write(python_root / "src" / "fakepy" / "internal" / "__init__.py", "from fakepy.internal.util import helper\n")
    write(python_root / "src" / "fakepy" / "internal" / "util.py", "def helper():\n    pass\n")

    return Pair(
        name="fake",
        ledger=tmp_path / "ledgers" / "fake.yml",
        matlab=MatlabSide(repo="org/FAKE", path=matlab_root, exclude=("software", "testing")),
        python=PythonSide(repo="org/fakepy", path=python_root, package="fakepy"),
    )
