"""Python side of the enzyme-usage scenario.

A single solved ecModel, walked through the three post-solve reporting functions in
sequence: enzymeUsage's per-protein usage/capacity readout, reportEnzymeUsage's two
summary tables, and getConcControlCoeffs's growth-sensitivity coefficients.

R2 and R4 are both blocked before the ecModel is built, leaving R3 --- ecTestGEM's only
single-gene, single-isozyme reaction --- as the sole route from m1 to m2. With either one
open the LP has more than one equally optimal way to route flux between the parallel
routes, and MATLAB and geckopy each land on a different vertex of that tie (same growth
rate, different per-protein usage): confirmed by direct execution, not a bug on either
side, and not solved by choosing different kcats, since the shared protein-pool budget
that would otherwise arbitrate between them has slack once real proteomics data narrows
each protein's own cap (see scenario.yml's blocked_reactions comment). Removing the
parallel route removes the degeneracy structurally instead.

Real ecTestGEM proteomics data narrows every protein's usage cap; P5's is the tightest,
and becomes the sole binding constraint on growth once R2/R4 are blocked --- which is
what gives getConcControlCoeffs something to report (see scenario.yml for the
MATLAB-COMPAT note this does, and does not, exercise).
"""

import importlib.util
import sys
from pathlib import Path

import cobra

from geckopy import (
    ModelAdapter,
    apply_kcat_constraints,
    constrain_enz_concs,
    enzyme_usage,
    fill_enz_concs,
    fill_eccodes_from_gem,
    get_conc_control_coeffs,
    load_conventional_gem,
    load_prot_data,
    make_ec_model,
    report_enzyme_usage,
    set_prot_pool_size,
)


def _adapter(inputs: dict) -> ModelAdapter:
    """geckopy's ecTestGEM adapter, repointed at the GECKO copy of the fixture.

    Same reasoning as protein_pool_ectestgem and kcat_chain_ectestgem: the parameters
    are geckopy's own (model_adapter.toml), the data files become the ones MATLAB reads.
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


def _usage_rows(usage) -> list[dict]:
    return sorted(
        (
            {
                "protein": str(p),
                "ub": float(ub),
                "abs_usage": float(a),
                "cap_usage": float(c),
            }
            for p, ub, a, c in zip(usage.prot_id, usage.ub, usage.abs_usage, usage.cap_usage)
        ),
        key=lambda r: r["protein"],
    )


def _report_table_rows(df, value_col: str) -> list[dict]:
    return sorted(
        (
            {"protein": str(row.prot_id), "abs_usage": float(row.abs_usage), value_col: float(getattr(row, value_col))}
            for row in df.itertuples()
        ),
        key=lambda r: r["protein"],
    )


def _control_coeff_rows(proteins, enz, coeffs) -> list[dict]:
    return sorted(
        (
            {"protein": str(p), "analysed": bool(e), "coeff": float(c)}
            for p, e, c in zip(proteins, enz, coeffs)
        ),
        key=lambda r: r["protein"],
    )


def run(ctx):
    inputs = ctx["inputs"]
    # Set before the model is read: a cobra model takes its solver from the
    # configuration at construction time.
    cobra.Configuration().solver = str(inputs["python_solver"])

    adapter = _adapter(inputs)
    conv = load_conventional_gem(adapter)
    for rxn_id in inputs["blocked_reactions"]:
        rxn = conv.reactions.get_by_id(str(rxn_id))
        rxn.lower_bound = 0.0
        rxn.upper_bound = 0.0

    model = make_ec_model(conv, adapter, gecko_light=False)
    model.solver = str(inputs["python_solver"])
    fill_eccodes_from_gem(model)

    index = {r: i for i, r in enumerate(model.ec.rxns)}
    for rxn_id, kcat in inputs["kcats"].items():
        i = index[str(rxn_id)]
        model.ec.kcat[i] = float(kcat)
        model.ec.source[i] = "manual"

    prot_data = load_prot_data(Path(adapter.params.path) / "data" / "proteomics.tsv", [1])
    fill_enz_concs(model, prot_data)
    constrain_enz_concs(model)

    apply_kcat_constraints(model)
    set_prot_pool_size(model)

    sol = model.optimize()

    usage = enzyme_usage(model, sol.fluxes)
    usage_result = {
        "objective": float(sol.objective_value),
        "proteins": _usage_rows(usage),
    }

    report = report_enzyme_usage(
        model, usage,
        high_cap_usage=float(inputs["high_cap_usage"]),
        top_abs_usage=int(inputs["top_abs_usage"]),
    )
    report_result = {
        "high_cap_usage": _report_table_rows(report.high_cap_usage, "cap_usage"),
        # Confirmed divergence, asserted rather than avoided: report_enzyme_usage skips
        # any enzyme with no flux-carrying reaction outright, so this table can return
        # fewer than top_abs_usage rows. reportEnzymeUsage.m instead always returns
        # exactly top_abs_usage rows, padding with a placeholder for anything inactive.
        # See scenario.yml and raven-gecko-parity#18 for the mechanism on each side.
        "top_abs_usage": _report_table_rows(report.top_abs_usage, "perc_usage"),
        "total_usage_flux": float(report.total_usage_flux),
    }

    enz, coeffs = get_conc_control_coeffs(model)
    control_coeffs_result = _control_coeff_rows(model.ec.enzymes, enz, coeffs)

    return {
        "usage": usage_result,
        "report": report_result,
        "control_coeffs": control_coeffs_result,
    }
