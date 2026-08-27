"""Python side of the compartment-copying scenario.

``copy_to_compartment`` takes one target compartment where RAVEN's
``copyToComps`` takes a list of them; the scenario names one, which is the case
both signatures express.

New reactions and metabolites are derived by difference from the model before
and after, not read from the return value: RAVEN returns only the updated model,
so the difference is the one quantity both sides can state.
"""

from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import copy_to_compartment


def run(ctx):
    inputs = ctx["inputs"]
    return {
        "copy": _checkpoint(inputs, delete_original=False),
        "move": _checkpoint(inputs, delete_original=True),
    }


def _checkpoint(inputs, *, delete_original):
    model = read_yaml_model(inputs["model"])
    before_rxns = {rxn.id for rxn in model.reactions}
    before_mets = {met.id for met in model.metabolites}

    out, _new_rxns, _new_mets = copy_to_compartment(
        model,
        [str(rxn) for rxn in inputs["reactions"]],
        str(inputs["target_compartment"]),
        target_compartment_name=str(inputs["target_compartment_name"]),
        delete_original=delete_original,
    )

    after_rxns = {rxn.id for rxn in out.reactions}
    after_mets = {met.id for met in out.metabolites}

    return {
        "n_reactions_before": len(before_rxns),
        "n_reactions_after": len(after_rxns),
        "n_metabolites_before": len(before_mets),
        "n_metabolites_after": len(after_mets),
        "new_reactions": sorted(after_rxns - before_rxns),
        "removed_reactions": sorted(before_rxns - after_rxns),
        "new_metabolites": _species(
            met for met in out.metabolites if met.id not in before_mets
        ),
        "compartments": [
            {"id": str(cid), "name": str(name or "")}
            for cid, name in sorted(out.compartments.items())
        ],
        "reactions": sorted(after_rxns),
        # By species and compartment, not by id --- see scenario.yml.
        "metabolites": _species(out.metabolites),
        "bounds": [
            {
                "reaction": rxn.id,
                "lower_bound": float(rxn.lower_bound),
                "upper_bound": float(rxn.upper_bound),
            }
            for rxn in sorted(out.reactions, key=lambda r: r.id)
        ],
        # The copies must carry the originals' gene associations, or a copied
        # pathway arrives with no enzymes behind it.
        "gene_rules": _gene_rules(out),
        "stoichiometry": _stoichiometry(out),
    }


def _species(metabolites):
    """Metabolites as (name, compartment), the identity that survives both
    naming conventions."""
    records = [
        {"name": str(met.name or ""), "compartment": str(met.compartment or "")}
        for met in metabolites
    ]
    records.sort(key=lambda r: (r["compartment"], r["name"]))
    return records


def _gene_rules(model):
    from raven_toolbox.manipulation import gpr_to_dnf

    rules = []
    for rxn in sorted(model.reactions, key=lambda r: r.id):
        clauses = [sorted(clause) for clause in gpr_to_dnf(rxn.gpr)]
        clauses.sort()
        rules.append({"reaction": rxn.id, "clauses": clauses})
    return rules


def _stoichiometry(model):
    entries = [
        {
            "reaction": rxn.id,
            "species": str(met.name or ""),
            "compartment": str(met.compartment or ""),
            "coefficient": float(coeff),
        }
        for rxn in model.reactions
        for met, coeff in rxn.metabolites.items()
    ]
    entries.sort(key=lambda e: (e["reaction"], e["compartment"], e["species"]))
    return entries
