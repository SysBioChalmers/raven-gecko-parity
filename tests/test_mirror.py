"""Mapping a change on one side to the work it creates on the other."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from parity import mirror
from parity.ledger import Entry, Ledger


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def committed(fake_pair):
    """Turn the fake python repo into a git checkout with one commit."""
    repo = fake_pair.python.path
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "initial")
    return fake_pair


def ledger() -> Ledger:
    return Ledger(
        pair="fake",
        matlab_repo="org/FAKE",
        python_repo="org/fakepy",
        entries=[
            Entry(status="parity", matlab="addRxns", python="fakepy.add_reactions"),
            Entry(status="matlab-only", matlab="predictLocalization", reason="not ported"),
            Entry(status="unreviewed", matlab="exportModel", python="fakepy.manipulation.export_model"),
        ],
    )


def test_editing_a_defining_module_reaches_its_export(committed):
    """The edit lands in add.py; the ledger row is keyed on the re-exported name."""
    (committed.python.path / "src" / "fakepy" / "manipulation" / "add.py").write_text(
        "def add_reactions():\n    return 1\n", encoding="utf-8"
    )
    result = mirror.analyse(committed, "python", ledger=ledger())

    assert [t.via for t in result.at_parity] == ["fakepy.add_reactions"]
    assert result.needs_attention


def test_a_touched_unreviewed_row_is_surfaced_for_triage(committed):
    (committed.python.path / "src" / "fakepy" / "manipulation" / "export.py").write_text(
        "def export_model():\n    return 2\n", encoding="utf-8"
    )
    result = mirror.analyse(committed, "python", ledger=ledger())

    assert [t.via for t in result.unreviewed] == ["fakepy.manipulation.export_model"]
    assert not result.at_parity


def test_an_untouched_repo_needs_no_attention(committed):
    result = mirror.analyse(committed, "python", ledger=ledger())
    assert not result.files
    assert not result.needs_attention


def test_a_changed_file_with_no_public_export_is_reported_as_unmapped(committed):
    (committed.python.path / "src" / "fakepy" / "internal" / "util.py").write_text(
        "def helper():\n    return 3\n", encoding="utf-8"
    )
    result = mirror.analyse(committed, "python", ledger=ledger())

    assert result.unmapped == ["src/fakepy/internal/util.py"]
    assert not result.needs_attention


def test_the_report_names_the_sibling_repo(committed):
    (committed.python.path / "src" / "fakepy" / "manipulation" / "add.py").write_text(
        "def add_reactions():\n    return 1\n", encoding="utf-8"
    )
    result = mirror.analyse(committed, "python", ledger=ledger())
    text = mirror.render(result, committed)

    assert "org/FAKE" in text
    assert "addRxns" in text


def test_describe_reports_the_branch_and_dirtiness(committed):
    assert "+dirty" not in mirror.describe(committed.python.path)
    (committed.python.path / "src" / "fakepy" / "manipulation" / "add.py").write_text("x = 1\n", encoding="utf-8")
    assert "+dirty" in mirror.describe(committed.python.path)


def test_describe_does_not_explode_outside_a_checkout(fake_pair):
    assert mirror.describe(fake_pair.matlab.path) == "not a git checkout"
