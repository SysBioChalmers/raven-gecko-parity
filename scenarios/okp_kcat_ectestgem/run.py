"""Python side of the OpenKineticsPredictor (OKP) scenario.

Three checkpoints on one ecModel built from ecTestGEM: findMetSmiles feeding the two
writeOpenKineticsPredictorInput checkpoints (with and without its onlyWithSmiles filter),
then readOpenKineticsPredictorOutput parsing a result file back into a kcat list. See
scenario.yml for why this stops at the CSV boundary rather than the real OKP REST API,
and for the one real MATLAB bug this scenario's write checkpoint found and confirmed
fixed ([GECKO #437]).

One checkpoint asserts a confirmed, real divergence on purpose rather than working around
it: MATLAB's kcatSource carries an 'OKP-' prefix geckopy's source column does not. See the
comment at read_output below.
"""

import importlib.util
import sys
from pathlib import Path

from geckopy import DLKcatIgnoreLists, ModelAdapter, load_conventional_gem, make_ec_model
from geckopy.databases.pubchem import find_met_smiles
from geckopy.gather_kcats.open_kinetics_predictor import build_okp_input_csv, parse_okp_output


def _adapter(inputs: dict) -> ModelAdapter:
    """geckopy's ecTestGEM adapter --- see kcat_chain_ectestgem/run.py for why the
    actual TestGEMAdapter subclass is needed rather than the generic ModelAdapter.
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


def _ignore_lists() -> DLKcatIgnoreLists:
    # ecTestGEM's own metabolites (m1, m2, e1, e2) are not currency/ignored metabolites
    # on either side; an empty ignore list keeps this scenario's fixture untouched by it,
    # matching kcat_chain_ectestgem's own DLKcat checkpoint.
    return DLKcatIgnoreLists(ignore_names=[], ignore_smiles=[], currency_pairs=[])


def _smiles_snapshot(model) -> dict:
    return {m.id: str(m.annotation.get("smiles", "")) for m in sorted(model.metabolites, key=lambda m: m.id)}


def _csv_pairs(csv_text: str) -> list[str]:
    lines = [line for line in csv_text.strip("\n").split("\n")[1:] if line]
    return sorted(lines)


def _checkpoint_smiles(model, inputs: dict) -> dict:
    find_met_smiles(model, cache_path=Path(inputs["scenario_root"]) / "data" / "smilesDB.tsv")
    return _smiles_snapshot(model)


def _checkpoint_write(model, ignore_lists) -> dict:
    # ec.rxns order on this fixture is [R2_EXP_1, R2_EXP_2, R2_REV_EXP_1, R2_REV_EXP_2,
    # R3, R5] (confirmed by direct execution, identical on both sides). Requesting
    # {R2_EXP_1, R2_EXP_2, R3} skips the two REV entries sitting in between --- exactly
    # the subset shape that GECKO #437's bug mishandled, so this checkpoint doubles as
    # its regression check.
    with_smiles = build_okp_input_csv(
        model, ignore_lists, ec_rxns=["R2_EXP_1", "R2_EXP_2", "R3"], only_with_smiles=True,
    )

    # m2 (R5's substrate) deliberately loses its SMILES here, so the two calls below
    # exercise onlyWithSmiles' two branches on something real: with the filter off, R5's
    # entry survives with a 'None' placeholder; with it on (the default), the same entry
    # is dropped instead of appearing at all.
    model.metabolites.get_by_id("m2c").annotation["smiles"] = ""
    full_rxns = ["R2_EXP_1", "R2_EXP_2", "R3", "R5"]
    without_filter = build_okp_input_csv(model, ignore_lists, ec_rxns=full_rxns, only_with_smiles=False)
    with_filter = build_okp_input_csv(model, ignore_lists, ec_rxns=full_rxns, only_with_smiles=True)

    return {
        "with_smiles": _csv_pairs(with_smiles),
        "after_clearing_m2_without_filter": _csv_pairs(without_filter),
        "after_clearing_m2_with_filter": _csv_pairs(with_filter),
    }


def _checkpoint_read(model, inputs: dict) -> dict:
    df = parse_okp_output(model, Path(inputs["okp_result_path"]))
    rows = sorted(
        (
            {
                "reaction": str(r.rxn_id),
                "gene": str(r.genes[0]) if r.genes else "",
                "substrate": str(r.substrates[0]) if r.substrates else "",
                "kcat": float(r.kcat),
                # geckopy's source column keeps parse_okp_output's stripped-but-not-
                # reprefixed value ('CataPro', 'BRENDA'); MATLAB's kcatSource carries an
                # 'OKP-' prefix on the same value (see scenario.yml). Both are recorded,
                # not normalized to a shared token, so the split stays visible in the
                # comparison rather than being hidden by the checkpoint itself.
                "source": str(r.source),
            }
            for r in df.itertuples()
        ),
        key=lambda r: (r["reaction"], r["gene"]),
    )
    return {"rows": rows}


def run(ctx):
    inputs = ctx["inputs"]
    adapter = _adapter(inputs)
    conv = load_conventional_gem(adapter)
    model = make_ec_model(conv, adapter, gecko_light=False)
    ignore_lists = _ignore_lists()

    smiles_result = _checkpoint_smiles(model, inputs)
    write_result = _checkpoint_write(model, ignore_lists)
    read_result = _checkpoint_read(model, inputs)

    return {
        "smiles": smiles_result,
        "write": write_result,
        "read_output": read_result,
    }
