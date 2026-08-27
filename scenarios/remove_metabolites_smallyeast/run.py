"""Python side of the metabolite-removal scenario.

``remove_metabolites`` wraps cobra's own ``remove_metabolites``, adding only
the by-name cross-compartment matching (RAVEN's ``isNames``); the base
deletion is cobra's, non-destructive by default, which silently strips the
metabolite from every reaction that used it rather than touching the
reactions themselves.

Two checkpoints: id-based removal (checking what happens to a many-metabolite
reaction versus a single-metabolite one), and name-based removal across
compartments. Reactions are inspected before and after by id, since removal
never renames or reorders what survives.
"""

from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import remove_metabolites

# Reactions ATP_c and GLY_c touch, chosen ahead of time so the detail is
# reported for exactly the reactions the removal affects.
TOUCHED_BY_ID = (
    "glyOUT", "GPP", "HXK", "PFK", "PGK", "PYK",
    "ACS", "PYC", "LSC1LSC2", "PCK", "GROWTH", "NADHX", "FADHX", "ATPX",
)


def run(ctx):
    inputs = ctx["inputs"]
    return {
        "by_id": _by_id_checkpoint(inputs),
        "by_name": _by_name_checkpoint(inputs),
    }


def _by_id_checkpoint(inputs):
    model = read_yaml_model(inputs["model"])
    before_mets = {met.id for met in model.metabolites}
    before_sizes = {rxn.id: len(rxn.metabolites) for rxn in model.reactions}

    remove_metabolites(model, [str(m) for m in inputs["removed_by_id"]])

    after_mets = {met.id for met in model.metabolites}
    return {
        "n_reactions": len(model.reactions),
        "n_metabolites_before": len(before_mets),
        "n_metabolites_after": len(after_mets),
        "removed_metabolites": sorted(before_mets - after_mets),
        "reactions": [
            {
                "reaction": rxn_id,
                "n_metabolites_before": before_sizes[rxn_id],
                "n_metabolites_after": len(model.reactions.get_by_id(rxn_id).metabolites),
                "stoichiometry": _stoichiometry(model.reactions.get_by_id(rxn_id)),
            }
            for rxn_id in TOUCHED_BY_ID
        ],
    }


def _by_name_checkpoint(inputs):
    model = read_yaml_model(inputs["model"])
    before_mets = {met.id for met in model.metabolites}

    remove_metabolites(model, [str(inputs["removed_by_name"])], by_name=True)

    after_mets = {met.id for met in model.metabolites}
    return {
        "n_reactions": len(model.reactions),
        "n_metabolites_before": len(before_mets),
        "n_metabolites_after": len(after_mets),
        "removed_metabolites": sorted(before_mets - after_mets),
    }


def _stoichiometry(rxn):
    entries = [
        {"metabolite": met.id, "coefficient": float(coeff)}
        for met, coeff in rxn.metabolites.items()
    ]
    entries.sort(key=lambda e: e["metabolite"])
    return entries
