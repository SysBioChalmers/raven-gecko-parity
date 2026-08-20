"""One-time triage of the GECKO <-> geckopy ledger.

The decisions below come from geckopy's `docs/migrating_from_gecko_matlab.md` §5 (a
function-by-function correspondence table), checked against what the two checkouts actually
contain rather than taken on trust. Three things the check turned up are recorded in the
rows themselves:

* geckopy exports both a canonical name and a deprecated alias for eight functions
  (`assign_standard_kcat` / `get_standard_kcat`, ...). Name-based seeding paired the MATLAB
  function to the *alias*; the canonical name is the real counterpart.
* MATLAB's OpenKineticsPredictor REST client (`submitOpenKineticsPredictor`,
  `fetchOpenKineticsPredictor`) and `mergeKcats` exist only on the unmerged
  `feat/geckopy-compat` branch. On `develop4` the file-based round-trip is still what ships.
* `bayesianSensitivityTuning` is marked "not ported" in the migration doc, but
  `geckopy/docs/internal/bayesian_tuning_plan.md` says the port is planned and paused --- so
  it is queued work, not a settled divergence.

Run once:  python scripts/triage_gecko.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parity.config import load_config  # noqa: E402
from parity.inventory import build_inventory  # noqa: E402
from parity.ledger import Entry, load_ledger, save_ledger  # noqa: E402

DOC = "geckopy docs/migrating_from_gecko_matlab.md §5"

# --------------------------------------------------------------------------------------
# Seeding paired these MATLAB functions to geckopy's deprecated aliases. Repoint them at
# the canonical name; the alias gets its own row below.
# --------------------------------------------------------------------------------------
REPAIR: dict[str, tuple[str, str]] = {
    "constrainFluxData": ("geckopy.apply_flux_data_constraints", "geckopy.constrain_flux_data"),
    "getECfromDatabase": ("geckopy.fill_eccodes_from_database", "geckopy.get_ec_from_database"),
    "getECfromGEM": ("geckopy.fill_eccodes_from_gem", "geckopy.get_ec_from_gem"),
    "getKcatAcrossIsozymes": ("geckopy.fill_kcats_from_isozymes", "geckopy.get_kcat_across_isozymes"),
    "getStandardKcat": ("geckopy.assign_standard_kcat", "geckopy.get_standard_kcat"),
    "mergeDLKcatAndFuzzyKcats": ("geckopy.merge_kcats", "geckopy.merge_dlkcat_and_fuzzy_kcats"),
    "selectKcatValue": ("geckopy.apply_kcat_list", "geckopy.select_kcat_value"),
    "sigmaFitter": ("geckopy.fit_sigma", "geckopy.sigma_fitter"),
}

# --------------------------------------------------------------------------------------
# Deliberately one-sided.
# --------------------------------------------------------------------------------------
MATLAB_ONLY: dict[str, str] = {
    "plotEcFVA": (
        "Not ported: plot directly from the ec_fva DataFrame with matplotlib or seaborn. "
        f"{DOC}."
    ),
    "updateProtPool": (
        "Obsolete since GECKO 3.2.0 --- set_prot_pool_size supersedes it. A candidate for "
        f"removal from MATLAB GECKO too. {DOC}."
    ),
    "ModelAdapterManager": (
        "Deliberate design divergence: geckopy has no global default adapter. Pass adapter= "
        "explicitly or set model.adapter, so there is no manager to port."
    ),
    "writeOpenKineticsPredictorInput": (
        "geckopy replaced the OpenKineticsPredictor file round-trip with a REST client "
        "(submit_open_kinetics_predictor / fetch_open_kinetics_predictor); the input CSV is "
        "built internally by build_okp_input_csv."
    ),
    "readOpenKineticsPredictorOutput": (
        "Counterpart of writeOpenKineticsPredictorInput --- superseded on the Python side by "
        "the REST client, whose parsing lives in parse_okp_output."
    ),
}

PYTHON_PENDING: dict[str, tuple[str | None, str]] = {
    "bayesianSensitivityTuning": (
        None,
        "ABC-SMC kcat tuning (~1370 LOC with its helpers). The migration doc calls it "
        "'not ported', but geckopy/docs/internal/bayesian_tuning_plan.md has the design and "
        "says the work is paused, not abandoned --- queued, not a divergence.",
    ),
}

MATLAB_PENDING: dict[str, tuple[str | None, str]] = {
    "geckopy.submit_open_kinetics_predictor": (
        None,
        "MATLAB submitOpenKineticsPredictor.m exists on the unmerged feat/geckopy-compat "
        "branch (84 commits ahead of develop4) but not on develop4 or develop. Merging that "
        "branch closes this row.",
    ),
    "geckopy.fetch_open_kinetics_predictor": (
        None,
        "MATLAB fetchOpenKineticsPredictor.m exists on the unmerged feat/geckopy-compat "
        "branch but not on develop4 or develop. Merging that branch closes this row.",
    ),
    "geckopy.relax_proteomics_greedy": (
        None,
        "New in geckopy: relaxes a fixed top-k of measured concentrations in a greedy loop "
        "until a target growth is reached --- an alternative to flexibilize_enz_concs. The "
        "migration doc marks it [Py]; queued here because it is a genuinely new algorithm, "
        "not a port artefact. Confirm before scheduling.",
    ),
    "geckopy.pfba_enzymes": (
        None,
        "New in geckopy: pFBA variant minimising total usage_prot_* flux instead of all "
        "fluxes. Marked [Py] in the migration doc; queued here as new functionality. "
        "Confirm before scheduling.",
    ),
    "geckopy.get_enzyme_bottlenecks": (
        None,
        "New in geckopy: per-enzyme dual-based bottleneck ranker. Marked [Py] in the "
        "migration doc; queued here as new functionality. Confirm before scheduling.",
    ),
}

# --------------------------------------------------------------------------------------
# Not part of the cross-implementation API.
# --------------------------------------------------------------------------------------
BAYESIAN_HELPER = (
    "Helper of bayesianSensitivityTuning, not a standalone entry point. It will be absorbed "
    "into the Python port rather than getting a counterpart of its own."
)

# The capability exists on the Python side, just not as its own exported function.
SUBSUMED: dict[str, str] = {
    "adapterTemplate": (
        "Adapter skeleton generation lives in the `geckopy init` CLI and "
        "templates/model_adapter.toml rather than in a library function."
    ),
    "startGECKOproject": (
        "Project skeleton generation lives in `geckopy init my_project` on the CLI rather "
        "than in a library function."
    ),
    "getECstring": (
        "EC-string formatting, inlined on the Python side inside fill_eccodes_from_database "
        f"and fill_eccodes_from_gem. {DOC}."
    ),
    "loadDatabases": (
        "geckopy loads databases implicitly at point of use rather than through one entry "
        "point. The download halves MATLAB performs inline (urlwrite for UniProt, a local "
        "downloadKEGG subfunction) are exposed separately in Python as "
        "geckopy.databases.download_kegg / download_uniprot."
    ),
}

INTERNAL: dict[str, str] = {
    # MATLAB glue.
    "GECKOInstaller": "Installer. Python installs with pip.",
    "findGECKOroot": "Path helper. pathlib.Path(__file__) covers it; nothing to port.",
    "updateGECKOdoc": (
        "Regenerates MATLAB Toolbox doc metadata. Python docs are docstring-driven, so there "
        "is nothing equivalent to regenerate."
    ),
    "parseGECKOargs": (
        "MATLAB varargin parsing glue. Python uses ordinary keyword arguments."
    ),
    # Bayesian helpers.
    "abc_max": BAYESIAN_HELPER,
    "addCarbonNum": BAYESIAN_HELPER,
    "getrSample": BAYESIAN_HELPER,
    "loadBayesianData": BAYESIAN_HELPER,
    "mse": BAYESIAN_HELPER,
    "updateprior": BAYESIAN_HELPER,
}

# geckopy's deprecated aliases, filled in from REPAIR below.
ALIAS_REASON = (
    "Deprecated alias of {canonical}, kept for backwards compatibility and emitting a "
    "DeprecationWarning. The canonical name carries the parity row."
)

# --------------------------------------------------------------------------------------
# Deliberately Python-only.
# --------------------------------------------------------------------------------------
RETURN_TYPE = (
    "Return type. MATLAB GECKO returns several parallel outputs ([model, a, b] = f(...)); "
    "geckopy returns one dataclass instead, so this has no MATLAB counterpart by design."
)
DATA_TYPE = (
    "Loaded-data type. MATLAB GECKO passes parallel cell arrays and structs; geckopy wraps "
    "them in a dataclass."
)
PIPELINE_STEP = (
    "Step of the make_ec_model build pipeline, exported so callers can reuse or reorder it. "
    "MATLAB keeps the equivalent logic inline in makeEcModel.m."
)
EXPLICIT_LOADER = (
    "Explicit data loader. MATLAB GECKO reads this file inline inside the function that "
    "consumes it rather than exposing a loader."
)

PYTHON_ONLY: dict[str, str] = {
    # Return types.
    "geckopy.AddNewRxnsResult": RETURN_TYPE,
    "geckopy.EnzymeUsageReport": RETURN_TYPE,
    "geckopy.EnzymeUsageResult": RETURN_TYPE,
    "geckopy.FlexEnzResult": RETURN_TYPE,
    "geckopy.GreedyRelaxResult": RETURN_TYPE,
    "geckopy.MapRxnsResult": RETURN_TYPE,
    "geckopy.NewEnzyme": RETURN_TYPE,
    "geckopy.RelaxationStep": RETURN_TYPE,
    "geckopy.SigmaFitterResult": RETURN_TYPE,
    "geckopy.TunedKcatsResult": RETURN_TYPE,
    # Loaded-data types.
    "geckopy.BrendaData": DATA_TYPE,
    "geckopy.ComplexPortalEntry": DATA_TYPE,
    "geckopy.DLKcatIgnoreLists": DATA_TYPE,
    "geckopy.FluxData": DATA_TYPE,
    "geckopy.PhylDist": DATA_TYPE,
    "geckopy.ProtData": DATA_TYPE,
    "geckopy.UniprotDB": DATA_TYPE,
    "geckopy.databases.KeggDB": DATA_TYPE,
    "geckopy.databases.brenda.Row": DATA_TYPE,
    # The model object itself.
    "geckopy.EcModel": (
        "The model object. MATLAB GECKO uses a RAVEN struct with an `ec` field; geckopy "
        "subclasses cobra.Model. A class, not a function --- no counterpart by design."
    ),
    "geckopy.EcData": (
        "The `ec` payload, equivalent to MATLAB's model.ec struct rather than to any "
        "function."
    ),
    "geckopy.Enzyme": (
        "Per-enzyme proxy object (model.enzymes.get_by_id('P00350')). MATLAB indexes into "
        "parallel cell arrays instead, so there is nothing to port."
    ),
    "geckopy.ModelParameters": (
        "Validated adapter parameters. MATLAB reads them off the ModelAdapter classdef "
        "properties; geckopy validates model_adapter.toml with pydantic."
    ),
    # Adapter plumbing.
    "geckopy.adapter.ComplexParams": "Adapter parameter group; MATLAB uses ModelAdapter classdef properties.",
    "geckopy.adapter.KeggParams": "Adapter parameter group; MATLAB uses ModelAdapter classdef properties.",
    "geckopy.adapter.UniprotParams": "Adapter parameter group; MATLAB uses ModelAdapter classdef properties.",
    "geckopy.adapter.resolve_adapter": (
        "Resolves the adapter argument, since geckopy has no global default. MATLAB reaches "
        "for ModelAdapterManager.getDefault() instead."
    ),
    "geckopy.adapter.resolve_param": (
        "Reads one adapter parameter with validation and a clear error. MATLAB indexes the "
        "classdef property directly."
    ),
    # Explicit loaders.
    "geckopy.load_complex_portal_json": EXPLICIT_LOADER,
    "geckopy.load_dlkcat_ignore_lists": EXPLICIT_LOADER,
    "geckopy.load_pax_db": EXPLICIT_LOADER,
    "geckopy.load_phyl_dist": EXPLICIT_LOADER,
    "geckopy.load_uniprot_tsv": EXPLICIT_LOADER,
    "geckopy.databases.load_kegg_tsv": EXPLICIT_LOADER,
    "geckopy.databases.download_kegg": (
        "MATLAB downloads KEGG from a local subfunction inside loadDatabases.m rather than "
        "exposing an entry point; geckopy makes it callable on its own."
    ),
    "geckopy.databases.download_uniprot": (
        "MATLAB downloads UniProt inline (urlwrite) inside loadDatabases.m rather than "
        "exposing an entry point; geckopy makes it callable on its own."
    ),
    # BRENDA refresh tooling.
    "geckopy.databases.brenda.parse_brenda_json": (
        "Part of the BRENDA JSON -> TSV refresh pipeline. MATLAB GECKO ships the pre-built "
        "TSV and has no equivalent generator."
    ),
    "geckopy.databases.brenda.aggregate_and_write": (
        "Part of the BRENDA JSON -> TSV refresh pipeline; no MATLAB equivalent generator."
    ),
    # OpenKineticsPredictor client internals.
    "geckopy.gather_kcats.OKPClient": (
        "HTTP client backing submit_open_kinetics_predictor / "
        "fetch_open_kinetics_predictor. MATLAB's develop4 code is file-based."
    ),
    "geckopy.gather_kcats.OKPError": "Exception type for the OKP client. MATLAB signals with error().",
    "geckopy.gather_kcats.open_kinetics_predictor.build_okp_input_csv": (
        "Builds the OKP request payload inside the client; MATLAB's equivalent is the "
        "user-facing writeOpenKineticsPredictorInput."
    ),
    "geckopy.gather_kcats.open_kinetics_predictor.parse_okp_output": (
        "Parses the OKP response inside the client; MATLAB's equivalent is the user-facing "
        "readOpenKineticsPredictorOutput."
    ),
    # Helpers exported alongside a paired function.
    "geckopy.gather_kcats.extract_enzyme_substrate_pairs": (
        "Helper exported alongside write_dlkcat_input; MATLAB keeps it inline in "
        "writeDLKcatInput.m."
    ),
    "geckopy.gather_kcats.format_kcat_source": (
        "Helper exported alongside apply_kcat_list; MATLAB keeps it inline in "
        "selectKcatValue.m."
    ),
    "geckopy.gather_kcats.normalize_source": (
        "Helper exported alongside merge_kcats; MATLAB keeps it inline in "
        "mergeDLKcatAndFuzzyKcats.m."
    ),
    # Build pipeline steps.
    "geckopy.ec_model.pipeline.add_protein_pool_exchange_reaction": PIPELINE_STEP,
    "geckopy.ec_model.pipeline.add_protein_pool_pseudometabolite": PIPELINE_STEP,
    "geckopy.ec_model.pipeline.add_protein_pseudometabolites": PIPELINE_STEP,
    "geckopy.ec_model.pipeline.add_protein_usage_reactions": PIPELINE_STEP,
    "geckopy.ec_model.pipeline.allocate_ec_and_coupling_light": PIPELINE_STEP,
    "geckopy.ec_model.pipeline.allocate_ec_for_catalyzed_reactions": PIPELINE_STEP,
    "geckopy.ec_model.pipeline.build_rxn_enzyme_coupling": PIPELINE_STEP,
    "geckopy.ec_model.pipeline.invert_backwards_only_reactions": PIPELINE_STEP,
    "geckopy.ec_model.pipeline.populate_enzyme_data": PIPELINE_STEP,
    "geckopy.ec_model.pipeline.remove_pseudoreaction_gprs": PIPELINE_STEP,
    "geckopy.ec_model.pipeline.split_light_rxn_id": PIPELINE_STEP,
}

# --------------------------------------------------------------------------------------
# Covered by a dependency on the other side.
# --------------------------------------------------------------------------------------
VIA_DEPENDENCY: dict[str, str] = {
    "geckopy.ec_model.pipeline.convert_to_irreversible": (
        "MATLAB GECKO calls RAVEN's convertToIrrev (makeEcModel.m:194). geckopy "
        "re-implements it in the build pipeline because the splitting is tied to GECKO's "
        "needs --- see geckopy docs/internal/raven_inventory.md §2."
    ),
    "geckopy.ec_model.pipeline.expand_model": (
        "MATLAB GECKO calls RAVEN's expandModel (makeEcModel.m:199). geckopy re-implements "
        "it over cobrapy's GPR syntax tree rather than RAVEN's string manipulation --- see "
        "geckopy docs/internal/raven_inventory.md §2."
    ),
}

# Notes worth carrying on rows that are otherwise settled.
NOTES: dict[str, str] = {
    "makeEcModel": (
        "[3->4] ec.genes/enzymes/mw/sequence sorted alphabetically for stable order; KEGG "
        "fallback for unmatched genes is opt-in via kegg_db=. [Py] single return; unmatched "
        "genes logged and annotated on rxn.notes['geckopy_warning']."
    ),
    "loadEcModel": (
        "[3->4] auto-flips legacy reverse-direction usage_prot_* / prot_pool_exchange to the "
        "forward convention on load. A scenario here would be well spent."
    ),
    "applyKcatConstraints": (
        "[3->4] writes coefficients with the forward-direction usage_prot_* / "
        "prot_pool_exchange convention."
    ),
    "enzymeUsage": "[3->4] usage flux read from positive usage_prot_* flux.",
    "reportEnzymeUsage": "[3->4] reads positive usage_prot_* flux.",
    "saveEcModel": "[3->4] emits the new cobrapy-style YAML; usage_prot_* in forward convention.",
    "ecFSEOF": "[Py] thin wrapper over raven_toolbox.analysis.fseof; selection is regression-based.",
    "getSubsetEcModel": "[Py] returns a new EcModel; the input is not mutated.",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-n", "--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_config()
    pair = config.pair("gecko")
    inventory = build_inventory(pair)
    ledger = load_ledger(pair.ledger)

    by_matlab, by_python = ledger.by_matlab(), ledger.by_python()
    applied = 0

    # 1. Repoint the eight alias pairings at the canonical export, and give the alias a row.
    for matlab, (canonical, alias) in REPAIR.items():
        entry = by_matlab.get(matlab)
        if entry is None:
            print(f"  ! no row for {matlab}")
            continue
        if canonical not in inventory.python_keys:
            print(f"  ! {canonical} is not exported by geckopy --- skipping {matlab}")
            continue

        # Seeding left the canonical export a one-sided stub of its own, because it could
        # not pair it by name. Now that it belongs to this row, that stub has to go.
        ledger.entries[:] = [
            e
            for e in ledger.entries
            if e is entry or not (e.python == canonical and e.matlab is None and e.status == "unreviewed")
        ]
        by_python.pop(canonical, None)

        entry.python = canonical
        entry.status = "parity"
        entry.notes = NOTES.get(matlab)

        alias_entry = by_python.get(alias)
        if alias_entry is None or alias_entry is entry:
            alias_entry = Entry(status="internal", python=alias)
            ledger.entries.append(alias_entry)
            by_python[alias] = alias_entry
        alias_entry.status = "internal"
        alias_entry.matlab = None
        alias_entry.python = alias
        alias_entry.reason = ALIAS_REASON.format(canonical=canonical.rsplit(".", 1)[-1])
        alias_entry.notes = None
        applied += 2

    # 2. Everything else the migration doc and the two checkouts settle.
    def decide(key: str, **fields) -> None:
        nonlocal applied
        entry = by_matlab.get(key) or by_python.get(key)
        if entry is None:
            print(f"  ! no row for {key}")
            return
        for name, value in fields.items():
            setattr(entry, name, value)
        applied += 1

    for name, reason in MATLAB_ONLY.items():
        decide(name, status="matlab-only", python=None, reason=reason, notes=None)
    for name, reason in INTERNAL.items():
        decide(name, status="internal", reason=reason, notes=None)
    for name, reason in SUBSUMED.items():
        decide(name, status="subsumed", python=None, reason=reason, notes=None)
    for name, reason in PYTHON_ONLY.items():
        decide(name, status="python-only", matlab=None, reason=reason, notes=None)
    for name, reason in VIA_DEPENDENCY.items():
        decide(name, status="via-dependency", matlab=None, reason=reason, notes=None)
    for name, (issue, note) in PYTHON_PENDING.items():
        decide(name, status="python-pending", python=None, issue=issue, notes=note, reason=None)
    for name, (issue, note) in MATLAB_PENDING.items():
        decide(name, status="matlab-pending", matlab=None, issue=issue, notes=note, reason=None)

    # 3. Everything still paired and untouched is a straight port: confirm it.
    for entry in ledger.entries:
        if entry.status == "unreviewed" and entry.matlab and entry.python:
            entry.status = "parity"
            entry.notes = NOTES.get(entry.matlab, f"Confirmed against {DOC}.")
            applied += 1

    print(f"triaged {applied} row(s)")
    remaining = [e.label for e in ledger.entries if e.status == "unreviewed"]
    if remaining:
        print(f"still unreviewed ({len(remaining)}): {', '.join(remaining)}")

    if args.dry_run:
        print("(dry run --- nothing written)")
        return 0

    save_ledger(ledger, pair.ledger)
    print(f"wrote {pair.ledger}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
