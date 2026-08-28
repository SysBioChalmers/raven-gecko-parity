"""Python side of the ecFVA scenario.

One ecModel, one call to ec_fva, mapped back to the conventional model's reactions. R2 is
ecTestGEM's only isozyme-split reaction (G1 and G2, forming a complex, or G3 alone); distinct
kcats for its two isozymes give the solver a real trade-off, which is what exposes this
scenario's one confirmed divergence --- see scenario.yml for the mechanism and geckopy's own
MATLAB-COMPAT note in ec_fva.py for the algorithmic difference it comes from.
"""

import importlib.util
import sys
from pathlib import Path

import cobra

from geckopy import (
    ModelAdapter,
    apply_kcat_constraints,
    ec_fva,
    fill_eccodes_from_gem,
    load_conventional_gem,
    make_ec_model,
    set_prot_pool_size,
)


def _adapter(inputs: dict) -> ModelAdapter:
    """geckopy's ecTestGEM adapter, repointed at the GECKO copy of the fixture.

    Same reasoning as protein_pool_ectestgem, kcat_chain_ectestgem and
    enzyme_usage_ectestgem: the parameters are geckopy's own (model_adapter.toml), the
    data files become the ones MATLAB reads.
    """
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


def run(ctx):
    inputs = ctx["inputs"]
    # Set before the model is read: a cobra model takes its solver from the
    # configuration at construction time.
    cobra.Configuration().solver = str(inputs["python_solver"])

    adapter = _adapter(inputs)
    conv = load_conventional_gem(adapter)

    model = make_ec_model(conv, adapter, gecko_light=False)
    model.solver = str(inputs["python_solver"])
    fill_eccodes_from_gem(model)

    index = {r: i for i, r in enumerate(model.ec.rxns)}
    for rxn_id, kcat in inputs["kcats"].items():
        i = index[str(rxn_id)]
        model.ec.kcat[i] = float(kcat)
        model.ec.source[i] = "manual"

    apply_kcat_constraints(model)
    set_prot_pool_size(model)

    df = ec_fva(model, conv, progress=False, n_proc=int(inputs["python_n_proc"]))

    rows = sorted(
        (
            {
                "reaction": str(rxn_id),
                "min_flux": float(row.min_flux),
                "max_flux": float(row.max_flux),
            }
            for rxn_id, row in df.iterrows()
        ),
        key=lambda r: r["reaction"],
    )

    return {"fva": rows}
