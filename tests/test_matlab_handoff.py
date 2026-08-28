"""Running MATLAB somewhere other than this process.

CI cannot spawn `matlab -batch` itself: MathWorks licenses public repositories
only through `matlab-actions/run-command`, so a MATLAB we start gets no licence.
`parity prepare` therefore writes the context and hands back the statement, and
`parity collect` picks up whatever wrote the result.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from parity.cli import main
from parity.config import ConfigError, load_config
from parity.scenarios import ScenarioError, collect_matlab, load_scenario, prepare_matlab

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


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch) -> Path:
    (tmp_path / "parity.toml").write_text(CONFIG, encoding="utf-8")
    (tmp_path / "DEMO").mkdir()
    (tmp_path / "demopy").mkdir()
    (tmp_path / "matlab").mkdir()
    scenario = tmp_path / "scenarios" / "demo_scenario"
    scenario.mkdir(parents=True)
    (scenario / "scenario.yml").write_text(
        "id: demo_scenario\npair: demo\ndescription: a scenario\n", encoding="utf-8"
    )
    (scenario / "demo_scenario.m").write_text("function r = demo_scenario(ctx)\nend\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def scenario_of(workspace: Path):
    return load_scenario(workspace / "scenarios" / "demo_scenario")


def test_prepare_writes_the_context_the_matlab_side_reads(workspace: Path):
    prepare_matlab(scenario_of(workspace), workspace)
    context = workspace / "scenarios" / "demo_scenario" / ".context.json"
    assert context.is_file()
    assert json.loads(context.read_text(encoding="utf-8"))


def test_prepare_does_not_run_anything(workspace: Path):
    """The whole point: it returns a statement for someone else to run."""
    statement = prepare_matlab(scenario_of(workspace), workspace)
    assert statement.startswith("addpath(")
    assert "parity_run(" in statement
    assert not (workspace / "scenarios" / "demo_scenario" / ".matlab_result.json").exists()


def test_guarded_statement_survives_a_failure(workspace: Path):
    """Scenarios share one MATLAB start, so one error must not end the run."""
    statement = prepare_matlab(scenario_of(workspace), workspace, guard=True)
    assert statement.startswith("try, ")
    assert statement.endswith("end")
    assert "demo_scenario failed" in statement
    # A literal backslash-n, which is what MATLAB's fprintf wants -- not a real
    # newline, which would split the statement across lines and not compile.
    assert chr(92) + "n'" in statement
    assert "\n" not in statement


def test_collect_refuses_to_invent_a_result(workspace: Path):
    """Silence here would be reported as agreement, which is the worst outcome."""
    with pytest.raises(ScenarioError, match="no MATLAB result"):
        collect_matlab(scenario_of(workspace))


def test_collect_records_what_matlab_wrote(workspace: Path):
    (workspace / "scenarios" / "demo_scenario" / ".matlab_result.json").write_text(
        json.dumps(
            {
                "result_version": 1,
                "scenario": "demo_scenario",
                "implementation": "matlab",
                "results": {"x": 1.0},
            }
        ),
        encoding="utf-8",
    )

    assert main(["collect", "demo_scenario"]) == 0

    written = json.loads((workspace / "results" / "matlab" / "demo_scenario.json").read_text("utf-8"))
    assert written["results"] == {"x": 1.0}


# --------------------------------------------------------------------------- #
# Path setup across pairs
#
# GECKO is built on RAVEN and ships no copy of it, so a gecko scenario needs
# both toolboxes on the MATLAB path. Naming RAVEN's location literally in
# GECKO's setup command would hard-code a path `parity.local.toml` is free to
# move, so the command names the pair side instead.
# --------------------------------------------------------------------------- #

TWO_PAIRS = """
[pairs.demo]
ledger = "ledgers/demo.yml"

[pairs.demo.matlab]
repo = "org/DEMO"
path = "DEMO"

[pairs.demo.python]
repo = "org/demopy"
package = "demopy"
path = "demopy"

[pairs.other]
ledger = "ledgers/other.yml"

[pairs.other.matlab]
repo = "org/OTHER"
path = "OTHER"
setup = "addpath(genpath('{demo_matlab}')); addpath(genpath('{path}'))"

[pairs.other.python]
repo = "org/otherpy"
package = "otherpy"
path = "otherpy"
"""


def test_a_setup_command_can_name_another_pairs_checkout(tmp_path: Path):
    (tmp_path / "parity.toml").write_text(TWO_PAIRS, encoding="utf-8")
    config = load_config(tmp_path / "parity.toml")

    setup = config.pair("other").matlab.setup_command
    assert setup == (
        f"addpath(genpath('{(tmp_path / 'DEMO').resolve().as_posix()}')); "
        f"addpath(genpath('{(tmp_path / 'OTHER').resolve().as_posix()}'))"
    )


def test_the_referenced_path_follows_a_local_override(tmp_path: Path):
    """The reason for the indirection: a moved checkout must move here too."""
    (tmp_path / "parity.toml").write_text(TWO_PAIRS, encoding="utf-8")
    (tmp_path / "parity.local.toml").write_text(
        '[pairs.demo.matlab]\npath = "elsewhere/DEMO"\n', encoding="utf-8"
    )
    config = load_config(tmp_path / "parity.toml")

    assert (tmp_path / "elsewhere" / "DEMO").resolve().as_posix() in config.pair("other").matlab.setup_command


def test_an_unknown_placeholder_is_refused(tmp_path: Path):
    """Left unresolved it would reach MATLAB as a literal brace and fail there."""
    (tmp_path / "parity.toml").write_text(
        TWO_PAIRS.replace("{demo_matlab}", "{nosuch_matlab}"), encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="nosuch_matlab"):
        load_config(tmp_path / "parity.toml")
