"""Python side of the ecModel-expansion scenario.

Returns plain, sorted data only. The result document is a set of checkpoints ---
`adapter`, `conventional`, `full`, `light` --- rather than one flat comparison, because
the four fail for different reasons: a difference in `adapter` means the two fixtures
have drifted apart, a difference in `conventional` means the two SBML readers disagree,
and only a difference in `full` or `light` is makeEcModel itself.
"""

from pathlib import Path

from geckopy import ModelAdapter, load_conventional_gem, make_ec_model

#: Infinite bounds are the one place a JSON round trip loses information: MATLAB's
#: jsonencode writes Inf as null, which the Python side canonicalises to the string
#: "Infinity", so an open bound would read as a difference between the two *harnesses*.
#: Every bound is therefore emitted as a finite value plus a class, exactly the
#: has_charge/charge convention docs/scenarios.md describes.
def _bound(value: float) -> tuple[float, str]:
    value = float(value)
    if value == float("inf"):
        return 0.0, "+inf"
    if value == float("-inf"):
        return 0.0, "-inf"
    return value, "finite"


def _adapter(ctx_inputs: dict) -> ModelAdapter:
    """geckopy's ecTestGEM adapter, repointed at the GECKO copy of the fixture.

    The parameters come from geckopy's own model_adapter.toml --- that is the thing being
    compared against MATLAB's TestGEMAdapter.m. Only `path` and `conv_gem` are moved, so
    that both implementations read the same model file and the same data/uniprot.tsv.
    """
    adapter = ModelAdapter.from_folder(ctx_inputs["adapter_python"])
    fixture = Path(ctx_inputs["fixture_dir"])
    adapter.params.path = fixture
    adapter.params.conv_gem = fixture / "models" / "testModel.xml"
    return adapter


def _adapter_params(adapter: ModelAdapter) -> dict:
    p = adapter.params
    return {
        "org_name": str(p.org_name),
        "sigma": float(p.sigma),
        "p_tot": float(p.p_tot),
        "f": float(p.f),
        "gr_exp": float(p.gr_exp),
        "c_source": str(p.c_source),
        "bio_rxn": str(p.bio_rxn),
        "enzyme_comp": str(p.enzyme_comp),
        "kegg_id": str(p.kegg.id),
        "kegg_gene_id": str(p.kegg.gene_id),
        "uniprot_type": str(p.uniprot.type),
        "uniprot_id": str(p.uniprot.id),
        "uniprot_gene_id_field": str(p.uniprot.gene_id_field),
        "uniprot_reviewed": bool(p.uniprot.reviewed),
        "complex_taxonomic_id": int(p.complex.taxonomic_id),
    }


def _stoichiometry(model) -> list[dict]:
    """The S matrix as a sorted list of records.

    Records rather than a keyed object, because reaction ids are not always valid MATLAB
    struct field names; sorted by (reaction, metabolite) as a tuple, which the MATLAB side
    reproduces by joining the two keys with char(1).
    """
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


def _gene_associations(model) -> list[dict]:
    """Which genes a reaction is associated with, as a set rather than as a rule string.

    The two toolboxes write the same logic differently --- RAVEN keeps `G1 and G2 or G3`,
    cobrapy parenthesises it as `(G1 and G2) or G3` --- so comparing rule strings would
    report a difference in spelling. After expansion the logic is carried by
    ec.rxn_enz_mat, which this scenario does compare; here the association matrix is
    enough and needs no parser on either side.
    """
    entries = [
        {"reaction": rxn.id, "gene": gene.id}
        for rxn in model.reactions
        for gene in rxn.genes
    ]
    return sorted(entries, key=lambda e: (e["reaction"], e["gene"]))


def _gem(model) -> dict:
    return {
        "n_reactions": len(model.reactions),
        "n_metabolites": len(model.metabolites),
        "n_genes": len(model.genes),
        "reactions": _reactions(model),
        "metabolites": [
            {"id": met.id, "name": str(met.name), "compartment": str(met.compartment)}
            for met in sorted(model.metabolites, key=lambda m: m.id)
        ],
        "genes": sorted(gene.id for gene in model.genes),
        "gene_associations": _gene_associations(model),
        "stoichiometry": _stoichiometry(model),
    }


def _ec_data(ec) -> dict:
    """The ec substructure --- the part of an ecModel that is GECKO's rather than cobra's."""
    rxn_enz_mat = ec.rxn_enz_mat
    if hasattr(rxn_enz_mat, "toarray"):
        rxn_enz_mat = rxn_enz_mat.toarray()

    coupling = [
        {
            "reaction": ec.rxns[i],
            "enzyme": ec.enzymes[j],
            "coefficient": float(rxn_enz_mat[i][j]),
        }
        for i in range(len(ec.rxns))
        for j in range(len(ec.enzymes))
        if rxn_enz_mat[i][j] != 0
    ]

    return {
        # Order is the result here, not an accident: ec.rxns follows the expansion, and
        # MATLAB's own tests assert that order. Not sorted, on either side.
        "rxns": [str(r) for r in ec.rxns],
        "genes": [str(g) for g in ec.genes],
        "enzymes": [str(e) for e in ec.enzymes],
        "mw": [float(m) for m in ec.mw],
        "sequence": [str(s) for s in ec.sequence],
        # makeEcModel leaves these unset; their *length* is what the two sides must agree
        # on at this stage, and a value appearing on one side only is a difference.
        "eccodes": [str(c) if c else "" for c in ec.eccodes],
        "n_kcat": len(ec.kcat),
        "n_source": len(ec.source),
        "n_notes": len(ec.notes),
        "n_concs": len(ec.concs),
        "kcat": [float(k) for k in ec.kcat],
        "coupling": sorted(coupling, key=lambda e: (e["reaction"], e["enzyme"])),
    }


def _ec_model(model) -> dict:
    result = _gem(model)
    result["gecko_light"] = bool(model.ec.gecko_light)
    result["ec"] = _ec_data(model.ec)
    return result


def run(ctx):
    inputs = ctx["inputs"]
    adapter = _adapter(inputs)
    model = load_conventional_gem(adapter)

    return {
        "adapter": _adapter_params(adapter),
        "conventional": _gem(model),
        # makeEcModel does not mutate its input, on either side, so both variants start
        # from the same conventional model.
        "full": _ec_model(make_ec_model(model, adapter, gecko_light=False)),
        "light": _ec_model(make_ec_model(model, adapter, gecko_light=True)),
    }
