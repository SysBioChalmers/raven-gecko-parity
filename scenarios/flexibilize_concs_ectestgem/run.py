"""Python side of the flexibilize-concentrations scenario.

Two independent checkpoints, matching the two ledger rows this scenario covers besides
``flexibilizeEnzConcs`` itself:

``flux_data``
    load_flux_data reading data/fluxData.tsv, then apply_flux_data_constraints on a fresh
    (kcat-free) ecModel, in both 'loose' and percentage-variance mode. Pure bound-setting,
    no LP solve involved.
``flexibilize``
    flexibilize_enz_concs on enzyme_usage_ectestgem's own R2/R4-blocked, single-bottleneck
    fixture (reused rather than re-derived --- see scenario.yml), which gives the
    "find the worst enzyme, relax it" loop exactly one unambiguous candidate (P5) to work
    with. Confirmed divergence in the post-loop refinement pass only; see scenario.yml.
"""

import importlib.util
import sys
from pathlib import Path

import cobra

from geckopy import (
    ModelAdapter,
    apply_flux_data_constraints,
    apply_kcat_constraints,
    constrain_enz_concs,
    fill_enz_concs,
    fill_eccodes_from_gem,
    flexibilize_enz_concs,
    load_conventional_gem,
    load_prot_data,
    make_ec_model,
    set_prot_pool_size,
)
from geckopy.databases.flux_data import load_flux_data


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


def _bounds(model, rxn_id: str) -> dict:
    rxn = model.reactions.get_by_id(rxn_id)
    return {"lb": float(rxn.lower_bound), "ub": float(rxn.upper_bound)}


def _checkpoint_flux_data(adapter, conv, inputs: dict) -> dict:
    flux_data = load_flux_data(inputs["flux_data_path"])
    parsed = {
        "conds": [str(c) for c in flux_data.conds],
        "p_tot": [float(v) for v in flux_data.p_tot],
        "gr_rate": [float(v) for v in flux_data.gr_rate],
        "exch_fluxes": [[float(v) for v in row] for row in flux_data.exch_fluxes],
        "exch_mets": [str(m) for m in flux_data.exch_mets],
        "exch_rxn_ids": [str(r) for r in flux_data.exch_rxn_ids],
    }

    def constrained(loose_strict_flux):
        model = make_ec_model(conv, adapter, gecko_light=False)
        fill_eccodes_from_gem(model)
        apply_flux_data_constraints(
            model, flux_data,
            condition=0, max_min_growth="max", loose_strict_flux=loose_strict_flux,
            bio_rxn=str(inputs["bio_rxn"]), c_source=str(inputs["c_source"]),
        )
        return {
            "S1": _bounds(model, "S1"),
            "S2": _bounds(model, "S2"),
            "R5": _bounds(model, "R5"),
        }

    return {
        "parsed": parsed,
        "loose": constrained("loose"),
        "pct": constrained(float(inputs["pct_variance"])),
    }


def _checkpoint_flexibilize(adapter, conv, inputs: dict) -> dict:
    for rxn_id in ("R2", "R4"):
        rxn = conv.reactions.get_by_id(rxn_id)
        rxn.lower_bound = 0.0
        rxn.upper_bound = 0.0

    model = make_ec_model(conv, adapter, gecko_light=False)
    model.solver = str(inputs["python_solver"])
    fill_eccodes_from_gem(model)
    model.adapter = adapter

    index = {r: i for i, r in enumerate(model.ec.rxns)}
    for rxn_id, kcat in inputs["flex_kcats"].items():
        i = index[str(rxn_id)]
        model.ec.kcat[i] = float(kcat)
        model.ec.source[i] = "manual"

    prot_data = load_prot_data(Path(adapter.params.path) / "data" / "proteomics.tsv", [1])
    fill_enz_concs(model, prot_data)
    constrain_enz_concs(model)
    apply_kcat_constraints(model)
    set_prot_pool_size(model)

    base_sol = model.optimize()
    base_growth = float(base_sol.objective_value)

    result = flexibilize_enz_concs(
        model,
        exp_growth=float(inputs["exp_growth"]),
        fold_change=float(inputs["fold_change"]),
        iter_per_enzyme=int(inputs["iter_per_enzyme"]),
        bio_rxn=str(inputs["bio_rxn"]),
        verbose=False,
    )

    final_sol = model.optimize()

    return {
        "base_growth": base_growth,
        "flexed": [
            {
                "protein": str(result.uniprot_ids[i]),
                "old_conc": float(result.old_concs[i]),
                "flex_conc": float(result.flex_concs[i]),
                "ratio_incr": float(result.ratio_incr[i]),
                "frequence": int(result.frequence[i]),
            }
            for i in range(len(result.uniprot_ids))
        ],
        "final_growth": float(final_sol.objective_value),
    }


def run(ctx):
    inputs = ctx["inputs"]
    cobra.Configuration().solver = str(inputs["python_solver"])

    adapter = _adapter(inputs)
    conv = load_conventional_gem(adapter)

    flux_data_result = _checkpoint_flux_data(adapter, conv, inputs)
    flexibilize_result = _checkpoint_flexibilize(adapter, conv, inputs)

    return {
        "flux_data": flux_data_result,
        "flexibilize": flexibilize_result,
    }
