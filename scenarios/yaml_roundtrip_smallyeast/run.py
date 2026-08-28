"""Python side of the YAML reader/writer scenario.

Three checkpoints --- see scenario.yml for why each exists. The writer output
is emitted line by line rather than as a digest: a digest would say the two
files differ, and the line list says where.

Both writes go to a temporary directory, not into the repository: the point is
what the writer produces, not an artefact anyone needs to keep.
"""

import tempfile
from pathlib import Path

from raven_toolbox.io import read_yaml_model, write_yaml_model
from raven_toolbox.manipulation import gpr_to_dnf


def run(ctx):
    source = ctx["inputs"]["model"]

    direct = read_yaml_model(source)

    with tempfile.TemporaryDirectory(prefix="parity_yaml_") as workdir:
        as_read = Path(workdir) / "as_read.yml"
        sorted_ids = Path(workdir) / "sorted.yml"
        write_yaml_model(direct, as_read)
        write_yaml_model(direct, sorted_ids, sort_ids=True)

        written = {
            "as_read": _file_record(as_read),
            "sorted": _file_record(sorted_ids),
        }
        reread = read_yaml_model(as_read)

    direct_summary = _summary(direct)
    roundtrip_summary = _summary(reread)

    return {
        "direct": direct_summary,
        "written": written,
        "roundtrip": {
            **roundtrip_summary,
            # This implementation's own verdict on its round trip. Both sides
            # reporting False is not a match in any useful sense, which is why
            # the summary above travels with it.
            "identical_to_direct": roundtrip_summary == direct_summary,
        },
    }


def _file_record(path: Path):
    text = path.read_text(encoding="utf-8")
    lines = text.replace("\r\n", "\n").split("\n")
    # A trailing newline is a property of the file, not a final empty line.
    if lines and lines[-1] == "":
        lines.pop()
    return {
        "n_lines": len(lines),
        "n_chars": sum(len(line) for line in lines),
        "lines": lines,
    }


def _summary(model):
    return {
        "model_id": str(model.id or ""),
        "model_name": str(model.name or ""),
        "n_reactions": len(model.reactions),
        "n_metabolites": len(model.metabolites),
        "n_genes": len(model.genes),
        "compartments": [
            {"id": str(cid), "name": str(name or "")}
            for cid, name in sorted(model.compartments.items())
        ],
        "reactions": [
            {
                "id": rxn.id,
                "name": str(rxn.name or ""),
                "lower_bound": float(rxn.lower_bound),
                "upper_bound": float(rxn.upper_bound),
                "objective_coefficient": float(rxn.objective_coefficient),
            }
            for rxn in sorted(model.reactions, key=lambda r: r.id)
        ],
        "metabolites": [
            {
                "id": met.id,
                "name": str(met.name or ""),
                "compartment": str(met.compartment or ""),
                "formula": str(met.formula or ""),
                # A missing charge is a flag plus a zero, not NaN: MATLAB's
                # jsonencode writes NaN as null while Python writes the string
                # "NaN", so a genuinely absent charge would read as a shape
                # difference between the two harnesses.
                "has_charge": met.charge is not None,
                "charge": float(met.charge) if met.charge is not None else 0.0,
            }
            for met in sorted(model.metabolites, key=lambda m: m.id)
        ],
        "genes": sorted(gene.id for gene in model.genes),
        "gene_rules": _gene_rules(model),
        "stoichiometry": _stoichiometry(model),
    }


def _gene_rules(model):
    """GPRs as sorted DNF clauses, so bracketing and gene order are not the test."""
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
