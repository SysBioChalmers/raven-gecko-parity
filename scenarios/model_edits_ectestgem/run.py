"""Python side of the model-edits scenario.

Five checkpoints, one per entry, each applied to its own fresh copy of a full ecModel ---
never to the same mutated model twice, so no checkpoint depends on the order the others
ran in. The shared ``_ec_data`` / ``_reactions`` / ``_gene_associations`` / ``_stoichiometry``
helpers are the same ones ``ec_model_expansion_ectestgem`` uses, reused rather than
reinvented for the same reason: they already handle the conventions that avoid false
differences (infinite bounds, sorted multi-key records, ec.rxns left in expansion order).
"""

from pathlib import Path

import cobra
import pandas as pd

from geckopy import (
    ModelAdapter,
    add_new_rxns_to_ec,
    copy_ec_to_gem,
    get_reactions_from_enzyme,
    load_conventional_gem,
    make_ec_model,
    map_rxns_to_conv,
    set_kcat_for_reactions,
)
from geckopy.utilities.add_new_rxns_to_ec import NewEnzyme


def _bound(value: float) -> tuple[float, str]:
    value = float(value)
    if value == float("inf"):
        return 0.0, "+inf"
    if value == float("-inf"):
        return 0.0, "-inf"
    return value, "finite"


def _adapter(inputs: dict) -> ModelAdapter:
    adapter = ModelAdapter.from_folder(inputs["adapter_python"])
    fixture = Path(inputs["fixture_dir"])
    adapter.params.path = fixture
    adapter.params.conv_gem = fixture / "models" / "testModel.xml"
    return adapter


def _gene_associations(model) -> list[dict]:
    entries = [{"reaction": rxn.id, "gene": gene.id} for rxn in model.reactions for gene in rxn.genes]
    return sorted(entries, key=lambda e: (e["reaction"], e["gene"]))


def _stoichiometry(model) -> list[dict]:
    entries = [
        {"reaction": rxn.id, "metabolite": met.id, "coefficient": float(coefficient)}
        for rxn in model.reactions
        for met, coefficient in rxn.metabolites.items()
    ]
    return sorted(entries, key=lambda e: (e["reaction"], e["metabolite"]))


def _reactions(model) -> list[dict]:
    records = []
    for rxn in sorted(model.reactions, key=lambda r: r.id):
        lower, lower_kind = _bound(rxn.lower_bound)
        upper, upper_kind = _bound(rxn.upper_bound)
        records.append(
            {
                "id": rxn.id,
                "lower_bound": lower,
                "lower_kind": lower_kind,
                "upper_bound": upper,
                "upper_kind": upper_kind,
                "objective_coefficient": float(rxn.objective_coefficient),
            }
        )
    return records


def _ec_data(ec) -> dict:
    matrix = ec.rxn_enz_mat
    if hasattr(matrix, "toarray"):
        matrix = matrix.toarray()
    coupling = [
        {"reaction": ec.rxns[i], "enzyme": ec.enzymes[j], "coefficient": float(matrix[i][j])}
        for i in range(len(ec.rxns))
        for j in range(len(ec.enzymes))
        if matrix[i][j] != 0
    ]
    # rxns/kcat/source/eccodes sorted by reaction id here, unlike ec_model_expansion_ectestgem's
    # ec.rxns: *that* scenario's order is makeEcModel's own expansion order, which MATLAB's own
    # unit tests pin exactly. The order addNewRxnsToEC appends new isozyme/reversibility variants
    # in has no such contract on either side --- neither implementation's tests assert it --- so
    # leaving it unsorted here would report an incidental loop-order difference as a finding.
    rxn_rows = sorted(
        zip(ec.rxns, ec.kcat, ec.source, ec.eccodes),
        key=lambda row: row[0],
    )
    return {
        "rxns": [str(r) for r, _, _, _ in rxn_rows],
        "genes": [str(g) for g in ec.genes],
        "enzymes": [str(e) for e in ec.enzymes],
        "mw": [float(m) for m in ec.mw],
        "eccodes": [str(c) if c else "" for _, _, _, c in rxn_rows],
        "kcat": [float(k) for _, k, _, _ in rxn_rows],
        "source": [str(s) for _, _, s, _ in rxn_rows],
        "coupling": sorted(coupling, key=lambda e: (e["reaction"], e["enzyme"])),
    }


def _model_summary(model) -> dict:
    return {
        "n_reactions": len(model.reactions),
        "n_metabolites": len(model.metabolites),
        "n_genes": len(model.genes),
        "reactions": _reactions(model),
        "genes": sorted(gene.id for gene in model.genes),
        "gene_associations": _gene_associations(model),
        "stoichiometry": _stoichiometry(model),
        "ec": _ec_data(model.ec),
    }


