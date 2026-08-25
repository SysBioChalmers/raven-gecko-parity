"""What the nightly writes down, and what it refuses to claim.

The one thing this report must never do is report a scenario that failed to run
as agreement. A missing result file means nobody knows the answer; printing
"MATCH" for it would turn a broken harness into a green light.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("nightly_report", ROOT / "scripts" / "nightly_report.py")
nightly_report = importlib.util.module_from_spec(_spec)
sys.modules["nightly_report"] = nightly_report
_spec.loader.exec_module(nightly_report)


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch) -> Path:
    """A miniature parity root with one scenario and nothing else."""
    (tmp_path / "parity.toml").write_text(
        '[pairs.demo]\nledger = "ledgers/demo.yml"\n'
        '[pairs.demo.matlab]\nrepo = "org/DEMO"\nref = "develop3"\npath = "DEMO"\n'
        '[pairs.demo.python]\nrepo = "org/demopy"\npackage = "demopy"\npath = "demopy"\n',
        encoding="utf-8",
    )
    (tmp_path / "DEMO").mkdir()
    (tmp_path / "demopy").mkdir()
    scenario = tmp_path / "scenarios" / "demo_scenario"
    scenario.mkdir(parents=True)
    (scenario / "scenario.yml").write_text(
        "id: demo_scenario\npair: demo\ndescription: a scenario\n"
        "tolerance:\n  rel: 1.0e-9\n  abs: 1.0e-12\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def result(workspace: Path, impl: str, value) -> None:
    path = workspace / "results" / impl / "demo_scenario.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"scenario": "demo_scenario", "implementation": impl, "results": {"x": value}}),
        encoding="utf-8",
    )


def run(workspace: Path, *extra: str) -> tuple[int, str]:
    code = nightly_report.main(
        ["--pair", "demo", "--state", "nightly/state.json", "--report", "nightly/report.md", *extra]
    )
    return code, (workspace / "nightly" / "report.md").read_text(encoding="utf-8")


def test_agreement_is_reported_and_exits_clean(workspace: Path):
    result(workspace, "python", 1.0)
    result(workspace, "matlab", 1.0)
    code, report = run(workspace)
    assert code == 0
    assert "| `demo_scenario` | MATCH |" in report


def test_a_scenario_that_never_ran_is_an_error_not_a_match(workspace: Path):
    result(workspace, "python", 1.0)  # MATLAB side never produced anything
    code, report = run(workspace)
    assert code == 1
    assert "| `demo_scenario` | ERROR | no result from matlab |" in report
    assert "MATCH" not in report


def test_differences_are_quoted_in_the_report(workspace: Path):
    result(workspace, "python", 1.0)
    result(workspace, "matlab", 2.0)
    code, report = run(workspace)
    assert code == 1
    assert "| `demo_scenario` | DIFFER | 1 difference(s) |" in report
    assert "results.x" in report


def test_state_records_the_revisions_the_next_run_compares_against(workspace: Path):
    result(workspace, "python", 1.0)
    result(workspace, "matlab", 1.0)
    run(workspace, "--sha", "demo.matlab=abc", "--sha", "demo.python=def")

    state = json.loads((workspace / "nightly" / "state.json").read_text(encoding="utf-8"))
    assert state["revisions"] == {"demo.matlab": "abc", "demo.python": "def"}
    assert state["verdicts"] == {"demo_scenario": "MATCH"}


def test_the_report_names_the_branch_as_well_as_the_sha(workspace: Path):
    """A sha alone does not tell a reader which branch was compared."""
    result(workspace, "python", 1.0)
    result(workspace, "matlab", 1.0)
    _, report = run(workspace, "--sha", "demo.matlab=0123456789abcdef")
    assert "org/DEMO @ `develop3` &mdash; `0123456789ab`" in report
