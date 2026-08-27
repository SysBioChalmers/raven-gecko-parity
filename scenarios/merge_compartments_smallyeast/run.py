"""Python side of the compartment-merging scenario.

``merge_compartments`` is handed a name-based grouping key rather than left on
its default id-suffix one, because RAVEN groups by ``metNames`` and the point
of the scenario is the grouping, not each side's idea of what to call the
result. See scenario.yml.

Reactions removed by the merge are reported as the difference between the model
before and after, not as the lists each function returns: RAVEN reports
``deletedRxns`` for the deleteRxnsWithOneMet mode only, and removes the
reactions that cancelled to nothing separately without reporting them, so the
returned lists are not the same quantity on the two sides. The difference is.
"""

from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import merge_compartments


def run(ctx):
    inputs = ctx["inputs"]
    model = read_yaml_model(inputs["model"])

    before_rxns = {rxn.id for rxn in model.reactions}
    before_species = {met.name for met in model.metabolites}

    merged, _deleted, deduplicated = merge_compartments(
        model,
        merged_id=str(inputs["merged_compartment"]),
        base_metabolite=lambda met: met.name,
        drop_single_metabolite_reactions=bool(inputs["delete_single_metabolite_reactions"]),
        deduplicate_reactions=True,
    )

    after_rxns = {rxn.id for rxn in merged.reactions}

    return {
        "n_reactions_before": len(before_rxns),
        "n_reactions_after": len(after_rxns),
        "n_species_before": len(before_species),
        "n_metabolites_before": len(model.metabolites),
        "n_metabolites_after": len(merged.metabolites),
        "compartments": sorted(merged.compartments),
        "reactions": sorted(after_rxns),
        "removed_reactions": sorted(before_rxns - after_rxns),
        "deduplicated_reactions": sorted(deduplicated),
        "metabolites": sorted(met.name for met in merged.metabolites),
        "bounds": [
            {
                "reaction": rxn.id,
                "lower_bound": float(rxn.lower_bound),
                "upper_bound": float(rxn.upper_bound),
            }
            for rxn in sorted(merged.reactions, key=lambda r: r.id)
        ],
        # Keyed by species name for the same reason the metabolite list is:
        # this is where the coefficient summing shows up, and it is the part
        # of the merge with any arithmetic in it.
        "stoichiometry": _stoichiometry(merged),
    }


def _stoichiometry(model):
    entries = [
        {"reaction": rxn.id, "species": str(met.name), "coefficient": float(coeff)}
        for rxn in model.reactions
        for met, coeff in rxn.metabolites.items()
    ]
    entries.sort(key=lambda e: (e["reaction"], e["species"]))
    return entries