def _base_model(inputs: dict):
    adapter = _adapter(inputs)
    conv = load_conventional_gem(adapter)
    return adapter, conv


def _fresh_ec_model(adapter, conv):
    return make_ec_model(conv, adapter, gecko_light=False)


# --------------------------------------------------------------------------- #
# getReactionsFromEnzyme / get_reactions_from_enzyme
# --------------------------------------------------------------------------- #

def _reactions_from_enzyme_case(model, protein_id: str) -> dict:
    try:
        df = get_reactions_from_enzyme(model, protein_id)
    except Exception:  # noqa: BLE001 --- which exception is not the finding; whether one was raised is
        return {"raised": True, "rxns": [], "kcat": []}
    records = sorted(zip(df["rxn_id"], df["kcat"]), key=lambda r: r[0])
    return {
        "raised": False,
        "rxns": [r for r, _ in records],
        "kcat": [float(k) for _, k in records],
    }


def _checkpoint_reactions_from_enzyme(adapter, conv, inputs: dict) -> dict:
    model = _fresh_ec_model(adapter, conv)
    return {
        "known": _reactions_from_enzyme_case(model, inputs["known_enzyme"]),
        "case_variant": _reactions_from_enzyme_case(model, inputs["case_variant_enzyme"]),
        "unknown": _reactions_from_enzyme_case(model, inputs["unknown_enzyme"]),
    }


# --------------------------------------------------------------------------- #
# setKcatForReactions / set_kcat_for_reactions
# --------------------------------------------------------------------------- #

def _kcat_and_source(model, ec_rxns: list[str]) -> dict:
    ec = model.ec
    index = {r: i for i, r in enumerate(ec.rxns)}
    records = [
        {"reaction": r, "kcat": float(ec.kcat[index[r]]), "source": str(ec.source[index[r]])}
        for r in ec_rxns
        if r in index
    ]
    return {"records": sorted(records, key=lambda e: e["reaction"])}


def _checkpoint_set_kcat(adapter, conv, inputs: dict) -> dict:
    # apply=False everywhere: matches what setKcatForReactions.m does on its own (it never
    # touches the S-matrix; applyKcatConstraints is a separate, later step on both sides).
    suffixed = _fresh_ec_model(adapter, conv)
    spec = inputs["kcat_suffixed"]
    set_kcat_for_reactions(suffixed, [spec["rxn"]], float(spec["value"]), apply=False)

    base_scalar = _fresh_ec_model(adapter, conv)
    spec = inputs["kcat_base_scalar"]
    set_kcat_for_reactions(base_scalar, [spec["rxn"]], float(spec["value"]), apply=False)

    base_list = _fresh_ec_model(adapter, conv)
    spec = inputs["kcat_base_list"]
    try:
        set_kcat_for_reactions(base_list, [spec["rxn"]], [float(v) for v in spec["values"]], apply=False)
        base_list_result = {"raised": False, **_kcat_and_source(base_list, ["R2_EXP_1", "R2_EXP_2"])}
    except Exception:  # noqa: BLE001 --- whether it raised is the finding, not the exception type
        base_list_result = {"raised": True, "records": []}

    return {
        "suffixed": _kcat_and_source(suffixed, ["R2_EXP_1", "R2_EXP_2"]),
        "base_scalar": _kcat_and_source(base_scalar, ["R2_EXP_1", "R2_EXP_2"]),
        "base_list": base_list_result,
    }


# --------------------------------------------------------------------------- #
# copyECtoGEM / copy_ec_to_gem
# --------------------------------------------------------------------------- #

def _eccode_tokens(model, rxn_id: str) -> list[str]:
    """The ec-code annotation on one reaction, as a sorted list of tokens.

    Compared as tokens rather than as MATLAB's raw ';'-joined string or geckopy's list,
    since the two sides genuinely disagree on which of those two shapes to store (a
    documented divergence, not this checkpoint's concern) --- the question here is whether
    the same codes land on the same reaction, not which container holds them.
    """
    value = model.reactions.get_by_id(rxn_id).annotation.get("ec-code")
    if not value:
        return []
    if isinstance(value, str):
        tokens = value.split(";")
    else:
        tokens = list(value)
    return sorted(t for t in tokens if t)


