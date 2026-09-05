"""Python side of the renameModelGenes/rename_model_genes scenario."""
import pandas as pd

from raven_toolbox.curation import rename_model_genes
from raven_toolbox.io import read_yaml_model


def run(ctx):
    inputs = ctx["inputs"]
    model = read_yaml_model(inputs["model"])

    gene_table = pd.DataFrame({
        inputs["from_col"]: inputs["gene_ids"],
        inputs["to_col"]: inputs["gene_names"],
    })
    # result.renamed/unmapped are Python-side bookkeeping with no structured
    # MATLAB counterpart (renameModelGenes.m only warns to the console) --
    # already covered directly by raven-toolbox's own unit tests. This
    # scenario compares the actual observable transform instead: the
    # resulting gene list and each reaction's gene set.
    rename_model_genes(model, gene_table, inputs["from_col"], inputs["to_col"])

    reaction_genes = {
        rxn.id: sorted(g.id for g in rxn.genes)
        for rxn in model.reactions
        if rxn.genes
    }

    return {
        "renamed": {
            "all_gene_ids": sorted(g.id for g in model.genes),
            "reaction_genes": reaction_genes,
        }
    }
