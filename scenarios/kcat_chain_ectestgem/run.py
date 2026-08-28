"""Python side of the kcat-chain scenario.

One flowing ecModel, walked through the real pipeline order --- fuzzy match, DLKcat
read + merge, select, isozyme fill, custom override, standard-kcat fallback, apply
constraints --- checkpointing the intermediate state after each stage, the same way
GECKO's own `testKcats_tc0011` does it. Checkpoints are not independent fresh copies
here (unlike model_edits_ectestgem): the pipeline is inherently sequential, each stage
consumes the previous stage's kcats, and hiding that behind fresh copies would just
mean re-deriving the same intermediate state repeatedly.

Two extra reactions are added to the stock ecTestGEM model, for reasons documented at
each use site: R2a (same GPR shape as R2, no EC code --- forces reliance on DLKcat for
one isozyme and on isozyme-fill/standard-kcat for the rest) and R6 (no GPR at all ---
the one reaction shape ecTestGEM's stock model does not have, needed to exercise
getStandardKcat's new-pseudo-protein path rather than only its fillZeroKcat path).

Three checkpoints assert a confirmed, real divergence on purpose rather than working
around it --- see the comments at `applyCustomKcats` (mode-A source/notes), the
`criteria='median'` sub-case under `selection` (MATLAB's own dead code), and the
isolated `constraints.light_partial_isozyme` sub-case (MATLAB silently zeroing a
reaction's enzyme cost). All three were confirmed by direct execution against a
pinned GECKO develop4 worktree before being written into this scenario; see
docs/gecko-behaviour-parity-plan.md for the upstream issues.
"""

import importlib.util
import sys
from pathlib import Path

import cobra
import numpy as np
import pandas as pd
from scipy import sparse

from geckopy import (
    EcData,
    ModelAdapter,
    apply_custom_kcats,
    apply_kcat_constraints,
    apply_kcat_list,
    assign_standard_kcat,
    fill_eccodes_from_gem,
    fill_kcats_from_isozymes,
    fuzzy_kcat_matching,
    load_brenda_data,
    load_conventional_gem,
    load_dlkcat_ignore_lists,
    load_phyl_dist,
    load_uniprot_tsv,
    make_ec_model,
    merge_kcats,
    read_dlkcat_output,
    remove_standard_kcat,
    write_dlkcat_input,
)


def _bound(value: float) -> tuple[float, str]:
    value = float(value)
    if value == float("inf"):
        return 0.0, "+inf"
    if value == float("-inf"):
        return 0.0, "-inf"
    return value, "finite"


