"""Python side of the reaction-transfer scenario.

``add_reactions_from_model`` and RAVEN's ``addRxnsGenesMets`` take the same
three arguments and the same three options; the draft is prepared identically on
both sides by removing the reactions along with the metabolites and genes they
leave unused.

What was added is derived by difference from the model before and after rather
than from the return value: RAVEN returns the updated model where this side
returns the reaction objects, so the difference is what both can state.
"""

from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import add_reactions_from_model, gpr_to_dnf


def run(ctx):
    inputs = ctx["inputs"]
    return {
        "with_genes": _checkpoint(inputs, genes=True),
        "without_genes": _checkpoint(inputs, genes=False),
    }


def _checkpoint(inputs, *, genes):
    transferred = [str(rxn) for rxn in inputs["transferred_reactions"]]

    draft = read_yaml_model(inputs["model"])
    # remove_orphans prunes the metabolites and genes the removed reactions
    # leave unused, matching removeUnusedMets / removeUnusedGenes on the other
    # side. Without it the transfer would have nothing to create.
    draft.remove_reactions(transferred, remove_orphans=True)

    before_rxns = {rxn.id for rxn in draft.reactions}
    before_mets = {met.id for met in draft.metabolites}
    before_genes = {gene.id for gene in draft.genes}

    source = read_yaml_model(inputs["model"])
    add_reactions_from_model(
        draft,
        source,
        transferred,
        genes=genes,
        note=str(inputs["note"]),
        confidence=int(inputs["confidence"]),
    )

    after_rxns = {rxn.id for rxn in draft.reactions}
    after_mets = {met.id for met in draft.metabolites}
    after_genes = {gene.id for gene in draft.genes}

    return {
        "n_reactions_before": len(before_rxns),
        "n_reactions_after": len(after_rxns),
        "n_metabolites_before": len(before_mets),
        "n_metabolites_after": len(after_mets),
        "n_genes_before": len(before_genes),
        "n_genes_after": len(after_genes),
        "added_reactions": sorted(after_rxns - before_rxns),
        "added_metabolites": sorted(after_mets - before_mets),
        "added_genes": sorted(after_genes - before_genes),
        "reactions": sorted(after_rxns),
        "metabolites": sorted(after_mets),
        "genes": sorted(after_genes),
        "bounds": [
            {
                "reaction": rxn.id,
                "lower_bound": float(rxn.lower_bound),
                "upper_bound": float(rxn.upper_bound),
            }
            for rxn in sorted(draft.reactions, key=lambda r: r.id)
        ],
        "gene_rules": _gene_rules(draft),
        # The provenance a curator later reads off a transferred reaction.
        "transfer_annotations": [
            {
                "reaction": rxn_id,
                "note": str((draft.reactions.get_by_id(rxn_id).notes or {}).get("note", "")),
                "confidence": float(
                    (draft.reactions.get_by_id(rxn_id).notes or {}).get("confidence_score", 0)
                ),
            }
            for rxn_id in sorted(after_rxns - before_rxns)
        ],
        "stoichiometry": _stoichiometry(draft),
    }


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
