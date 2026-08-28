"""Python side of the ftINIT scoring stage.

Two checkpoints:

``gene_scores``
    ``gene_scores_from_expression`` --- RAVEN's ``5*log(level/reference)``,
    clamped to [-5, 10].

``reaction_scores``
    ``score_reactions_from_genes`` --- the GPR walk, isozymes combined with
    ``max`` and complexes with ``min``.

RAVEN does both in one call (``scoreComplexModel`` returns ``geneScores`` and
``rxnScores``), so the split is on this side only; the two result documents
still line up checkpoint for checkpoint.

A gene with no expression value is reported as ``has_score: false`` with a zero
rather than as a NaN: MATLAB's jsonencode writes NaN as null while this side
canonicalises it to the string "NaN", so a genuinely absent score would read as
a difference between the two harnesses.
"""

from raven_toolbox.init import gene_scores_from_expression, score_reactions_from_genes
from raven_toolbox.io import read_yaml_model


def run(ctx):
    inputs = ctx["inputs"]
    model = read_yaml_model(inputs["model"])
    model_genes = sorted(gene.id for gene in model.genes)

    expression = _read_expression(inputs["expression"], set(model_genes))
    gene_scores = gene_scores_from_expression(expression, float(inputs["threshold"]))

    reaction_scores = score_reactions_from_genes(
        model,
        gene_scores,
        isozyme_scoring=str(inputs["isozyme_scoring"]),
        complex_scoring=str(inputs["complex_scoring"]),
        no_gene_score=float(inputs["no_gene_score"]),
    )

    return {
        "gene_scores": {
            "n_genes": len(model_genes),
            "n_scored": sum(1 for gene in model_genes if gene in gene_scores),
            "scores": [
                {
                    "gene": gene,
                    "has_score": gene in gene_scores,
                    "score": float(gene_scores.get(gene, 0.0)),
                }
                for gene in model_genes
            ],
        },
        "reaction_scores": {
            "n_reactions": len(reaction_scores),
            "scores": [
                {"reaction": rxn, "score": float(reaction_scores[rxn])}
                for rxn in sorted(reaction_scores)
            ],
        },
    }


def _read_expression(path, wanted):
    """Two columns, tab separated: gene, level.

    First occurrence wins and the table is restricted to *wanted*, both done
    here rather than left to either toolbox --- see scenario.yml.
    """
    expression = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            gene, _, level = line.partition("\t")
            gene = gene.strip()
            if gene in wanted and gene not in expression:
                expression[gene] = float(level)
    return expression