def _checkpoint_copy_ec(adapter, conv, inputs: dict) -> dict:
    target = inputs["overwrite_target_rxn"]

    fill_empty = _fresh_ec_model(adapter, conv)
    copy_ec_to_gem(fill_empty, overwrite=False)

    overwrite_nonempty = _fresh_ec_model(adapter, conv)
    copy_ec_to_gem(overwrite_nonempty, overwrite=False)
    before = _eccode_tokens(overwrite_nonempty, target)
    copy_ec_to_gem(overwrite_nonempty, overwrite=False)  # idempotent: no new info, no change expected

    overwrite_empty = _fresh_ec_model(adapter, conv)
    # Blank the ec.eccodes entry for `target` before copying, so overwrite=True is asked to
    # replace a real annotation with nothing --- the case MATLAB clobbers and geckopy does not.
    ec_index = {r: i for i, r in enumerate(overwrite_empty.ec.rxns)}
    if target in ec_index:
        overwrite_empty.ec.eccodes[ec_index[target]] = ""
    copy_ec_to_gem(overwrite_empty, overwrite=True)

    return {
        "fill_empty": {
            r.id: _eccode_tokens(fill_empty, r.id) for r in fill_empty.reactions
        },
        "overwrite_false_unchanged": before == _eccode_tokens(overwrite_nonempty, target),
        "overwrite_true_with_empty": _eccode_tokens(overwrite_empty, target),
    }


# --------------------------------------------------------------------------- #
# mapRxnsToConv / map_rxns_to_conv
# --------------------------------------------------------------------------- #

def _checkpoint_map_rxns(adapter, conv, inputs: dict) -> dict:
    model = _fresh_ec_model(adapter, conv)

    # One synthetic value per ecModel reaction, keyed by id: the alphabetical rank among
    # this model's own reaction ids. Computed purely from the id strings, so it does not
    # depend on the two implementations agreeing on row order --- only on agreeing on the
    # *set* of ids, already confirmed by ec_model_expansion_ectestgem.
    ec_rxn_ids = sorted(r.id for r in model.reactions)
    flux_by_id = {rid: float(rank) for rank, rid in enumerate(ec_rxn_ids, start=1)}
    flux_series = __import__("pandas").Series(flux_by_id)

    result = map_rxns_to_conv(model, conv, flux_series)

    mapped = sorted(
        (
            {"reaction": rxn.id, "flux": float(value)}
            for rxn, value in zip(conv.reactions, result.mapped_flux)
        ),
        key=lambda e: e["reaction"],
    )
    usage = sorted(
        (
            {"enzyme": label, "flux": float(value)}
            for label, value in zip(result.usage_enz, result.enz_usage_flux)
        ),
        key=lambda e: e["enzyme"],
    )
    return {"mapped": mapped, "usage": usage}


# --------------------------------------------------------------------------- #
# addNewRxnsToEC / add_new_rxns_to_ec
# --------------------------------------------------------------------------- #

def _parse_equation(equation: str) -> tuple[list[str], list[str], bool]:
    """RAVEN's bracketed equation syntax ('m1[c] <=> e2[e]') -> (reactants, products, reversible)."""
    reversible = "<=>" in equation
    separator = "<=>" if reversible else "=>"
    left, right = (side.strip() for side in equation.split(separator))
    reactants = [m.strip() for m in left.split("+")] if left else []
    products = [m.strip() for m in right.split("+")] if right else []
    return reactants, products, reversible


def _bracket_to_cobra_id(token: str) -> str:
    """'m1[c]' -> 'm1c', matching this model's own metabolite-id convention."""
    name, compartment = token.rstrip("]").split("[")
    return f"{name}{compartment}"


def _checkpoint_add_new_rxns(adapter, conv, inputs: dict) -> dict:
    model = _fresh_ec_model(adapter, conv)

    spec = inputs["new_reaction"]
    reactants, products, reversible = _parse_equation(spec["equation"])

    new_rxn = cobra.Reaction(id=spec["id"], name=spec["name"])
    new_rxn.lower_bound = -1000.0 if reversible else 0.0
    new_rxn.upper_bound = 1000.0
    for token in reactants:
        new_rxn.add_metabolites({model.metabolites.get_by_id(_bracket_to_cobra_id(token)): -1.0})
    for token in products:
        new_rxn.add_metabolites({model.metabolites.get_by_id(_bracket_to_cobra_id(token)): 1.0})
    new_rxn.gene_reaction_rule = spec["gr_rule"]

    new_enzymes = [NewEnzyme(enzyme=e["enzyme"], gene=e["gene"], mw=float(e["mw"])) for e in inputs["new_enzymes"]]

    result = add_new_rxns_to_ec(model, [new_rxn], new_enzymes)

    return {
        "rxns_added": sorted(result.rxns_added),
        "enz_added": sorted(result.enz_added),
        "model": _model_summary(model),
    }


def run(ctx):
    inputs = ctx["inputs"]
    adapter, conv = _base_model(inputs)

    return {
        "reactions_from_enzyme": _checkpoint_reactions_from_enzyme(adapter, conv, inputs),
        "set_kcat": _checkpoint_set_kcat(adapter, conv, inputs),
        "copy_ec": _checkpoint_copy_ec(adapter, conv, inputs),
        "map_rxns": _checkpoint_map_rxns(adapter, conv, inputs),
        "add_new_rxns": _checkpoint_add_new_rxns(adapter, conv, inputs),
    }
