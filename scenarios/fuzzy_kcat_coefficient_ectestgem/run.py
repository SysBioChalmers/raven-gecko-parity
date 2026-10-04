"""Python side of the fuzzy-kcat coefficient scenario.

A BRENDA kcat is a turnover per molecule of the substrate it was measured on, so
fuzzy matching divides it by that substrate's stoichiometric coefficient. R7, added
to ecTestGEM as `2 m1 + 0.5 m2 => e1` with EC 1.1.2.1, has a BRENDA row on m1 only
(80 per second): 40 when divided by m1's coefficient, 160 when divided by the
smallest coefficient of the reaction.
"""

import importlib.util
import sys
from pathlib import Path

import cobra
import pandas as pd

from geckopy import (
    ModelAdapter,
    fill_eccodes_from_gem,
    fuzzy_kcat_matching,
    load_brenda_data,
    load_conventional_gem,
    load_phyl_dist,
    make_ec_model,
)


def _adapter(inputs: dict) -> ModelAdapter:
    """The ecTestGEM adapter subclass, as in kcat_chain_ectestgem."""
    base = ModelAdapter.from_folder(inputs["adapter_python"])
    fixture = Path(inputs["fixture_dir"])
    base.params.path = fixture
    base.params.conv_gem = fixture / "models" / "testModel.xml"

    adapter_module_path = Path(inputs["adapter_python"]) / "adapter.py"
    spec = importlib.util.spec_from_file_location("ectestgem_adapter", adapter_module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.TestGEMAdapter(base.params)


def _add_unequal_coefficients(conv: cobra.Model) -> None:
    """R7: two m1 and half an m2 give one e1, with EC 1.1.2.1 and no other substrate row."""
    m1 = conv.metabolites.get_by_id("m1c")
    m2 = conv.metabolites.get_by_id("m2c")
    e1 = conv.metabolites.get_by_id("e1e")

    r7 = cobra.Reaction("R7", name="R7")
    r7.lower_bound = 0.0
    r7.upper_bound = 1000.0
    r7.add_metabolites({m1: -2.0, m2: -0.5, e1: 1.0})
    r7.gene_reaction_rule = "G1"
    r7.annotation["ec-code"] = "1.1.2.1"
    conv.add_reactions([r7])


def run(ctx):
    inputs = ctx["inputs"]
    adapter = _adapter(inputs)
    conv = load_conventional_gem(adapter)
    _add_unequal_coefficients(conv)
    model = make_ec_model(conv, adapter, gecko_light=False)
    fill_eccodes_from_gem(model)

    brenda = load_brenda_data(inputs["brenda_dir"])
    phyl_dist = load_phyl_dist(inputs["phyl_dist_path"])
    fuzzy_df = fuzzy_kcat_matching(model, brenda, phyl_dist)

    matches = [
        {
            "reaction": str(row.rxn_id),
            "kcat": float(row.kcat),
            "eccode": str(row.eccode) if row.eccode else "",
            "origin": -1 if pd.isna(row.origin) else int(row.origin),
            "wildcard_level": -1 if pd.isna(row.wildcard_level) else int(row.wildcard_level),
        }
        for row in fuzzy_df.itertuples()
    ]
    matches.sort(key=lambda r: r["reaction"])
    return {"matches": matches}
