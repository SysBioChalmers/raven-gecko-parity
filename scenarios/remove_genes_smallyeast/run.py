"""Python side of the gene-removal scenario.

``remove_genes`` returns the reactions it found blocked; RAVEN's
``removeGenes`` returns only the updated model. Both checkpoints therefore
report the blocked set as what this side returns directly, and everything
else --- reaction/metabolite/gene counts, the affected reactions' bounds and
GPRs --- as a comparison of the model before and after.

Only the three touched reactions (PGI, PFK, HXK) are inspected in detail: the
rest of the model is untouched by construction, and re-comparing all 53
reactions would bury the three that matter.
"""

from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import gpr_to_dnf, remove_genes

TOUCHED = ("PGI", "PFK", "HXK")


def run(ctx):
    inputs = ctx["inputs"]
    return {
        "constrained": _checkpoint(inputs, policy="constrain"),
        "removed": _checkpoint(inputs, policy="remove"),
    }


def _checkpoint(inputs, *, policy):
    model = read_yaml_model(inputs["model"])
    genes = [str(gene) for gene in inputs["removed_genes"]]

    before_rxns = {rxn.id for rxn in model.reactions}
    before_mets = {met.id for met in model.metabolites}
    before_genes = {gene.id for gene in model.genes}

    blocked = remove_genes(
        model, genes, blocked_reactions=policy, remove_orphans=True
    )

    after_rxns = {rxn.id for rxn in model.reactions}

    return {
        "n_reactions_before": len(before_rxns),
        "n_reactions_after": len(after_rxns),
        "n_metabolites_before": len(before_mets),
        "n_metabolites_after": len(model.metabolites),
        "n_genes_before": len(before_genes),
        "n_genes_after": len(model.genes),
        "removed_reactions": sorted(before_rxns - after_rxns),
        "blocked_reactions": sorted(blocked),
        "reactions": [_reaction_state(model, rid) for rid in TOUCHED],
    }


def _reaction_state(model, rxn_id):
    if rxn_id not in model.reactions:
        return {
            "reaction": rxn_id, "present": False,
            "lower_bound": 0.0, "upper_bound": 0.0, "clauses": [],
        }
    rxn = model.reactions.get_by_id(rxn_id)
    # As sorted DNF clauses rather than the raw grRule/gene_reaction_rule
    # string: a bracketing or case difference in how each side renders a rule
    # back to text would otherwise read as a divergence in gene logic.
    clauses = [sorted(clause) for clause in gpr_to_dnf(rxn.gpr)]
    clauses.sort()
    return {
        "reaction": rxn_id,
        "present": True,
        "lower_bound": float(rxn.lower_bound),
        "upper_bound": float(rxn.upper_bound),
        "clauses": clauses,
    }
