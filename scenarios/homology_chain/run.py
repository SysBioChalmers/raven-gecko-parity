"""Python side of the homology chain.

Two checkpoints in one run:

``blast``
    The bidirectional hit table from the same two FASTA files the MATLAB side
    searches, with the same binary and the same e-value. Both toolboxes ship
    BLAST+ 2.17.0 -- RAVEN in ``software/``, raven-toolbox fetched from
    raven-data -- so identical input should give an identical table. If it does
    not, the difference is in how the two parse or filter the output, which is
    exactly what this checkpoint isolates.

``draft``
    The model built from a *fixed* ortholog mapping rather than from the BLAST
    hits above. The galactosidase sequences have no model behind them, and
    pinning the mapping leaves the model-building logic -- reaction transfer,
    GPR rewriting, gene renaming -- as the only variable.

Shape rules, per docs/scenarios.md: sort everything, always emit every key, use
lists of records rather than objects keyed by model identifiers.
"""

from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import gpr_to_dnf
from raven_toolbox.reconstruction.homology import (
    get_model_from_homology,
    make_ortholog_hits,
    run_blast,
)


def run(ctx):
    inputs = ctx["inputs"]
    return {
        "blast": _blast_checkpoint(inputs),
        "draft": _draft_checkpoint(inputs),
    }


def _blast_checkpoint(inputs):
    hits = run_blast(
        inputs["query_id"],
        inputs["query_fasta"],
        [inputs["ref_id"]],
        [inputs["ref_fasta"]],
        evalue=float(inputs["blast_evalue"]),
    )

    records = [
        {
            "from_id": str(row.from_id),
            "to_id": str(row.to_id),
            "from_gene": str(row.from_gene),
            "to_gene": str(row.to_gene),
            "evalue": float(row.evalue),
            "identity": float(row.identity),
            "align_len": int(row.align_len),
            "bitscore": float(row.bitscore),
            "ppos": float(row.ppos),
        }
        for row in hits.itertuples()
    ]
    records.sort(key=lambda r: (r["from_id"], r["to_id"], r["from_gene"], r["to_gene"]))

    # Per-direction counts, as a sorted list of records: a direction that goes
    # missing entirely is then a value difference rather than a structural one.
    directions: dict[tuple[str, str], int] = {}
    for record in records:
        key = (record["from_id"], record["to_id"])
        directions[key] = directions.get(key, 0) + 1

    return {
        "n_hits": len(records),
        "directions": [
            {"from_id": f, "to_id": t, "n_hits": n}
            for (f, t), n in sorted(directions.items())
        ],
        "hits": records,
    }


def _draft_checkpoint(inputs):
    template = read_yaml_model(inputs["model"])
    template.id = inputs["source_model_id"]

    # Sorted, not model order: the two toolboxes need not store genes the same
    # way, and the mapping must not depend on that.
    source_genes = sorted(gene.id for gene in template.genes)
    count = min(int(inputs["ortholog_count"]), len(source_genes))
    pairs = [(gene, f"t_{gene}") for gene in source_genes[:count]]

    hits = make_ortholog_hits(
        pairs, inputs["source_model_id"], inputs["target_organism_id"]
    )
    draft = get_model_from_homology(
        [template], hits, inputs["target_organism_id"]
    ).model

    reactions = sorted(rxn.id for rxn in draft.reactions)
    return {
        "n_reactions": len(reactions),
        "n_metabolites": len(draft.metabolites),
        "n_genes": len(draft.genes),
        "ortholog_pairs": [{"source": s, "target": t} for s, t in pairs],
        "reactions": reactions,
        "metabolites": sorted(met.id for met in draft.metabolites),
        "genes": sorted(gene.id for gene in draft.genes),
        "gene_rules": _gene_rules(draft),
        "stoichiometry": _stoichiometry(draft),
    }


def _gene_rules(model):
    """GPRs as sorted DNF clauses, so ``A or B`` and ``B or A`` compare equal."""
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
            "metabolite": met.id,
            "coefficient": float(coeff),
        }
        for rxn in model.reactions
        for met, coeff in rxn.metabolites.items()
    ]
    entries.sort(key=lambda e: (e["reaction"], e["metabolite"]))
    return entries