def _adapter(inputs: dict) -> ModelAdapter:
    """geckopy's ecTestGEM adapter --- the actual `TestGEMAdapter` subclass, not the
    generic `ModelAdapter`, since only the subclass knows R4 is spontaneous
    (`ModelAdapter.from_folder` does not auto-discover it; MATLAB's
    `ModelAdapterManager.getAdapter` loads TestGEMAdapter.m the same explicit way).
    """
    base = ModelAdapter.from_folder(inputs["adapter_python"])
    fixture = Path(inputs["fixture_dir"])
    base.params.path = fixture
    base.params.conv_gem = fixture / "models" / "testModel.xml"

    adapter_module_path = Path(inputs["adapter_python"]) / "adapter.py"
    spec = importlib.util.spec_from_file_location("ectestgem_adapter", adapter_module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.TestGEMAdapter(base.params)


def _add_extra_reactions(conv: cobra.Model) -> None:
    """R2a and R6, added to the conventional model before ecModel expansion.

    R2a mirrors R2's GPR ('G1 and G2 or G3') but carries no EC code, so fuzzy matching
    cannot touch it at all --- every kcat it gets has to come from DLKcat (one isozyme)
    or the standard-kcat fallback (the rest, deliberately not covered by the DLKcat
    fixture either). R6 has no GPR --- the one shape missing from the stock fixture,
    needed so getStandardKcat has a reaction to attach its new 'standard'
    pseudo-protein to, rather than only ever filling an existing enzyme's zero kcat.
    """
    m1 = conv.metabolites.get_by_id("m1c")
    m2 = conv.metabolites.get_by_id("m2c")

    r2a = cobra.Reaction("R2a", name="R2a")
    r2a.lower_bound = -1000.0
    r2a.upper_bound = 1000.0
    r2a.add_metabolites({m1: -1.0, m2: 1.0})
    r2a.gene_reaction_rule = "G1 and G2 or G3"

    r6 = cobra.Reaction("R6", name="R6")
    r6.lower_bound = 0.0
    r6.upper_bound = 1000.0
    r6.add_metabolites({m1: -1.0, m2: 1.0})

    conv.add_reactions([r2a, r6])


def _base_model(inputs: dict):
    adapter = _adapter(inputs)
    conv = load_conventional_gem(adapter)
    _add_extra_reactions(conv)
    return adapter, conv


def _fresh_ec_model(adapter, conv):
    model = make_ec_model(conv, adapter, gecko_light=False)
    fill_eccodes_from_gem(model)
    return model


def _source_token(source: str) -> str:
    """The base provenance token: lowercased, and dropping geckopy's bracketed
    wildcard/origin detail (e.g. 'DLKcat' -> 'dlkcat'; 'brenda (wc=0, origin=1)'
    -> 'brenda'). Both are documented MATLAB-COMPAT choices (select_kcat_value.py:
    geckopy lowercases MATLAB's raw kcatSource string and appends fuzzy detail),
    not divergences this scenario is asserting, so the checkpoint compares on the
    token both sides agree on.
    """
    return source.split(" (", 1)[0].lower()


def _kcat_rows(model, rxn_ids: list[str]) -> list[dict]:
    ec = model.ec
    index = {r: i for i, r in enumerate(ec.rxns)}
    records = []
    for r in rxn_ids:
        if r not in index:
            continue
        i = index[r]
        records.append(
            {
                "reaction": r,
                "kcat": float(ec.kcat[i]),
                "source": _source_token(str(ec.source[i])) if ec.source[i] else "",
                "notes": str(ec.notes[i]) if ec.notes[i] else "",
            }
        )
    return sorted(records, key=lambda e: e["reaction"])


def _all_ec_rxns(model) -> list[str]:
    return sorted(str(r) for r in model.ec.rxns)


# --------------------------------------------------------------------------- #
# fuzzy: loadBRENDAdata + fuzzyKcatMatching
# --------------------------------------------------------------------------- #

def _checkpoint_fuzzy(model, inputs: dict):
    brenda = load_brenda_data(inputs["brenda_dir"])
    phyl_dist = load_phyl_dist(inputs["phyl_dist_path"])

    kcat_max = [
        {
            "eccode": str(row.ec_code),
            "substrate": str(row.substrate),
            "organism": str(row.organism),
            "kcat": float(row.kcat),
        }
        for row in brenda.kcat_max.itertuples()
    ]
    kcat_max.sort(key=lambda r: (r["eccode"], r["substrate"], r["organism"]))

    fuzzy_df = fuzzy_kcat_matching(model, brenda, phyl_dist)
    matches = [
        {
            "reaction": str(row.rxn_id),
            "kcat": float(row.kcat),
            "eccode": str(row.eccode) if row.eccode else "",
            "origin": -1 if pd.isna(row.origin) else int(row.origin),
            "wildcard_level": -1 if pd.isna(row.wildcard_level) else int(row.wildcard_level),
        }
        for row in fuzzy_df.itertuples()
    ]
    matches.sort(key=lambda r: r["reaction"])

    return {"brenda_kcat_max": kcat_max, "matches": matches}, fuzzy_df


# --------------------------------------------------------------------------- #
# dlkcat: writeDLKcatInput + readDLKcatOutput + mergeDLKcatAndFuzzyKcats
# --------------------------------------------------------------------------- #

def _checkpoint_dlkcat(model, fuzzy_df, inputs: dict):
    ignore_lists = load_dlkcat_ignore_lists()
    written = write_dlkcat_input(
        model, Path(inputs["dlkcat_write_target"]), ignore_lists,
        ec_rxns=["R2a_EXP_1", "R2a_EXP_2"], overwrite=True, only_with_smiles=False,
    )
    written_rows = sorted(
        (
            {"reaction": str(r.rxn_id), "gene": str(r.gene), "substrate": str(r.substrate)}
            for r in written.itertuples()
        ),
        key=lambda r: (r["reaction"], r["gene"]),
    )

    dlkcat_df = read_dlkcat_output(model, inputs["dlkcat_output_path"])
    dlkcat_rows = sorted(
        (
            {
                "reaction": str(r.rxn_id),
                "gene": str(r.genes[0]) if r.genes else "",
                "kcat": float(r.kcat),
            }
            for r in dlkcat_df.itertuples()
        ),
        key=lambda r: (r["reaction"], r["gene"]),
    )

    merged = merge_kcats(fuzzy_df, dlkcat_df, source_priority=["database_top", "dlkcat", "database_bottom"])
    merged_rows = sorted(
        (
            {"reaction": str(r.rxn_id), "kcat": float(r.kcat), "source": str(r.source)}
            for r in merged.itertuples()
        ),
        key=lambda r: (r["reaction"], r["source"]),
    )

    return {
        "written_input": written_rows,
        "read_output": dlkcat_rows,
        "merged": merged_rows,
    }, merged


# --------------------------------------------------------------------------- #
# selection: selectKcatValue + applyCustomKcats + getKcatAcrossIsozymes
# --------------------------------------------------------------------------- #

def _checkpoint_selection(model, merged, inputs: dict):
    out = {}

    apply_kcat_list(model, merged, criteria="max")
    out["after_select_max"] = _kcat_rows(model, _all_ec_rxns(model))

    # MATLAB's selectKcatValue.m computes [selectedKcats(i),j] = median(...)/mean(...)
    # for these two criteria --- a two-output call standard MATLAB median/mean do not
    # support (only max/min do). Confirmed by direct execution: this errors
    # unconditionally with "Too many output arguments" whenever it reaches a
    # reaction needing aggregation, i.e. on any non-empty kcatList. geckopy's
    # apply_kcat_list has no such restriction. Asserted here rather than avoided.
    probe = model.copy()
    try:
        apply_kcat_list(probe, merged, criteria="median")
        median_result = {"raised": False}
    except Exception:  # noqa: BLE001 --- whether it raises is the finding, not the exception type
        median_result = {"raised": True}
    out["select_median"] = median_result

    fill_kcats_from_isozymes(model, apply=False)
    out["after_isozyme_fill"] = _kcat_rows(model, _all_ec_rxns(model))

    # customKcats.tsv's only row targets R3 by reaction id alone (mode A: no protein
    # listed). MATLAB's applyCustomKcats.m only ever writes ec.kcat in this branch,
    # leaving ec.source/ec.notes at whatever they already were (here: 'brenda', from
    # the fuzzy match). geckopy's apply_custom_kcats shares one write path across all
    # three modes and always sets source='custom' and appends the note. Both sides
    # apply the same new kcat; source/notes are the deliberately-asserted difference.
    apply_custom_kcats(model, Path(inputs["custom_kcats_path"]), apply=False)
    out["after_custom_kcats"] = _kcat_rows(model, ["R3"])

    return out


# --------------------------------------------------------------------------- #
# standard: getStandardKcat + removeStandardKcat
# --------------------------------------------------------------------------- #

def _checkpoint_standard(model, inputs: dict):
    uniprot_db = load_uniprot_tsv(inputs["uniprot_path"], id_type="taxonomy_id", auto_download=False)

    before_rxns = _all_ec_rxns(model)
    before_snapshot = _kcat_rows(model, before_rxns)

    assign_standard_kcat(model, uniprot_db, fill_zero_kcat=True)
    after_rxns = _all_ec_rxns(model)
    new_rxns = sorted(set(after_rxns) - set(before_rxns))

    out = {
        "new_ec_rxns": new_rxns,
        "r6_and_r2a_rev": _kcat_rows(model, ["R6", "R2a_REV_EXP_1", "R2a_REV_EXP_2"]),
        "all_after_assign": _kcat_rows(model, after_rxns),
    }

    probe = model.copy()
    remove_standard_kcat(probe)
    out["after_remove"] = {
        "ec_rxns": _all_ec_rxns(probe),
        "rows": _kcat_rows(probe, _all_ec_rxns(probe)),
    }
    return out


# --------------------------------------------------------------------------- #
# constraints: applyKcatConstraints
# --------------------------------------------------------------------------- #

def _prot_coefficients(model) -> list[dict]:
    records = []
    for rxn in model.reactions:
        for met, coeff in rxn.metabolites.items():
            if met.id.startswith("prot_") and coeff != 0:
                records.append({"reaction": rxn.id, "metabolite": met.id, "coefficient": float(coeff)})
    return sorted(records, key=lambda e: (e["reaction"], e["metabolite"]))


def _checkpoint_constraints(model) -> dict:
    apply_kcat_constraints(model)
    return {"coefficients": _prot_coefficients(model)}


def _checkpoint_constraints_light_partial_isozyme(adapter) -> dict:
    """Isolated, purpose-built light-model case: one reaction, two isozymes, only one
    of which has a kcat assigned. MATLAB's applyKcatConstraints.m corrects an
    unassigned isozyme's Inf cost (MW/0) to 0 *before* taking min() across isozymes,
    so the fabricated zero always wins --- silently writing a zero enzyme cost for
    the whole reaction even though the other isozyme has a real, valid kcat.
    geckopy's apply_kcat_constraints skips invalid isozymes before the comparison
    instead. Confirmed by direct execution against a pinned GECKO develop4 worktree;
    not reachable through the shared ecTestGEM fixture, so built standalone here.
    """
    model = cobra.Model("light_partial_isozyme")
    pool = cobra.Metabolite("prot_pool", compartment="c")
    model.add_metabolites([pool])
    rxn = cobra.Reaction("R1")
    rxn.lower_bound = 0.0
    rxn.upper_bound = 1000.0
    model.add_reactions([rxn])

    ec = EcData(
        gecko_light=True,
        rxns=["001_R1", "002_R1"],
        kcat=np.array([0.0, 50.0]),
        source=["", ""],
        notes=["", ""],
        eccodes=["", ""],
        rxn_enz_mat=sparse.csr_matrix([[1.0, 0.0], [0.0, 1.0]]),
        genes=["G1", "G2"],
        enzymes=["P1", "P2"],
        mw=np.array([10000.0, 5000.0]),
        sequence=["", ""],
    )
    model.ec = ec
    model.adapter = adapter

    apply_kcat_constraints(model)
    return {"coefficients": _prot_coefficients(model)}


def run(ctx):
    inputs = ctx["inputs"]
    adapter, conv = _base_model(inputs)
    model = _fresh_ec_model(adapter, conv)

    fuzzy_result, fuzzy_df = _checkpoint_fuzzy(model, inputs)
    dlkcat_result, merged = _checkpoint_dlkcat(model, fuzzy_df, inputs)
    selection_result = _checkpoint_selection(model, merged, inputs)
    standard_result = _checkpoint_standard(model, inputs)
    constraints_result = _checkpoint_constraints(model)
    constraints_result["light_partial_isozyme"] = _checkpoint_constraints_light_partial_isozyme(adapter)["coefficients"]

    return {
        "fuzzy": fuzzy_result,
        "dlkcat": dlkcat_result,
        "selection": selection_result,
        "standard": standard_result,
        "constraints": constraints_result,
    }
