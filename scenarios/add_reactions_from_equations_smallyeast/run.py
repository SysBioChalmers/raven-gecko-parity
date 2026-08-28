"""Python side of the equation-parsing scenario.

``add_reactions_from_equations`` takes a sequence of mappings where RAVEN's
``addRxns`` takes a struct of parallel arrays, but the fields line up one for
one: id/rxns, equation/equations, name/rxnNames, gene_reaction_rule/grRules,
bounds/(lb, ub).

Two calls rather than one, because RAVEN takes lb and ub as vectors over the
whole batch --- see scenario.yml.
"""

from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import add_reactions_from_equations, gpr_to_dnf


def run(ctx):
    inputs = ctx["inputs"]
    return {
        "from_arrows": _checkpoint(inputs, inputs["arrow_reactions"], bounded=False),
        "explicit_bounds": _checkpoint(inputs, inputs["bounded_reactions"], bounded=True),
    }


def _checkpoint(inputs, declared, *, bounded):
    model = read_yaml_model(inputs["model"])
    before_rxns = {rxn.id for rxn in model.reactions}
    before_mets = {met.id for met in model.metabolites}
    before_genes = {gene.id for gene in model.genes}

    specs = []
    for entry in declared:
        spec = {
            "id": str(entry["id"]),
            "equation": str(entry["equation"]),
            "name": str(entry.get("name", "")),
        }
        rule = str(entry.get("gene_reaction_rule", ""))
        if rule:
            spec["gene_reaction_rule"] = rule
        if bounded:
            spec["bounds"] = (float(entry["lower_bound"]), float(entry["upper_bound"]))
        specs.append(spec)

    add_reactions_from_equations(
        model,
        specs,
        mets_by="id",
        compartment=str(inputs["compartment"]),
        allow_new_mets=bool(inputs["allow_new_mets"]),
        allow_new_genes=bool(inputs["allow_new_genes"]),
    )

    after_rxns = {rxn.id for rxn in model.reactions}
    after_mets = {met.id for met in model.metabolites}
    after_genes = {gene.id for gene in model.genes}

    added = sorted(after_rxns - before_rxns)
    return {
        "n_reactions_before": len(before_rxns),
        "n_reactions_after": len(after_rxns),
        "n_metabolites_before": len(before_mets),
        "n_metabolites_after": len(after_mets),
        "n_genes_before": len(before_genes),
        "n_genes_after": len(after_genes),
        "added_reactions": added,
        "added_metabolites": sorted(after_mets - before_mets),
        "added_genes": sorted(after_genes - before_genes),
        # Only the added reactions, in detail: the rest of the model is
        # untouched and comparing all 53 again would bury the six that matter.
        "added_detail": [
            {
                "reaction": rxn_id,
                "name": str(model.reactions.get_by_id(rxn_id).name or ""),
                "lower_bound": float(model.reactions.get_by_id(rxn_id).lower_bound),
                "upper_bound": float(model.reactions.get_by_id(rxn_id).upper_bound),
                "clauses": _clauses(model.reactions.get_by_id(rxn_id)),
                "stoichiometry": _stoichiometry(model.reactions.get_by_id(rxn_id)),
            }
            for rxn_id in added
        ],
        # A created metabolite has to land somewhere sensible, not just exist.
        # Its *name* is deliberately not compared --- see scenario.yml.
        "added_metabolite_detail": [
            {
                "metabolite": met.id,
                "compartment": str(met.compartment or ""),
            }
            for met in sorted(
                (m for m in model.metabolites if m.id not in before_mets),
                key=lambda m: m.id,
            )
        ],
    }


def _clauses(rxn):
    clauses = [sorted(clause) for clause in gpr_to_dnf(rxn.gpr)]
    clauses.sort()
    return clauses


def _stoichiometry(rxn):
    entries = [
        {"metabolite": met.id, "coefficient": float(coeff)}
        for met, coeff in rxn.metabolites.items()
    ]
    entries.sort(key=lambda e: e["metabolite"])
    return entries
