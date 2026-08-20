"""Ledger round-tripping, and the name matcher that proposes rows."""

from __future__ import annotations

from parity.inventory import build_inventory
from parity.ledger import Entry, Ledger, dump_ledger, load_ledger, merge_entries, save_ledger
from parity.seed import discover, expand, normalise, sync_ledger


def test_a_ledger_survives_a_round_trip(tmp_path):
    original = Ledger(
        pair="fake",
        matlab_repo="org/FAKE",
        python_repo="org/fakepy",
        entries=[
            Entry(status="parity", matlab="addRxns", python="fakepy.add_reactions", scenarios=["s1"]),
            Entry(status="matlab-only", matlab="predictLocalization", reason="not ported"),
        ],
    )
    path = save_ledger(original, tmp_path / "fake.yml")
    reloaded = load_ledger(path)

    assert {e.matlab for e in reloaded.entries} == {"addRxns", "predictLocalization"}
    assert reloaded.by_matlab()["addRxns"].python == "fakepy.add_reactions"
    assert reloaded.by_matlab()["addRxns"].scenarios == ["s1"]
    assert reloaded.by_matlab()["predictLocalization"].reason == "not ported"


def test_serialisation_is_stable_so_diffs_stay_readable(tmp_path):
    ledger = Ledger(
        pair="fake",
        matlab_repo="org/FAKE",
        python_repo="org/fakepy",
        entries=[
            Entry(status="parity", matlab="zeta", python="fakepy.zeta"),
            Entry(status="parity", matlab="alpha", python="fakepy.alpha"),
        ],
    )
    first = dump_ledger(ledger)
    ledger.entries.reverse()

    assert dump_ledger(ledger) == first, "row order must not depend on insertion order"
    assert first.index("alpha") < first.index("zeta")


def test_empty_fields_are_omitted_rather_than_written_as_null():
    text = dump_ledger(
        Ledger(pair="f", matlab_repo="a", python_repo="b", entries=[Entry(status="matlab-only", matlab="x", reason="y")])
    )
    rows = text.split("entries:", 1)[1]

    assert "python:" not in rows, "an absent side is left out, not written as an empty field"
    assert "scenarios:" not in rows
    assert "null" not in text


def test_hand_written_decisions_survive_a_resync():
    existing = [Entry(status="matlab-only", matlab="addRxns", reason="deliberate")]
    discovered = [
        Entry(status="unreviewed", matlab="addRxns", python="fakepy.add_reactions"),
        Entry(status="unreviewed", matlab="brandNew"),
    ]
    merged = merge_entries(existing, discovered)

    assert len(merged) == 2
    assert merged[0].status == "matlab-only", "a resync must never overwrite a human decision"
    assert merged[1].matlab == "brandNew"


def test_camel_and_snake_case_fold_together():
    assert normalise("predictLocalization") == normalise("predict_localization")


def test_matlab_abbreviations_expand_to_the_python_spelling():
    assert expand("addRxns") == expand("add_reactions")
    assert expand("removeMets") == expand("remove_metabolites")


def test_expansion_leaves_ordinary_names_alone():
    assert expand("exportModel") == "exportmodel"


def test_discovery_pairs_by_name_and_flags_the_rest(fake_pair):
    entries, summary = discover(build_inventory(fake_pair))

    paired = {e.matlab: e.python for e in entries if e.matlab and e.python}
    assert paired == {"addRxns": "fakepy.add_reactions", "exportModel": "fakepy.manipulation.export_model"}
    assert summary.exact == 1, "exportModel <-> export_model"
    assert summary.expanded == 1, "addRxns <-> add_reactions, via the abbreviation table"
    assert summary.matlab_unmatched == 1, "predictLocalization has no counterpart in the fake package"


def test_everything_discovered_starts_unreviewed(fake_pair):
    entries, _ = discover(build_inventory(fake_pair))
    assert {e.status for e in entries} == {"unreviewed"}, "the tool pairs names; a human confirms behaviour"


def test_sync_covers_the_whole_inventory(fake_pair):
    ledger, added, _ = sync_ledger(fake_pair)

    assert added == len(ledger.entries) > 0
    inventory = build_inventory(fake_pair)
    assert {e.matlab for e in ledger.entries if e.matlab} == inventory.matlab_keys
    assert {e.python for e in ledger.entries if e.python} == inventory.python_keys


def test_sync_is_idempotent(fake_pair):
    ledger, _, _ = sync_ledger(fake_pair)
    save_ledger(ledger, fake_pair.ledger)

    _, added_again, _ = sync_ledger(fake_pair)
    assert added_again == 0
