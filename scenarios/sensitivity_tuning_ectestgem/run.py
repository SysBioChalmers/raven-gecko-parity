"""Python side of the sensitivity-tuning scenario.

Three independent checkpoints, matching the three ledger rows this scenario covers:

``sensitivity_tuning``
    sensitivity_tuning on enzyme_usage_ectestgem's own R2/R4-blocked, single-route
    fixture, with kcat_R3 deliberately too low for the target growth rate.
``sigma_fitter``
    fit_sigma (method='grid', matching MATLAB's own 100-point sweep exactly) on a
    separate instance of the same fixture shape. Confirmed divergence in the returned
    model's pool bound only --- see scenario.yml; filed and fixed as GECKO#433.
``truncate_values``
    Plain rounding, one value per order-of-magnitude regime.
"""

import importlib.util
import sys
from pathlib import Path

import cobra
import numpy as np

from geckopy import (
    ModelAdapter,
    apply_kcat_constraints,
    fill_eccodes_from_gem,
    fit_sigma,
    load_conventional_gem,
    make_ec_model,
    sensitivity_tuning,
    set_prot_pool_size,
    truncate_values,
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


def _blocked_single_route_model(adapter, conv, kcats: dict):
    """R2/R4 blocked, R3 the sole route, given kcats applied. Fresh conv copy each call."""
    conv = conv.copy()
    for rxn_id in ("R2", "R4"):
        rxn = conv.reactions.get_by_id(rxn_id)
        rxn.lower_bound = 0.0
        rxn.upper_bound = 0.0

    model = make_ec_model(conv, adapter, gecko_light=False)
    fill_eccodes_from_gem(model)
    model.adapter = adapter

    index = {r: i for i, r in enumerate(model.ec.rxns)}
    for rxn_id, kcat in kcats.items():
        i = index[str(rxn_id)]
        model.ec.kcat[i] = float(kcat)
        model.ec.source[i] = "manual"

    return model


def _checkpoint_sensitivity_tuning(adapter, conv, inputs: dict) -> dict:
    model = _blocked_single_route_model(adapter, conv, inputs["sens_kcats"])
    model.solver = str(inputs["python_solver"])
    apply_kcat_constraints(model)
    set_prot_pool_size(model)

    base_sol = model.optimize()
    base_growth = float(base_sol.objective_value)

    result = sensitivity_tuning(
        model,
        desired_growth_rate=float(inputs["sens_desired_growth"]),
        bio_rxn=str(inputs["bio_rxn"]),
        verbose=False,
    )

    final_sol = model.optimize()

    return {
        "base_growth": base_growth,
        "tuned": [
            {
                "reaction": str(result.rxns[i]),
                "enzymes": str(result.enzymes[i]),
                "old_kcat": float(result.old_kcat[i]),
                "new_kcat": float(result.new_kcat[i]),
                "source": str(result.source[i]),
            }
            for i in range(len(result.rxns))
        ],
        "final_growth": float(final_sol.objective_value),
    }


def _checkpoint_sigma_fitter(adapter, conv, inputs: dict) -> dict:
    model = _blocked_single_route_model(adapter, conv, inputs["sigma_kcats"])
    model.solver = str(inputs["python_solver"])
    model.objective = str(inputs["bio_rxn"])
    apply_kcat_constraints(model)
    set_prot_pool_size(model)

    # method='grid' matches MATLAB's own algorithm exactly (both sweep the full
    # [1/100, ..., 1.0] grid); geckopy's growth_grid/error_grid diagnostics have no
    # counterpart in sigmaFitter.m's own two-output signature, so this checkpoint
    # compares only what both functions actually return: the fitted sigma, and the
    # protein-pool bound the returned model ends up with.
    result = fit_sigma(
        model,
        growth_rate=float(inputs["sigma_growth_rate"]),
        p_tot=float(inputs["sigma_p_tot"]),
        f=float(inputs["sigma_f"]),
        method="grid",
    )

    pool_rxn = model.reactions.get_by_id("prot_pool_exchange")

    return {
        "sigma": float(result.sigma),
        "model_pool_ub": float(pool_rxn.upper_bound),
    }


def _checkpoint_truncate_values(inputs: dict) -> list:
    arr = np.array(inputs["truncate_values"], dtype=float)
    out = truncate_values(arr)
    return [float(v) for v in out]


def run(ctx):
    inputs = ctx["inputs"]
    cobra.Configuration().solver = str(inputs["python_solver"])

    adapter = _adapter(inputs)
    conv = load_conventional_gem(adapter)

    return {
        "sensitivity_tuning": _checkpoint_sensitivity_tuning(adapter, conv, inputs),
        "sigma_fitter": _checkpoint_sigma_fitter(adapter, conv, inputs),
        "truncate_values": _checkpoint_truncate_values(inputs),
    }
