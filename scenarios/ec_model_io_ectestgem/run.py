"""Python side of the ecModel save/load scenario.

Three checkpoints, the same shape as raven-toolbox's own ``yaml_roundtrip_smallyeast``:
``direct`` (the ecModel before any write), ``written`` (the file ``save_ec_model`` produces,
as lines), and ``roundtrip`` (the ecModel after write then read, plus this side's own
verdict on whether the round trip was lossless). See scenario.yml for why ``direct`` here is
a freshly *built* ecModel rather than one read off disk, unlike the RAVEN scenario it mirrors.

``model.ec.concs`` is left out of the summary. ``make_ec_model`` never sets it --- every
entry is NaN --- and NaN cannot be compared with plain equality (``nan != nan``), which
would make ``identical_to_direct`` false even when nothing had actually changed. That is a
harness problem, not a finding, so the field most exposed to it is simply not part of what
this scenario asserts. ``protein_pool_ectestgem`` already exercises ``ec.concs`` with real
values.
"""

import tempfile
from pathlib import Path

from geckopy import ModelAdapter, load_conventional_gem, load_ec_model, make_ec_model, save_ec_model


def _bound(value: float) -> tuple[float, str]:
    """An infinite bound as a class and a zero --- see ec_model_expansion_ectestgem."""
    value = float(value)
    if value == float("inf"):
        return 0.0, "+inf"
    if value == float("-inf"):
        return 0.0, "-inf"
    return value, "finite"


def _adapter(inputs: dict) -> ModelAdapter:
    adapter = ModelAdapter.from_folder(inputs["adapter_python"])
    fixture = Path(inputs["fixture_dir"])
    adapter.params.path = fixture
    adapter.params.conv_gem = fixture / "models" / "testModel.xml"
    return adapter


def _gene_associations(model) -> list[dict]:
    entries = [{"reaction": rxn.id, "gene": gene.id} for rxn in model.reactions for gene in rxn.genes]
    return sorted(entries, key=lambda e: (e["reaction"], e["gene"]))


def _stoichiometry(model) -> list[dict]:
    entries = [
        {"reaction": rxn.id, "metabolite": met.id, "coefficient": float(coefficient)}
        for rxn in model.reactions
        for met, coefficient in rxn.metabolites.items()
    ]
    return sorted(entries, key=lambda e: (e["reaction"], e["metabolite"]))


def _reactions(model) -> list[dict]:
    records = []
    for rxn in sorted(model.reactions, key=lambda r: r.id):
        lower, lower_kind = _bound(rxn.lower_bound)
        upper, upper_kind = _bound(rxn.upper_bound)
        records.append(
            {
                "id": rxn.id,
                "lower_bound": lower,
                "lower_kind": lower_kind,
                "upper_bound": upper,
                "upper_kind": upper_kind,
                "objective_coefficient": float(rxn.objective_coefficient),
            }
        )
    return records


def _ec_data(ec) -> dict:
    matrix = ec.rxn_enz_mat
    if hasattr(matrix, "toarray"):
        matrix = matrix.toarray()
    coupling = [
        {"reaction": ec.rxns[i], "enzyme": ec.enzymes[j], "coefficient": float(matrix[i][j])}
        for i in range(len(ec.rxns))
        for j in range(len(ec.enzymes))
        if matrix[i][j] != 0
    ]
    return {
        # Not sorted: the expansion order is the result, as in ec_model_expansion_ectestgem.
        "rxns": [str(r) for r in ec.rxns],
        "genes": [str(g) for g in ec.genes],
        "enzymes": [str(e) for e in ec.enzymes],
        "mw": [float(m) for m in ec.mw],
        "sequence": [str(s) for s in ec.sequence],
        "eccodes": [str(c) if c else "" for c in ec.eccodes],
        "kcat": [float(k) for k in ec.kcat],
        "coupling": sorted(coupling, key=lambda e: (e["reaction"], e["enzyme"])),
    }


def _summary(model) -> dict:
    return {
        "model_id": str(model.id or ""),
        "n_reactions": len(model.reactions),
        "n_metabolites": len(model.metabolites),
        "n_genes": len(model.genes),
        "reactions": _reactions(model),
        "metabolites": [
            {"id": met.id, "name": str(met.name or ""), "compartment": str(met.compartment or "")}
            for met in sorted(model.metabolites, key=lambda m: m.id)
        ],
        "genes": sorted(gene.id for gene in model.genes),
        "gene_associations": _gene_associations(model),
        "stoichiometry": _stoichiometry(model),
        "gecko_light": bool(model.ec.gecko_light),
        "ec": _ec_data(model.ec),
    }


def _file_record(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return {"n_lines": len(lines), "n_chars": sum(len(line) for line in lines), "lines": lines}


def run(ctx):
    inputs = ctx["inputs"]
    adapter = _adapter(inputs)
    model = load_conventional_gem(adapter)
    ec_model = make_ec_model(model, adapter, gecko_light=False)

    direct = _summary(ec_model)

    with tempfile.TemporaryDirectory(prefix="parity_ecmodel_") as workdir:
        path = Path(workdir) / "ecModel.yml"
        save_ec_model(ec_model, path)
        written = _file_record(path)
        reread = load_ec_model(path)

    roundtrip_summary = _summary(reread)

    return {
        "direct": direct,
        "written": written,
        "roundtrip": {
            **roundtrip_summary,
            "identical_to_direct": roundtrip_summary == direct,
        },
    }
