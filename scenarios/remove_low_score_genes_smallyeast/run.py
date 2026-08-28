"""Python side of the low-score-gene-pruning scenario.

``remove_low_score_genes`` returns a new model rather than mutating in place,
same convention as RAVEN's ``removeLowScoreGenes``.

The synthetic PGI rule is built with ``change_gene_reaction_rules`` --- already
cross-validated by change_gene_rules_smallyeast, so leaning on it here to
reach a complex/isozyme mix smallYeast has no natural example of is safe
rather than circular.

Every reaction other than the three the scenario targets is fingerprinted
before and after: the function's whole contract is that it prunes exactly the
genes it should and touches nothing else, and that is only evidence if the
rest of the model is looked at too.
"""

from raven_toolbox.init import remove_low_score_genes
from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import change_gene_reaction_rules, gpr_to_dnf

TARGETS = ("HXK", "PFK", "PGI")


def run(ctx):
    inputs = ctx["inputs"]
    model = read_yaml_model(inputs["model"])

    synthetic = inputs["synthetic_rule"]
    change_gene_reaction_rules(
        model, {str(synthetic["reaction"]): str(synthetic["grRule"])}, replace=True
    )

    before_other = {
        rxn.id: _clauses(rxn) for rxn in model.reactions if rxn.id not in TARGETS
    }
    n_genes_before = len(model.genes)

    scores = {str(k): float(v) for k, v in dict(inputs["scores"]).items()}
    reduced, removed = remove_low_score_genes(
        model,
        scores,
        isozyme_scoring=str(inputs["isozyme_scoring"]),
        complex_scoring=str(inputs["complex_scoring"]),
    )

    after_other = {
        rxn.id: _clauses(rxn) for rxn in reduced.reactions if rxn.id not in TARGETS
    }

    return {
        "n_genes_before": n_genes_before,
        "n_genes_after": len(reduced.genes),
        "removed_genes": sorted(removed),
        "reactions": [
            {"reaction": rxn_id, "clauses": _clauses(reduced.reactions.get_by_id(rxn_id))}
            for rxn_id in TARGETS
        ],
        "n_untouched_reactions_checked": len(before_other),
        # The point of the scenario: this should be empty on both sides.
        "unexpectedly_changed_reactions": sorted(
            rid for rid in before_other if before_other[rid] != after_other.get(rid)
        ),
    }


def _clauses(rxn):
    clauses = [sorted(clause) for clause in gpr_to_dnf(rxn.gpr)]
    clauses.sort()
    return clauses
