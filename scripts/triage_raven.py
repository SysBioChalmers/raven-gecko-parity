"""One-time triage of the RAVEN <-> raven-toolbox ledger.

Sources, in order of authority --- every row was checked against what the two checkouts
actually contain, not taken on trust:

* `raven-toolbox/docs/reference/migration.md` (already imported by import_migration_md.py;
  this fills in the many-to-many rows that importer deliberately skipped),
* `raven-toolbox/docs/reference/todo.md` --- the protocol feasibility table, which maps a
  real reconstruction workflow function-by-function onto cobrapy and raven-toolbox,
* `raven-toolbox/IMPROVEMENTS.md` --- the recorded rationale for what was ported
  differently or not at all,
* `raven-toolbox/docs/reference/flux_sampling_algorithms.md` section 8 --- the sampling
  implementation map,
* the RAVEN function headers and the raven-toolbox docstrings themselves.

The dominant finding is structural rather than per-function: raven-toolbox is built on
cobrapy, so a large share of RAVEN's public surface is `via-dependency` --- the capability is
there, it just belongs to cobra rather than to raven-toolbox. A second large share is
`subsumed`: RAVEN splits an algorithm across several files because MATLAB allows one public
function per file, while Python keeps it inside one entry point.

Run once:  python scripts/triage_raven.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parity.config import load_config  # noqa: E402
from parity.inventory import build_inventory  # noqa: E402
from parity.ledger import Entry, load_ledger, save_ledger  # noqa: E402

P = "raven_toolbox"

# --------------------------------------------------------------------------------------
# Pairings the name-based seeder could not make. Each was confirmed by comparing the RAVEN
# header line with the raven-toolbox docstring.
# --------------------------------------------------------------------------------------
PAIR: dict[str, tuple[str, str | None]] = {
    # Gap-filling: RAVEN's names lead with the algorithm, Python's with the action.
    "gapFillFastLP": (f"{P}.gapfilling.fill_gaps_fast_lp", "Both are 'LP-based gap-filling (fastGapFill / swiftGapFill)'."),
    "gapFillMILP": (f"{P}.gapfilling.fill_gaps_kumar_milp", "Objective-based gap-filling under a growth floor (Kumar 2007)."),
    "gapFillTopological": (f"{P}.gapfilling.analyse_topology", "Both are the BFS metabolite-producibility pre-screen."),
    # INIT / ftINIT.
    "INITStepDesc": (f"{P}.init.InitStep", "Describes one step of the ftINIT schedule."),
    "ftINITInternalAlg": (f"{P}.init.run_ftinit", "The single-step ftINIT MILP, beneath the full pipeline."),
    "ftINITFillGapsForAllTasks": (f"{P}.init.fill_tasks", "Task-aware gap-filling within ftINIT."),
    "scoreComplexModel": (f"{P}.init.score_reactions_from_genes", "Gene scores to reaction scores via the GPR."),
    # Sampling.
    "sampleMaxVolEllipse": (
        f"{P}.analysis.max_volume_ellipsoid",
        "The MVE core of CHRR. Per flux_sampling_algorithms.md the Python one is the "
        "numerically validated reference the MATLAB mirrors line-for-line --- a strong "
        "scenario candidate.",
    ),
    # Manipulation and GPR handling.
    "changeGrRules": (f"{P}.manipulation.change_gene_reaction_rules", "Confirmed by the protocol table in todo.md."),
    "contractModel": (
        f"{P}.manipulation.remove_duplicate_reactions",
        "todo.md flags these as NOT exactly equivalent --- a behaviour row, so no scenario "
        "asserting identity until the difference is characterised.",
    ),
    "grRuleToDNF": (f"{P}.manipulation.gpr_to_dnf", "Rewrites a GPR into disjunctive normal form."),
    "isDnfGrRule": (f"{P}.utils.is_dnf", "Direct counterpart; see the standardizeGrRules repair below."),
    # Reconstruction.
    "getBlast": (f"{P}.reconstruction.homology.run_blast", "Confirmed by migration.md and the protocol table."),
    "getDiamond": (f"{P}.reconstruction.homology.run_diamond", "Confirmed by migration.md and the protocol table."),
    # Annotation, omics, localisation, biomass, curation.
    "assignSBOterms": (f"{P}.annotation.add_sbo_terms", "Confirmed by yaml_format.md, which names both."),
    "deltaGCSV": (f"{P}.annotation.load_delta_g_csv", "The read half; save_delta_g_csv is the write half."),
    "scoreModel": (f"{P}.omics.hpa_gene_scores", "migration.md maps parseHPA/parseHPArna/scoreModel onto the omics module."),
    "getUniProtScores": (f"{P}.localization.fetch_uniprot_localization", "Fetches per-gene localisation evidence from UniProtKB."),
    "getBiomassFractions": (f"{P}.biomass.sum_biomass", "Mass fractions per biomass component class."),
    "scaleBiomassFraction": (f"{P}.biomass.scale_biomass", "Rescale one component class to a target fraction."),
    "scaleBiomassPseudoreaction": (f"{P}.biomass.rescale_pseudoreaction", "Rescale the pseudoreaction coefficients."),
    "curateModelFromTables": (f"{P}.curation.batch_curate_from_tsv", "Table-driven batch curation."),
    # The implementations were always in manipulation/compartments.py; only the package
    # exports were missing. This triage surfaced that as two pending rows, and raven-toolbox
    # commit "manipulation: export merge_compartments and copy_to_compartment" fixed it.
    "copyToComps": (f"{P}.manipulation.copy_to_compartment", "Duplicate reactions into a target compartment."),
    "mergeCompartments": (f"{P}.manipulation.merge_compartments", "Collapse a multi-compartment model into one."),
}

# migration.md paired `is_dnf` with standardizeGrRules' lint half. `is_dnf` is the direct
# counterpart of isDnfGrRule; the lint half is find_non_dnf_grrules.
REPAIR: dict[str, str] = {
    "standardizeGrRules": f"{P}.utils.find_non_dnf_grrules",
}

# --------------------------------------------------------------------------------------
# Covered by cobrapy. The single largest category, and the direct consequence of building
# raven-toolbox on cobra rather than on a RAVEN-shaped struct.
# --------------------------------------------------------------------------------------
def cobra(what: str, extra: str = "") -> str:
    return f"cobrapy covers this: {what}." + (f" {extra}" if extra else "")


VIA_DEPENDENCY: dict[str, str] = {
    # Solver layer.
    "solveLP": cobra("model.optimize()"),
    "optimizeProb": cobra("model.optimize(), with optlang underneath"),
    "checkSolution": cobra("the Solution object carries status, objective_value and fluxes"),
    "setRavenSolver": cobra('model.solver = "gurobi"'),
    "qMOMA": cobra("cobra.flux_analysis.moma(linear=False)"),
    # Flux analysis.
    "getAllowedBounds": cobra("cobra.flux_analysis.flux_variability_analysis"),
    "looplessFVA": cobra("cobra.flux_analysis.flux_variability_analysis(loopless=True)"),
    "cycleFreeFlux": cobra("cobra.flux_analysis.loopless_solution / add_loopless"),
    "haveFlux": cobra(
        "cobra.flux_analysis.find_blocked_reactions",
        "Confirmed by the gap-analysis row in todo.md. Tolerance semantics differ slightly.",
    ),
    "getEssentialRxns": cobra("cobra.flux_analysis.find_essential_reactions"),
    "getMinimalMedium": cobra("cobra.medium.minimal_medium"),
    "findGeneDeletions": cobra("cobra.flux_analysis.single_gene_deletion / double_gene_deletion"),
    "runProductionEnvelope": cobra("cobra.flux_analysis.production_envelope"),
    "runPhenotypePhasePlane": cobra("cobra.flux_analysis.production_envelope over two varying reactions"),
    "runRobustnessAnalysis": cobra("cobra.flux_analysis.production_envelope over one varying reaction"),
    # Gap analysis primitives.
    "canProduce": cobra(
        "analyse_topology plus cobra.flux_analysis.find_blocked_reactions",
        "Confirmed by the gap-analysis row in todo.md.",
    ),
    "canConsume": cobra(
        "analyse_topology plus cobra.flux_analysis.find_blocked_reactions",
        "Confirmed by the gap-analysis row in todo.md.",
    ),
    "checkProduction": cobra(
        "analyse_topology plus cobra.flux_analysis.find_blocked_reactions",
        "Confirmed by the gap-analysis row in todo.md.",
    ),
    "getAllSubGraphs": cobra(
        "analyse_topology plus cobra.flux_analysis.find_blocked_reactions",
        "Confirmed by the gap-analysis row in todo.md.",
    ),
    # Model surgery.
    "addMets": cobra("model.add_metabolites([cobra.Metabolite(...)])"),
    "addGenesRaven": cobra("genes are created automatically from a reaction's GPR"),
    "addExchangeRxns": cobra("model.add_boundary(metabolite, type='exchange')"),
    "removeReactions": cobra(
        "model.remove_reactions(remove_orphans=...)",
        "IMPROVEMENTS.md records the decision: with orphan cleanup kept coupled the wrapper "
        "added nothing, so it was removed entirely.",
    ),
    "deleteUnusedGenes": cobra(
        "cobra.manipulation.prune_unused_genes",
        "raven_toolbox.manipulation.remove_genes also covers it.",
    ),
    # Queries.
    "getIndexes": cobra(
        "DictList get_by_id / get_by_any / query",
        "IMPROVEMENTS.md: deliberately not ported --- a 1-based index resolver is redundant "
        "in an object model. Only the name[comp] sliver was kept, as utils.parse_name_comp.",
    ),
    "getExchangeRxns": cobra("model.exchanges"),
    "getTransportRxns": cobra("a one-liner over reaction.compartments"),
    "getAllRxnsFromGenes": cobra("gene.reactions"),
    "getGenesFromGrRules": cobra("GPR.genes on the parsed syntax tree"),
    "parseGrRule": cobra("the GPR parser; assigning gene_reaction_rule parses it"),
    "grRuleToString": cobra("GPR.to_string()"),
    "buildEquation": cobra("reaction.build_reaction_string(use_metabolite_names=...)"),
    "constructS": cobra("cobra.util.array.create_stoichiometric_matrix"),
    # I/O.
    "importModel": cobra("cobra.io.read_sbml_model", "Confirmed by the protocol table in todo.md."),
    "exportModel": cobra("cobra.io.write_sbml_model", "Confirmed by the protocol table in todo.md."),
    "readFasta": "Biopython's SeqIO covers FASTA parsing; raven-toolbox reads sequences through it.",
    # Sampling.
    "sampleACHR": cobra(
        "cobra.sampling.ACHRSampler",
        "flux_sampling_algorithms.md section 8: the Python side wraps cobra's mature ACHR "
        "rather than reimplementing it. MATLAB had neither sampler, so it implements both.",
    ),
    "sampleWarmupPoints": cobra("ACHRSampler generates its own warmup points internally"),
}

# --------------------------------------------------------------------------------------
# The capability exists on the Python side, inside something else. RAVEN splits these out
# because MATLAB allows one public function per file.
# --------------------------------------------------------------------------------------
SUBSUMED: dict[str, str] = {
    "gapFillFastCore": "The L1-norm LP subroutine of gapFillFastLP; inside fill_gaps_fast_lp on the Python side.",
    "gapFillSwiftCore": "The SWIFTCORE LP subroutine of swiftGapFill; inside fill_gaps_fast_lp on the Python side.",
    "checkRxn": "Single-reaction feasibility probe, used inside the gap-analysis entry points.",
    "consumeSomething": "Consumption probe used inside the gap analysis; not a separate Python entry point.",
    "makeSomething": "Production probe used inside the gap analysis; not a separate Python entry point.",
    "ftINITFillGapsMILP": "The inner MILP of the ftINIT task gap-fill; inside init.fill_tasks.",
    "ftINITFillGaps": (
        "Single-task variant. migration.md paired it with fill_tasks, but ftINIT.m actually calls "
        "ftINITFillGapsForAllTasks, and fill_tasks takes the whole task list --- so the ForAllTasks "
        "row carries the pairing and this one is folded into it."
    ),
    "getExprForRxnScore": "Inverse of the reaction-scoring step, folded into the init scoring functions.",
    "rescaleModelForINIT": "Numerical preconditioning inside the ftINIT preparation, part of prep_init_model.",
    "reverseRxns": "Direction-flipping helper used by the INIT preprocessing.",
    "parseYAML": "The RAVEN YAML tokeniser; inside io.read_yaml_model.",
    "writeExcel": "Sheet writer; inside io.export_to_excel.",
    "cleanSheet": "Excel cell-cleaning helper; inside io.export_to_excel.",
    "parseFormulas": "Chemical-formula parser; inside utils.get_elemental_balance.",
    "parseRxnEqu": "Equation-string parser; inside manipulation.add_reactions_from_equations.",
    "findPotentialErrors": "Structural checks folded into utils.check_model's report.",
    "sortModel": "Field-and-entity sorting; utils.sort_identifiers covers the identifier ordering that matters in cobra.",
    "compareRxnsGenesMetsComps": "Pairwise entity comparison; comparison.compare_models returns the same information as tidy DataFrames for N models.",
    "getModelFromKEGG": "Building the model from KO assignments is a stage inside reconstruction.kegg.get_kegg_model_for_organism.",
    "sampleCHRR": "CHRR is reached through analysis.random_sampling(method='chrr'); the implementation is the private _sample_chrr.",
    "sampleChebyshevCenter": "Interior-point start for CHRR; the private _chebyshev_center, over scipy linprog.",
}

# --------------------------------------------------------------------------------------
# Deliberately one-sided, with the decision recorded upstream.
# --------------------------------------------------------------------------------------
MATLAB_ONLY: dict[str, str] = {
    "ravenCobraWrapper": (
        "cobra is the canonical object in raven-toolbox --- there is no parallel RAVEN "
        "struct to convert to or from. Recorded in migration.md under 'deliberately not ported'."
    ),
    "standardizeModelFieldOrder": (
        "RAVEN struct field ordering is moot in an object model; cobra has no field order to "
        "standardise."
    ),
    "permuteModel": (
        "Row/column permutation of the RAVEN struct's parallel arrays. Meaningless in cobra, "
        "where entities are objects rather than array positions."
    ),
    "printFluxes": (
        "Console formatting of a flux vector. Python users print a pandas Series or DataFrame; "
        "listed as MATLAB-only in todo.md."
    ),
    "printModel": "Console model summary. Not ported; cobra's repr and DataFrames cover it.",
    "printModelStats": "Console model statistics. Not ported; compare_models and cobra's repr cover it.",
}

PYTHON_PENDING_NOTE = (
    "No port decision is recorded either way. Left in the queue rather than declared a "
    "divergence, so the choice stays visible."
)

PYTHON_PENDING: dict[str, str] = {
    "analyzeSampling": "Correlates per-reaction expression t-scores with flux samples. " + PYTHON_PENDING_NOTE,
    "compareFluxes": "Diagnostic flux comparison across conditions; cobra_raven_comparison.md calls it a practical tool COBRA lacks. " + PYTHON_PENDING_NOTE,
    "followChanged": "Walks reactions whose flux changed between two solutions. " + PYTHON_PENDING_NOTE,
    "followFluxes": "Traces flux through a metabolite's producers and consumers. " + PYTHON_PENDING_NOTE,
    "getFluxZ": "Z-scores fluxes across a sample set. " + PYTHON_PENDING_NOTE,
    "traceFluxPath": "Traces a carbon/flux path between two reactions. " + PYTHON_PENDING_NOTE,
    "walkFluxes": "Graph walk over the flux network. " + PYTHON_PENDING_NOTE,
    "getMinNrFluxes": "Minimal-cardinality flux set (a MILP, not cobra's L1 pFBA). " + PYTHON_PENDING_NOTE,
    "runSimpleOptKnock": "Reaction-knockout strain design. cobrapy dropped its design module; straindesign and mewpy cover this ground. " + PYTHON_PENDING_NOTE,
    "gapReport": "Summary report over a gap analysis. analyse_topology returns the data; the reporting layer is not ported. " + PYTHON_PENDING_NOTE,
    "findLeakMetabolite": "Finds metabolites produced from nothing (leaks). " + PYTHON_PENDING_NOTE,
    "exportToTabDelimited": "Tab-delimited model export. " + PYTHON_PENDING_NOTE,
    "modelSummary": "Console/struct model summary. " + PYTHON_PENDING_NOTE,
    "generateNewIds": "Generates the next free id in a model's numbering scheme. " + PYTHON_PENDING_NOTE,
    "removeBadRxns": "Flags reactions with structural problems for review. " + PYTHON_PENDING_NOTE,
    "replaceMets": "Substitutes one metabolite for another across the model. " + PYTHON_PENDING_NOTE,
    "addIdentifierPrefix": "Adds an SBML-safe prefix to model identifiers. " + PYTHON_PENDING_NOTE,
    "removeIdentifierPrefix": "Strips the SBML-safe identifier prefix. " + PYTHON_PENDING_NOTE,
    "fitParameters": "Fits growth-associated maintenance parameters to measured data. " + PYTHON_PENDING_NOTE,
    "downloadGenomeData": "Fetches genome/proteome files for a reconstruction. " + PYTHON_PENDING_NOTE,
    "getGeneData": "Retrieves per-gene annotation for curation. " + PYTHON_PENDING_NOTE,
    "processProteinFastaFile": "Normalises a proteome FASTA before homology search. " + PYTHON_PENDING_NOTE,
    "renameModelGenes": "Renames genes across GPRs and the gene list. " + PYTHON_PENDING_NOTE,
    "guessComposition": "Infers biomass composition from a related organism. " + PYTHON_PENDING_NOTE,
}

# --------------------------------------------------------------------------------------
# MATLAB glue: not part of the cross-implementation API in any language.
# --------------------------------------------------------------------------------------
ARG_GLUE = "MATLAB argument-validation glue. Python uses ordinary keyword arguments and type hints."

INTERNAL: dict[str, str] = {
    "checkInstallation": "Installation check. Python installs with pip.",
    "runRAVENtests": "Test-suite runner. Python uses pytest.",
    "setRavenSolver_placeholder": "",
    "convertCharArray": ARG_GLUE,
    "emptyOrLogicalScalar": ARG_GLUE,
    "emptyOrTextOrCellOfText": ARG_GLUE,
    "emptyOrTextScalar": ARG_GLUE,
    "parseRAVENargs": ARG_GLUE,
    "ravenModelFields": "Enumerates the RAVEN struct's field names --- meaningless in an object model.",
    "ravenList": "MATLAB cell-array helper.",
    "printOrange": "Coloured console output. Python uses the logging module.",
    "progressReport": "Console progress display. Python uses logging / tqdm.",
    "setRavenProgress": "Toggles the console progress display.",
    "parallelWorkersRAVEN": "MATLAB Parallel Computing Toolbox pool setup.",
    "checkFileExistence": "File-existence glue with MATLAB dialog prompts.",
    "getWSLpath": "Windows-to-WSL path translation for the external binaries. Python resolves binaries through raven_toolbox.binaries.",
    "makeFakeBlastStructure": "Fabricates a BLAST result struct for tests and for merging KEGG with homology draft models.",
    "splitProbForConditioning": "Numerical conditioning of a MATLAB LP before it goes to the solver.",
}
INTERNAL.pop("setRavenSolver_placeholder")

# --------------------------------------------------------------------------------------
# Python-only. Kept deliberately narrow: types, constants, and steps that only exist
# because the Python design decomposed something RAVEN keeps whole.
# --------------------------------------------------------------------------------------
RESULT_TYPE = (
    "Result type. RAVEN returns several parallel outputs; raven-toolbox returns one "
    "dataclass, so this has no MATLAB counterpart by design."
)
DATA_TYPE = "Parsed-data type. RAVEN passes structs and parallel cell arrays instead."
CONSTANT = "Default-value constant, exported so callers can inspect and override it. RAVEN hard-codes the equivalent."
KEGG_STEP = (
    "One stage of the KEGG reconstruction pipeline, exported separately so the expensive "
    "artefact build can be cached and re-run. RAVEN keeps all five stages inside "
    "getKEGGModelForOrganism."
)
SIMPLIFY_MODE = (
    "One mode of RAVEN's simplifyModel, split into its own function. migration.md records "
    "that the cobra-covered modes were cheatsheeted rather than wrapped."
)

PYTHON_ONLY: dict[str, str] = {
    # Result and data types.
    f"{P}.analysis.FSEOFResult": RESULT_TYPE,
    f"{P}.analysis.FluxSamplingResult": RESULT_TYPE,
    f"{P}.analysis.RandomSamplingResult": RESULT_TYPE,
    f"{P}.analysis.ReporterResult": RESULT_TYPE,
    f"{P}.gapfilling.FastLPResult": RESULT_TYPE,
    f"{P}.gapfilling.GapFillResult": RESULT_TYPE,
    f"{P}.gapfilling.KumarGapFillResult": RESULT_TYPE,
    f"{P}.gapfilling.TopologicalAnalysisResult": RESULT_TYPE,
    f"{P}.init.FtInitResult": RESULT_TYPE,
    f"{P}.init.InitModelResult": RESULT_TYPE,
    f"{P}.init.InitResult": RESULT_TYPE,
    f"{P}.init.TaskFillResult": RESULT_TYPE,
    f"{P}.curation.CurationResult": RESULT_TYPE,
    f"{P}.comparison.DiffReport": RESULT_TYPE,
    f"{P}.comparison.ModelComparison": RESULT_TYPE,
    f"{P}.tasks.EssentialReactionsResult": RESULT_TYPE,
    f"{P}.tasks.TaskResult": RESULT_TYPE,
    f"{P}.reconstruction.homology.HomologyResult": RESULT_TYPE,
    f"{P}.localization.AssignmentProposal": RESULT_TYPE,
    f"{P}.localization.LocalizationProposal": RESULT_TYPE,
    f"{P}.localization.LocalizationResult": RESULT_TYPE,
    f"{P}.localization.RelocationResult": RESULT_TYPE,
    f"{P}.localization.ReviewReport": RESULT_TYPE,
    f"{P}.localization.PreparedFasta": RESULT_TYPE,
    f"{P}.utils.ElementalBalance": RESULT_TYPE,
    f"{P}.utils.GPRIssue": RESULT_TYPE,
    f"{P}.utils.ModelIssue": RESULT_TYPE,
    f"{P}.tasks.Task": DATA_TYPE,
    f"{P}.init.PrepData": "RAVEN's prepData struct, as a type. The data exists in RAVEN; the class does not.",
    f"{P}.init.ReactionMasks": "RAVEN's toIgnore* index sets, as a type.",
    f"{P}.biomass.BiomassComponent": DATA_TYPE,
    f"{P}.biomass.BiomassConfig": DATA_TYPE,
    f"{P}.omics.HPAData": DATA_TYPE,
    f"{P}.omics.HPARnaData": DATA_TYPE,
    f"{P}.io.EcData": "The enzyme-constrained payload geckopy writes into the shared YAML schema.",
    f"{P}.localization.LocalizationScores": DATA_TYPE,
    f"{P}.localization.GrowthCondition": DATA_TYPE,
    f"{P}.localization.SubstrateOntology": DATA_TYPE,
    f"{P}.localization.TransporterAnnotation": DATA_TYPE,
    f"{P}.reconstruction.kegg.KeggCompound": DATA_TYPE,
    f"{P}.reconstruction.kegg.KeggKO": DATA_TYPE,
    f"{P}.reconstruction.kegg.KeggReaction": DATA_TYPE,
    f"{P}.reconstruction.kegg.PhylDist": DATA_TYPE,
    # Constants.
    f"{P}.annotation.DEFAULT_BIOMASS_MET_NAMES": CONSTANT,
    f"{P}.annotation.DEFAULT_BIOMASS_RXN_NAME": CONSTANT,
    f"{P}.annotation.DEFAULT_NGAM_RXN_NAME": CONSTANT,
    f"{P}.comparison.DEFAULT_ANNOTATION_KEYS": CONSTANT,
    f"{P}.conditions.DEFAULT_RESET_EXCHANGES_UPPER_BOUND": CONSTANT,
    f"{P}.curation.DEFAULT_CORE_GENE_COLUMNS": CONSTANT,
    f"{P}.curation.DEFAULT_CORE_MET_COLUMNS": CONSTANT,
    f"{P}.curation.DEFAULT_CORE_RXN_COEFFS_COLUMNS": CONSTANT,
    f"{P}.curation.DEFAULT_CORE_RXN_COLUMNS": CONSTANT,
    f"{P}.localization.DEEPLOC_COMPARTMENT_TRUST": CONSTANT,
    f"{P}.reconstruction.homology.HIT_COLUMNS": CONSTANT,
    f"{P}.omics.HPA_LEVEL_SCORES": CONSTANT,
    # Steps split out of something RAVEN keeps whole.
    f"{P}.init.classify_reactions": "The toIgnore classification, split out of prepINITModel so it can be inspected.",
    f"{P}.init.gene_scores_from_expression": "RAVEN's 5*ln(level/reference) scoring, split out of the INIT entry points.",
    f"{P}.analysis.find_good_reactions": "The non-loop flux screen randomSampling performs inline when choosing random objectives.",
    f"{P}.annotation.save_delta_g_csv": "The write half of the deltaG CSV round-trip; RAVEN's deltaGCSV only reads.",
    f"{P}.omics.rna_gene_scores": "The RNA-seq half of RAVEN's scoreModel, split from the HPA half.",
    f"{P}.manipulation.simplify_model": "Umbrella entry point over the individual simplify passes, which RAVEN exposes only as simplifyModel modes.",
    f"{P}.manipulation.constrain_reversible_reactions": SIMPLIFY_MODE,
    f"{P}.manipulation.group_linear_reactions": SIMPLIFY_MODE,
    f"{P}.manipulation.remove_no_flux_reactions": SIMPLIFY_MODE,
    f"{P}.manipulation.remove_zero_interval_reactions": SIMPLIFY_MODE,
    f"{P}.tasks.find_task_essential_reactions": "The essentialRxns output of RAVEN's checkTasks, as its own entry point.",
    f"{P}.curation.batch_curate": "In-memory DataFrame variant of batch_curate_from_tsv, which carries the parity row.",
    f"{P}.conditions.load_condition": "Reads a growth-condition table; RAVEN's applyCondition reads the file itself.",
    f"{P}.conditions.set_reaction_bounds": "Bounds helper behind apply_condition; RAVEN uses setParam.",
    f"{P}.localization.apply_assignment": "Materialises an AssignmentProposal; RAVEN's predictLocalization always applies in place.",
    f"{P}.localization.apply_localization": "Materialises a LocalizationProposal; RAVEN always applies in place.",
    f"{P}.localization.combine_scores": "Merges evidence from several predictors, which RAVEN's single-source parseScores never needs.",
    f"{P}.localization.load_uniprot": "Parses a downloaded UniProtKB TSV export; the fetching half carries the parity row.",
    f"{P}.localization.prepare_deeploc_input": "Writes the FASTA to feed DeepLoc; pairs with load_deeploc.",
    f"{P}.localization.fetch_protein_sequences": "Fetches model gene sequences from UniProtKB for the predictors.",
    f"{P}.localization.annotate_proteome": "Runs a predictor over a whole proteome; the loaders carry the parity rows.",
    f"{P}.localization.default_metabolite_chebi": "Default ChEBI lookup behind the transport-evidence scoring.",
    f"{P}.localization.default_substrate_of": "Default substrate lookup behind the transport-evidence scoring.",
    f"{P}.reconstruction.homology.blast_from_table": "Adapter for a pre-computed hit table; listed under 'new in raven-toolbox' in migration.md.",
    f"{P}.reconstruction.homology.make_ortholog_hits": "Builds the ortholog hit set the homology draft consumes.",
    f"{P}.reconstruction.homology.validate_hits": "Validates a hit table's shape before use.",
    f"{P}.reconstruction.kegg.parse_taxonomy": "Lineage parsing behind phyl_dist; RAVEN's getPhylDist does both at once.",
    f"{P}.reconstruction.kegg.parse_taxonomy_records": "Record-level half of parse_taxonomy.",
}

for _name in (
    "assign_kos", "build_hmm_library", "build_kegg_tables", "build_ko_fastas", "build_ko_hmm",
    "build_reference_model", "download_kegg_dump", "extract_kegg_dump", "fetch_kegg_files",
    "get_kegg_model_for_organism_from_artefacts", "get_kegg_model_from_sequences",
    "get_kegg_model_from_sequences_with_artefacts", "organism_domains", "organisms_in_domain",
    "parse_hmmsearch_tblout", "parse_kegg_compounds", "parse_kegg_dump", "parse_kegg_kos",
    "parse_kegg_reactions", "read_kegg_table", "run_hmmsearch", "stream_organism_gene_ko",
    "write_kegg_tables",
):
    PYTHON_ONLY[f"{P}.reconstruction.kegg.{_name}"] = KEGG_STEP

# --------------------------------------------------------------------------------------
# New capabilities with no RAVEN counterpart. Queued rather than declared Python-only,
# because the stated policy is that MATLAB gains new functionality unless decided otherwise.
# --------------------------------------------------------------------------------------
MATLAB_PENDING: dict[str, str] = {
    f"{P}.localization.load_mulocdeep": (
        "MULocDeep evidence loader --- a predictor RAVEN's parseScores has no adapter for. "
        "migration.md marks it '(new)'."
    ),
    f"{P}.localization.load_compartments": (
        "COMPARTMENTS (jensenlab.org) evidence loader --- a source RAVEN has no adapter for. "
        "migration.md marks it '(new)'."
    ),
    f"{P}.localization.annotate_transporters": (
        "Transport-protein annotation, the entry point of the transport-evidence subsystem. "
        "No RAVEN counterpart; todo.md lists it among the Python-only subsystems worth "
        "documenting, but it is a capability MATLAB could gain."
    ),
    f"{P}.localization.evidence_aware_transport_cost": (
        "Evidence-weighted transport cost used by assign_compartments. Pairs with "
        "annotate_transporters; back-port alongside it."
    ),
    f"{P}.localization.curation_priority": (
        "Ranks genes by how much a curation decision would change the placement. No RAVEN "
        "counterpart."
    ),
    f"{P}.localization.triage_localization": (
        "Turns a certification report into a reviewable triage list. No RAVEN counterpart."
    ),
    f"{P}.localization.relocate_reactions": (
        "Moves reactions between compartments given an accepted proposal. No RAVEN counterpart."
    ),
    f"{P}.io.export_model_to_sif": (
        "Cytoscape SIF export (rc / rr / cc graphs). migration.md lists this under I/O as a port "
        "of exportModelToSIF, but MATLAB RAVEN has no such function on any branch --- so it is new "
        "functionality, not a port."
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-n", "--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_config()
    pair = config.pair("raven")
    inventory = build_inventory(pair)
    ledger = load_ledger(pair.ledger)
    applied = 0

    def absorb(python_name: str, keep: Entry) -> None:
        """Drop the one-sided stub seeding left for a now-paired export."""
        ledger.entries[:] = [
            e
            for e in ledger.entries
            if e is keep or not (e.python == python_name and e.matlab is None and e.status == "unreviewed")
        ]

    # 1. Repairs first --- they free up an export another row is about to claim.
    for matlab, python in REPAIR.items():
        entry = ledger.by_matlab().get(matlab)
        if entry is None or python not in inventory.python_keys:
            print(f"  ! cannot repair {matlab}")
            continue
        absorb(python, entry)
        entry.python = python
        entry.status = "parity"
        applied += 1

    # 2. New pairings.
    for matlab, (python, note) in PAIR.items():
        entry = ledger.by_matlab().get(matlab)
        if entry is None:
            print(f"  ! no row for {matlab}")
            continue
        if python not in inventory.python_keys:
            print(f"  ! {python} is not exported --- skipping {matlab}")
            continue
        absorb(python, entry)
        entry.python = python
        entry.status = "parity"
        entry.notes = note
        applied += 1

    by_matlab, by_python = ledger.by_matlab(), ledger.by_python()

    def decide(key: str, **fields) -> None:
        nonlocal applied
        entry = by_matlab.get(key) or by_python.get(key)
        if entry is None:
            print(f"  ! no row for {key}")
            return
        for name, value in fields.items():
            setattr(entry, name, value)
        applied += 1

    for name, reason in VIA_DEPENDENCY.items():
        decide(name, status="via-dependency", python=None, reason=reason, notes=None)
    for name, reason in SUBSUMED.items():
        decide(name, status="subsumed", python=None, reason=reason, notes=None)
    for name, reason in MATLAB_ONLY.items():
        decide(name, status="matlab-only", python=None, reason=reason, notes=None)
    for name, reason in INTERNAL.items():
        decide(name, status="internal", reason=reason, notes=None)
    for name, note in PYTHON_PENDING.items():
        decide(name, status="python-pending", python=None, notes=note, reason=None)
    for name, reason in PYTHON_ONLY.items():
        decide(name, status="python-only", matlab=None, reason=reason, notes=None)
    for name, note in MATLAB_PENDING.items():
        decide(name, status="matlab-pending", matlab=None, notes=note, reason=None)

    # Anything still paired and unreviewed is a straight port the seeder matched by name and
    # migration.md corroborates: confirm it rather than leaving it in limbo.
    for entry in ledger.entries:
        if entry.status == "unreviewed" and entry.matlab and entry.python:
            entry.status = "parity"
            entry.notes = entry.notes or "Name-matched port, corroborated by migration.md."
            applied += 1

    print(f"triaged {applied} row(s)")
    remaining = [e.label for e in ledger.entries if e.status == "unreviewed"]
    if remaining:
        print(f"\nstill unreviewed ({len(remaining)}):")
        for name in remaining:
            print(f"  {name}")

    if args.dry_run:
        print("(dry run --- nothing written)")
        return 0

    save_ledger(ledger, pair.ledger)
    print(f"wrote {pair.ledger}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
