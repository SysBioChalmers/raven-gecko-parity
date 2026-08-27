"""Python side of the model-merging scenario.

``merge_models`` returns a new model; RAVEN's ``mergeModels`` returns a struct
carrying ``rxnFrom`` / ``metFrom`` / ``geneFrom``. Both are reduced here to the
same three questions: what is in the merged model, which reaction ids had to be
renamed, and where each entity came from.

Shape rules, per docs/scenarios.md: sort everything, always emit every key,
lists of records rather than objects keyed by model identifiers.
"""

import warnings

from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import gpr_to_dnf, merge_models


def run(ctx):
    inputs = ctx["inputs"]
    first = read_yaml_model(inputs["first"])
    second = read_yaml_model(inputs["second"])

    original_ids = {rxn.id for rxn in first.reactions} | {rxn.id for rxn in second.reactions}

    # merge_models warns when two models map a metabolite key to different
    # formulae or charges. That is information about the *fixture*, not about
    # parity, and RAVEN has no matching channel for it, so it is silenced here
    # rather than left to pollute the run.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        merged = merge_models([first, second])

    return {
        "model_id": str(merged.id or ""),
        "n_reactions": len(merged.reactions),
        "n_metabolites": len(merged.metabolites),
        "n_genes": len(merged.genes),
        "reactions": sorted(rxn.id for rxn in merged.reactions),
        # Derived by difference from the two inputs rather than by matching on
        # a suffix, so a reaction that already ended in "_smallYeastBad" could
        # not be miscounted as a rename.
        "renamed_reactions": sorted(
            rxn.id for rxn in merged.reactions if rxn.id not in original_ids
        ),
        "metabolites": _metabolite_records(merged),
        "genes": sorted(gene.id for gene in merged.genes),
        "reaction_origins": _origins(merged),
        "gene_rules": _gene_rules(merged),
        "stoichiometry": _stoichiometry(merged),
    }


def _metabolite_records(model):
    """Id plus the name and compartment that unification matched on."""
    return [
        {
            "id": met.id,
            "name": str(met.name or ""),
            "compartment": str(met.compartment or ""),
        }
        for met in sorted(model.metabolites, key=lambda m: m.id)
    ]


def _origins(model):
    return [
        {"reaction": rxn.id, "origin": str((rxn.notes or {}).get("origin", ""))}
        for rxn in sorted(model.reactions, key=lambda r: r.id)
    ]


def _gene_rules(model):
    rules = []
    for rxn in sorted(model.reactions, key=lambda r: r.id):
        clauses = [sorted(clause) for clause in gpr_to_dnf(rxn.gpr)]
        clauses.sort()
        rules.append({"reaction": rxn.id, "clauses": clauses})
    return rules


def _stoichiometry(model):
    entries = [
        {"reaction": rxn.id, "metabolite": met.id, "coefficient": float(coeff)}
        for rxn in model.reactions
        for met, coeff in rxn.metabolites.items()
    ]
    entries.sort(key=lambda e: (e["reaction"], e["metabolite"]))
    return entries
