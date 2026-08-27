"""Python side of the enzyme-annotation scenario.

Three checkpoints, each run over both ecModel flavours and each over all ec reactions and
over a declared subset:

``complexes``
    ec.rxn_enz_mat after applyComplexData --- subunit stoichiometry, so a coefficient of 2
    where the model had 1.
``eccodes_from_gem``
    ec.eccodes filled from the GEM's own annotations.
``eccodes_from_database``
    ec.eccodes filled from the UniProt snapshot, falling through to KEGG.

One API difference is handled rather than measured: MATLAB's applyComplexData leaves the
kcat coefficients alone, while geckopy re-applies them unless told not to. The scenario
passes ``apply=False`` so the two do the same work --- with every kcat still zero at this
stage the difference would not show up in the numbers anyway, and silently letting one
side rebuild the LP would make a later divergence impossible to attribute.
"""

from pathlib import Path

from geckopy import (
    ModelAdapter,
    apply_complex_data,
    fill_eccodes_from_database,
    fill_eccodes_from_gem,
    load_conventional_gem,
    load_uniprot_tsv,
    make_ec_model,
)
from geckopy.databases.kegg_loader import load_kegg_tsv


def _adapter(inputs: dict) -> ModelAdapter:
    """geckopy's ecTestGEM adapter, repointed at the GECKO copy of the fixture.

    See ec_model_expansion_ectestgem/run.py --- same reasoning: the parameters stay
    geckopy's, the data files become the ones MATLAB reads.
    """
    adapter = ModelAdapter.from_folder(inputs["adapter_python"])
    fixture = Path(inputs["fixture_dir"])
    adapter.params.path = fixture
    adapter.params.conv_gem = fixture / "models" / "testModel.xml"
    return adapter


def _coupling(ec) -> list[dict]:
    """Non-zero entries of ec.rxn_enz_mat as sorted records."""
    matrix = ec.rxn_enz_mat
    if hasattr(matrix, "toarray"):
        matrix = matrix.toarray()
    entries = [
        {"reaction": ec.rxns[i], "enzyme": ec.enzymes[j], "coefficient": float(matrix[i][j])}
        for i in range(len(ec.rxns))
        for j in range(len(ec.enzymes))
        if matrix[i][j] != 0
    ]
    return sorted(entries, key=lambda e: (e["reaction"], e["enzyme"]))


def _eccodes(ec) -> list[str]:
    """ec.eccodes in ec.rxns order --- the order is the result, so it is not sorted."""
    return [str(code) if code else "" for code in ec.eccodes]


def run(ctx):
    inputs = ctx["inputs"]
    adapter = _adapter(inputs)
    model = load_conventional_gem(adapter)

    # Loaded once and reused: the same two snapshots MATLAB's loadDatabases reads out of
    # the adapter's data folder.
    uniprot = load_uniprot_tsv(adapter.params.path / "data" / "uniprot.tsv")
    kegg = load_kegg_tsv(adapter.params.path / "data" / "kegg.tsv")

    results = {}
    for flavour, light in (("full", False), ("light", True)):
        subset = list(inputs["subset_full" if flavour == "full" else "subset_light"])

        # A fresh ecModel per checkpoint. Each function mutates the model it is given, and
        # sharing one between them would make each checkpoint depend on the order the
        # previous ones ran in.
        def fresh():
            return make_ec_model(model, adapter, gecko_light=light)

        complexes = fresh()
        # apply=False: do what MATLAB does and no more --- see the module docstring.
        apply_complex_data(complexes, apply=False)

        from_gem, from_gem_subset = fresh(), fresh()
        fill_eccodes_from_gem(from_gem)
        fill_eccodes_from_gem(from_gem_subset, ec_rxns=subset)

        from_db, from_db_subset = fresh(), fresh()
        fill_eccodes_from_database(from_db, uniprot, kegg_db=kegg)
        fill_eccodes_from_database(from_db_subset, uniprot, kegg_db=kegg, ec_rxns=subset)

        results[flavour] = {
            "ec_rxns": [str(r) for r in complexes.ec.rxns],
            "complexes": _coupling(complexes.ec),
            "eccodes_from_gem": _eccodes(from_gem.ec),
            "eccodes_from_gem_subset": _eccodes(from_gem_subset.ec),
            "eccodes_from_database": _eccodes(from_db.ec),
            "eccodes_from_database_subset": _eccodes(from_db_subset.ec),
        }

    return results
