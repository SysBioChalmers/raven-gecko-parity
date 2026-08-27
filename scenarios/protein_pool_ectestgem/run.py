"""Python side of the protein-pool scenario.

Five checkpoints, matching the five ledger rows this scenario covers:

``pool_size``
    setProtPoolSize / set_prot_pool_size, on both ecModel flavours, at the adapter's own
    defaults and at an explicit override.
``prot_data``
    loadProtData / load_prot_data reading data/proteomics.tsv.
``f_factor``
    calculateFfactor / calculate_f_factor, at the model's own enzyme list and at a declared
    subset.
``enzyme_concs``
    fillEnzConcs + constrainEnzConcs, fully measured and partially measured, plus
    removeConstraints/remove_constraints.
``light_constrain_raises``
    constrainEnzConcs has no usage reactions to constrain on a gecko-light model; both sides
    refuse. A boolean flag, not an exception message --- comparing free text across two
    languages is the kind of false difference docs/scenarios.md warns about.
"""

from pathlib import Path

from geckopy import (
    ModelAdapter,
    calculate_f_factor,
    constrain_enz_concs,
    fill_enz_concs,
    load_conventional_gem,
    load_prot_data,
    make_ec_model,
    set_prot_pool_size,
)
from geckopy.databases.pax_db_loader import ProtData


def _adapter(inputs: dict) -> ModelAdapter:
    """geckopy's ecTestGEM adapter, repointed at the GECKO copy of the fixture.

    Same reasoning as the other two scenarios in this chain: the parameters are geckopy's
    own (model_adapter.toml), the data files become the ones MATLAB reads.
    """
    adapter = ModelAdapter.from_folder(inputs["adapter_python"])
    fixture = Path(inputs["fixture_dir"])
    adapter.params.path = fixture
    adapter.params.conv_gem = fixture / "models" / "testModel.xml"
    return adapter


def _concs(model) -> list[dict]:
    """model.ec.concs paired with the enzyme it belongs to, sorted by enzyme.

    Sorted rather than left in ec.enzymes order: unlike ec_model_expansion_ectestgem's
    ec.rxns/genes/enzymes lists, where the expansion order *is* the result, here the point is
    whether the right value landed on the right enzyme --- a question sorting does not
    obscure, and the pairing is what makes it safe to sort at all. A NaN entry (no
    measurement) is emitted as a flag and a zero, the same has_charge/charge convention
    docs/scenarios.md uses for an absent metabolite charge: MATLAB's jsonencode writes NaN as
    null, which is not the same absence the Python side would write.
    """
    concs = model.ec.concs
    records = []
    for enzyme, conc in zip(model.ec.enzymes, concs):
        value = float(conc)
        has_conc = value == value  # NaN != NaN
        records.append({"enzyme": str(enzyme), "has_conc": has_conc, "conc": value if has_conc else 0.0})
    return sorted(records, key=lambda r: r["enzyme"])


def _usage_bounds(model) -> list[dict]:
    """usage_prot_<enzyme> upper bounds, sorted by enzyme."""
    records = [
        {"enzyme": str(enzyme), "upper_bound": float(model.reactions.get_by_id(f"usage_prot_{enzyme}").upper_bound)}
        for enzyme in model.ec.enzymes
    ]
    return sorted(records, key=lambda r: r["enzyme"])


def run(ctx):
    inputs = ctx["inputs"]
    adapter = _adapter(inputs)
    model = load_conventional_gem(adapter)

    def fresh(light):
        return make_ec_model(model, adapter, gecko_light=light)

    # --- pool_size: both flavours, default adapter parameters and an explicit override.
    # A fresh ecModel per call would prove nothing new --- the bound does not depend on
    # what else has been done to the model --- so one ecModel per flavour serves both calls.
    override = inputs["pool_size_override"]
    pool_size = {}
    for flavour, light in (("full", False), ("light", True)):
        ec = fresh(light)
        default_bound = float(set_prot_pool_size(ec))
        override_bound = float(
            set_prot_pool_size(ec, p_tot=float(override["p_tot"]), f=float(override["f"]), sigma=float(override["sigma"]))
        )
        pool_size[flavour] = {"default": default_bound, "override": override_bound}

    # --- prot_data: read once, both other checkpoints reuse it.
    prot_data = load_prot_data(Path(adapter.params.path) / "data" / "proteomics.tsv", [1])
    prot_data_result = {
        "uniprot_ids": [str(u) for u in prot_data.uniprot_ids],
        "abundances": [float(a) for a in prot_data.abundances.ravel()],
    }

    # --- f_factor: the model's own enzyme list, and a declared subset.
    ec_for_f = fresh(False)
    f_factor = {
        "default": float(calculate_f_factor(ec_for_f, prot_data)),
        "subset": float(calculate_f_factor(ec_for_f, prot_data, enzymes=list(inputs["f_factor_enzymes"]))),
    }

    # --- enzyme_concs: fully measured, then partially measured, then removeConstraints.
    # Every ecModel here is full: constrainEnzConcs is defined for full ecModels only, which
    # is its own checkpoint below rather than folded into this one.
    ec_full = fresh(False)
    fill_enz_concs(ec_full, prot_data)
    concs_full = _concs(ec_full)
    constrain_enz_concs(ec_full)
    constrained_full = _usage_bounds(ec_full)

    partial_ids = set(inputs["partial_proteins"])
    keep = [uid in partial_ids for uid in prot_data.uniprot_ids]
    partial_data = ProtData(
        uniprot_ids=[uid for uid, k in zip(prot_data.uniprot_ids, keep) if k],
        abundances=prot_data.abundances[keep, :],
    )
    ec_partial = fresh(False)
    fill_enz_concs(ec_partial, partial_data)
    concs_partial = _concs(ec_partial)
    constrain_enz_concs(ec_partial)
    constrained_partial = _usage_bounds(ec_partial)
    constrain_enz_concs(ec_partial, remove_constraints=True)
    removed_partial = _usage_bounds(ec_partial)
    # remove_constraints resets the LP bound but must leave ec.concs itself untouched --- the
    # measurement is not forgotten, only unenforced.
    concs_after_remove = _concs(ec_partial)

    enzyme_concs = {
        "full": {"concs": concs_full, "constrained": constrained_full},
        "partial": {
            "concs": concs_partial,
            "constrained": constrained_partial,
            "concs_survive_removal": concs_after_remove == concs_partial,
            "removed": removed_partial,
        },
    }

    # --- light_constrain_raises: no usage reactions on a gecko-light model.
    ec_light = fresh(True)
    fill_enz_concs(ec_light, prot_data)
    try:
        constrain_enz_concs(ec_light)
        light_constrain_raised = False
    except Exception:  # noqa: BLE001 --- which exception type is not the finding; whether one was raised is
        light_constrain_raised = True

    return {
        "pool_size": pool_size,
        "prot_data": prot_data_result,
        "f_factor": f_factor,
        "enzyme_concs": enzyme_concs,
        "light_constrain_raises": light_constrain_raised,
    }
