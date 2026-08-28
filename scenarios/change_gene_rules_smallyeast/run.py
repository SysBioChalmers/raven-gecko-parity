"""Python side of the gene-rule-setting scenario.

``change_gene_reaction_rules`` takes a mapping of reaction id to GPR string;
RAVEN's ``changeGrRules`` takes parallel arrays of the same. Both create any
gene mentioned in a new rule that the model does not already have.

Only ``replace`` mode and ``append`` mode onto a reaction that already carries
a GPR are covered --- see scenario.yml for why append mode onto an empty GPR
is a confirmed divergence (raven-gecko-parity#12) rather than a checkpoint
here.
"""

from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import change_gene_reaction_rules, gpr_to_dnf


def run(ctx):
    inputs = ctx["inputs"]
    return {
        "replace": _checkpoint(inputs, dict(inputs["replaced"]), replace=True),
        "append": _checkpoint(inputs, dict(inputs["appended"]), replace=False),
    }


def _checkpoint(inputs, rules, *, replace):
    model = read_yaml_model(inputs["model"])
    before_genes = {gene.id for gene in model.genes}

    rules = {str(k): str(v) for k, v in rules.items()}
    change_gene_reaction_rules(model, rules, replace=replace)

    after_genes = {gene.id for gene in model.genes}

    return {
        "n_genes_before": len(before_genes),
        "n_genes_after": len(after_genes),
        "created_genes": sorted(after_genes - before_genes),
        "reactions": [
            _fingerprint(model.reactions.get_by_id(rxn_id))
            for rxn_id in sorted(rules)
        ],
    }


def _fingerprint(rxn):
    clauses = [sorted(clause) for clause in gpr_to_dnf(rxn.gpr)]
    clauses.sort()
    return {"reaction": rxn.id, "clauses": clauses}
