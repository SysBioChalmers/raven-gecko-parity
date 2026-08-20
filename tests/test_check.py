"""The three ways parity rots, and the check that catches each one."""

from __future__ import annotations

import pytest

from parity.check import run_check
from parity.ledger import Entry, Ledger


def ledger_of(*entries: Entry) -> Ledger:
    return Ledger(pair="fake", matlab_repo="org/FAKE", python_repo="org/fakepy", entries=list(entries))


def complete(*extra: Entry) -> Ledger:
    """A ledger that covers the whole fake inventory, plus whatever is passed in."""
    return ledger_of(
        Entry(status="parity", matlab="addRxns", python="fakepy.add_reactions"),
        Entry(status="parity", matlab="exportModel", python="fakepy.manipulation.export_model"),
        Entry(status="matlab-only", matlab="predictLocalization", reason="simulated annealing; not ported"),
        *extra,
    )


def kinds(result) -> list[str]:
    return [f.kind for f in result.findings]


def test_a_complete_ledger_passes(fake_pair):
    result = run_check(fake_pair, ledger=complete())
    assert result.ok()
    assert not result.errors


def test_a_new_public_function_fails_the_check(fake_pair):
    """The point of the whole exercise: new code cannot slip in undeclared."""
    partial = ledger_of(Entry(status="parity", matlab="addRxns", python="fakepy.add_reactions"))
    result = run_check(fake_pair, ledger=partial)

    uncovered = {f.subject for f in result.findings if f.kind == "uncovered"}
    assert uncovered == {"exportModel", "predictLocalization", "fakepy.manipulation.export_model"}
    assert not result.ok()


def test_a_renamed_function_is_reported_as_stale(fake_pair):
    stale = complete(Entry(status="matlab-only", matlab="removedLongAgo", reason="gone"))
    result = run_check(fake_pair, ledger=stale)
    assert "stale" in kinds(result)
    assert not result.ok()


def test_two_rows_cannot_claim_the_same_function(fake_pair):
    duplicated = complete(Entry(status="matlab-pending", python="fakepy.add_reactions"))
    result = run_check(fake_pair, ledger=duplicated)
    assert "duplicate" in kinds(result)


@pytest.mark.parametrize(
    "entry",
    [
        Entry(status="parity", matlab="addRxns"),
        Entry(status="matlab-only", matlab="addRxns", python="fakepy.add_reactions", reason="r"),
        Entry(status="matlab-only", matlab="addRxns"),
        Entry(status="python-pending", matlab="addRxns", python="fakepy.add_reactions"),
        Entry(status="subsumed", matlab="addRxns", python="fakepy.add_reactions", reason="r"),
        Entry(status="subsumed", matlab="addRxns"),
        Entry(status="invented-status", matlab="addRxns"),
    ],
    ids=[
        "parity-needs-both",
        "one-sided-cannot-pair",
        "needs-a-reason",
        "pending-means-absent",
        "subsumed-cannot-pair",
        "subsumed-needs-a-reason",
        "unknown-status",
    ],
)
def test_contradictory_rows_are_rejected(fake_pair, entry):
    result = run_check(fake_pair, ledger=ledger_of(entry))
    assert "invalid" in kinds(result)


def test_queued_work_without_an_issue_warns_but_does_not_fail(fake_pair):
    queued = ledger_of(
        Entry(status="parity", matlab="addRxns", python="fakepy.add_reactions"),
        Entry(status="parity", matlab="exportModel", python="fakepy.manipulation.export_model"),
        Entry(status="python-pending", matlab="predictLocalization"),
    )
    result = run_check(fake_pair, ledger=queued)
    assert result.ok()
    assert "untracked" in kinds(result)


def test_unreviewed_rows_pass_normally_but_fail_under_strict(fake_pair):
    triage = ledger_of(
        Entry(status="unreviewed", matlab="addRxns", python="fakepy.add_reactions"),
        Entry(status="unreviewed", matlab="exportModel", python="fakepy.manipulation.export_model"),
        Entry(status="unreviewed", matlab="predictLocalization"),
    )
    result = run_check(fake_pair, ledger=triage)

    assert result.ok(), "adoption has to be incremental, so triage debt is not an error"
    assert not result.ok(strict=True), "but --strict is what drives it to zero"
    assert result.unreviewed == 3
