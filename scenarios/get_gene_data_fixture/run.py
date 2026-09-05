"""Python side of the getGeneData/get_gene_data scenario."""
from raven_toolbox.curation import get_gene_data


def run(ctx):
    table = get_gene_data(ctx["inputs"]["gff"])
    return {"parsed": table.fillna("").to_dict(orient="records")}
