# Compartment assignment and confidence tracking — evidence base

The measurement and design record behind raven-toolbox's compartment-assignment
method (`assign_compartments`, `predict_localization`) and its per-reaction
confidence tracking.

These documents live here rather than on
[raven-docs](https://github.com/edkerk/raven-docs) because both features are
still in development and neither is at parity with MATLAB RAVEN. The
user-facing site documents current, settled behaviour in both toolboxes; a
benchmark of a method that is still changing describes a moving target, and
would be read as a statement about what the toolbox does today. When either
feature settles, its evidence moves back alongside the guide page that
describes it.

Nothing here is superseded. The numbers were measured as reported, and the
designs are the designs the code implements.

## Method design

| Document | What it covers |
|---|---|
| [localization_redesign.md](localization_redesign.md) | The flux-free placement MILP plus materialised-FBA certification that `assign_compartments` is built on, and why placement and certification are separated |
| [multi_localization_design.md](multi_localization_design.md) | Reaction-level multi-localisation, and the flux-activity coupling that makes the opt-in `multi_localization` flag sound |
| [transport_evidence_scoring.md](transport_evidence_scoring.md) | Replacing the blanket inter-compartment transport penalty with a per-transport, evidence-aware cost — planned for both RAVEN and raven-toolbox, which is why it sits here rather than in either |
| [confidence_tracking.md](confidence_tracking.md) | Per-reaction, multi-facet confidence scoring: the data model, the YAML and SBML round-trip, and what each facet measures |
| [curation_priority_signals.md](curation_priority_signals.md) | A catalogue of signals for ranking which assignments need manual review. Generated from a brainstorm and, by its own note, never verified against the implementation — read it as a design menu, not a result |

## Predictor benchmarks

How well DeepLoc's predictions match curated models, across four organisms
chosen for their distance from its training data.

| Document | Organism / question |
|---|---|
| [deeploc_yeast_benchmark.md](deeploc_yeast_benchmark.md) | yeast-GEM — the reference case |
| [deeploc_humangem_benchmark.md](deeploc_humangem_benchmark.md) | Human-GEM — a positive control, and the circularity it exposes |
| [deeploc_aracore_benchmark.md](deeploc_aracore_benchmark.md) | AraCore (*Arabidopsis*) — cross-kingdom, fully independent |
| [deeploc_icre1355_benchmark.md](deeploc_icre1355_benchmark.md) | iCre1355 (*Chlamydomonas*) — the most training-distant test |
| [deeploc_normalisation_benchmark.md](deeploc_normalisation_benchmark.md) | Whether raw predictor probabilities beat rescaled ones |
| [localization_finetuning.md](localization_finetuning.md) | Tuning the DeepLoc-loading hyperparameters against curated yeast-GEM |

## Method validation

| Document | What it establishes |
|---|---|
| [yeast_validation.md](yeast_validation.md) | Three yeast checks of certified assignment, including recovery of curated yeast-GEM |
| [multiorganism_validation.md](multiorganism_validation.md) | Whether the method generalises at genome scale across four kingdoms |
| [yeast_localization_benchmark.md](yeast_localization_benchmark.md) | End-to-end run — model, scoring, MILP — with a predictor-noise sweep |
| [predictlocalization_comparison.md](predictlocalization_comparison.md) | Head-to-head against RAVEN's `predictLocalization`, which optimises the same objective by a different method |

## Comparison with CarveFungi

| Document | What it covers |
|---|---|
| [carvefungi_analysis.md](carvefungi_analysis.md) | How CarveFungi's compartment assignment works, and where the two approaches diverge |
| [carvefungi_milp_benchmark.md](carvefungi_milp_benchmark.md) | This transport cost run on CarveFungi's own carve MILP, as a like-for-like test |

## Parameters

| Document | What it covers |
|---|---|
| [localization_parameters.md](localization_parameters.md) | Measured defaults for `predict_localization`, from the 2026-06-20 parameter campaign |
