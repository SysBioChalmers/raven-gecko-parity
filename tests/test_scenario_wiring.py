"""A scenario and the ledger rows it validates have to point at each other.

`parity mirror` answers "I changed this --- which scenarios should I re-run?"
by walking from a changed function to its ledger row and reading that row's
``scenarios``. A scenario that lists an entry the row does not list back is
therefore invisible to exactly the question the tool exists to answer, and
nothing else notices: `parity check` validates statuses, not cross-references,
and a scenario runs perfectly well while pointing at a function that was
renamed away three months ago.

These tests read this repository's own scenarios and ledgers rather than a
synthetic fixture, because the thing being checked is the wiring in this
repository.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parity.config import load_config
from parity.ledger import load_ledger
from parity.scenarios import list_scenarios

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_config(ROOT / "parity.toml")
SCENARIOS = list_scenarios(ROOT / "scenarios")
LEDGERS = {pair.name: load_ledger(pair.ledger) for pair in CONFIG.pairs.values()}

# Named so a failure reads as "gpr_dnf_rules: ..." rather than "scenario3: ...".
IDS = [scenario.id for scenario in SCENARIOS]


def entry_names(pair: str) -> set[str]:
    """Every name a scenario may legitimately cite, either side of the ledger."""
    names = set()
    for entry in LEDGERS[pair].entries:
        names.update(name for name in (entry.matlab, entry.python) if name)
    return names


def rows_citing(pair: str, scenario_id: str):
    return [e for e in LEDGERS[pair].entries if scenario_id in (e.scenarios or [])]


def test_there_are_scenarios_to_check():
    """A wiring test that silently checks nothing would pass forever."""
    assert SCENARIOS


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_a_scenario_has_both_entry_points(scenario):
    assert scenario.python_entry.is_file(), f"{scenario.id} has no run.py"
    assert scenario.matlab_entry.is_file(), f"{scenario.id} has no {scenario.id}.m"


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_a_scenario_belongs_to_a_configured_pair(scenario):
    assert scenario.pair in LEDGERS, f"{scenario.id} names pair {scenario.pair!r}"


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_a_scenario_covers_something(scenario):
    """Without `entries` a scenario proves nothing about any declared row."""
    assert scenario.entries, f"{scenario.id} declares no entries"


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_every_entry_a_scenario_claims_exists_in_the_ledger(scenario):
    known = entry_names(scenario.pair)
    unknown = [name for name in scenario.entries if name not in known]
    assert not unknown, f"{scenario.id} cites {unknown}, which no {scenario.pair} ledger row names"


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_the_rows_a_scenario_claims_cite_it_back(scenario):
    """The direction `parity mirror` actually reads."""
    cited_back = {
        name
        for entry in rows_citing(scenario.pair, scenario.id)
        for name in (entry.matlab, entry.python)
        if name
    }
    missing = [name for name in scenario.entries if name not in cited_back]
    assert not missing, (
        f"{scenario.id} claims to cover {missing}, but those rows do not list it under "
        f"'scenarios' --- `parity mirror` would not suggest re-running it"
    )


def test_no_ledger_row_points_at_a_scenario_that_does_not_exist():
    known = {scenario.id for scenario in SCENARIOS}
    dangling = [
        (pair, entry.label, scenario_id)
        for pair, ledger in LEDGERS.items()
        for entry in ledger.entries
        for scenario_id in (entry.scenarios or [])
        if scenario_id not in known
    ]
    assert not dangling, f"ledger rows cite scenarios that are not in scenarios/: {dangling}"
