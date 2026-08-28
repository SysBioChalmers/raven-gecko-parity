"""Python side of the ecFSEOF scenario.

Red on purpose --- see scenario.yml for the three confirmed, execution-measured
divergences this checkpoint exists to demonstrate: the enforced-flux levels
themselves, the candidate search space, and the target-selection criterion.
"""

import importlib.util
import sys
from pathlib import Path

import cobra

from geckopy import (
    ModelAdapter,
    apply_kcat_constraints,
    ec_fseof,
    fill_eccodes_from_gem,
    load_conventional_gem,
    make_ec_model,
    set_prot_pool_size,
)


def _adapter(inputs: dict) -> ModelAdapter:
    """geckopy's ecTestGEM adapter, repointed at the GECKO copy of the fixture.

    Same reasoning as every other scenario in this pair: the parameters are geckopy's
    own (model_adapter.toml), the data files become the ones MATLAB reads.
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
    cobra.Configuration().solver = str(inputs["python_solver"])

    adapter = _adapter(inputs)
    conv = load_conventional_gem(adapter)

    model = make_ec_model(conv, adapter, gecko_light=False)
    model.solver = str(inputs["python_solver"])
    fill_eccodes_from_gem(model)
    model.adapter = adapter

    index = {r: i for i, r in enumerate(model.ec.rxns)}
    for rxn_id, kcat in inputs["kcats"].items():
        i = index[str(rxn_id)]
        model.ec.kcat[i] = float(kcat)
        model.ec.source[i] = "manual"

    apply_kcat_constraints(model)
    set_prot_pool_size(model)

    result = ec_fseof(
        model,
        str(inputs["prod_target_rxn"]),
        str(inputs["cs_rxn"]),
        n_steps=int(inputs["n_steps"]),
        bio_rxn=str(inputs["bio_rxn"]),
    )

    # target_type is not compared: MATLAB's rxnTargets/transportTargets output does not
    # carry the OE/KD/KO label at all (only geneTargets does, in a different id space),
    # so there is nothing on the MATLAB side to compare it against. The target *set*
    # already demonstrates the divergence this scenario exists to show.
    targets = sorted(str(row.reaction) for row in result.targets.itertuples())

    return {
        "enforced_levels": [float(v) for v in result.enforced],
        "targets": targets,
    }
