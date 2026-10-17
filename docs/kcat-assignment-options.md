# Kcat gathering and assignment: three designs

Status: decided 2026-10-05, design C. The plan is `kcat-assignment-plan.md`.
Every design is meant to be implemented identically in geckopy and GECKO
(MATLAB).

## 1. How it works today

Order in the full ecModel tutorial (both implementations):

1. Gather: `fuzzyKcatMatching`, DLKcat (`writeDLKcatInput`, `runDLKcat`,
   `readDLKcatOutput`), OKP (`submit/fetchOpenKineticsPredictor`,
   `readOpenKineticsPredictorOutput`). Each returns a kcat list in memory.
2. Choose: `mergeKcats` keeps one source per reaction by a priority list,
   with BRENDA split into a top tier (no wildcards, good origin) and a bottom
   tier.
3. Assign: `assignKcatValues` writes `model.ec.kcat` and `model.ec.source`.
4. Model-side steps, each writing `model.ec.kcat` and `model.ec.source`:
   `applyCustomKcats` (`custom`), `getKcatAcrossIsozymes` (`isozymes`),
   `getStandardKcat` (`standard`), `setKcatForReactions`
   (`setKcatForReactions`), tuning (`sensitivityTuning`; CMA-ES tuning
   changes `ec.kcat` and leaves `ec.source` as it was).
5. `applyKcatConstraints` copies `ec.kcat` into the S matrix.

Problems a redesign should solve:

- **Keys depend on the build.** Gathered lists are keyed by
  `model.ec.rxns`, whose IDs depend on how the model was built: `_EXP_n`
  suffixes numbered by GPR order in full models, `001_` prefixes in light
  models. Custom kcats use a different, stable key (protein set and/or
  conventional reaction ID with `_REV`).
- **Custom kcats follow their own path.** They have their own format, file
  and matching code. In GECKO, `applyCustomKcats` has no light-model branch:
  its whole body sits inside `if ~model.ec.geckoLight`, although the light
  tutorial says it can be used. I have not checked geckopy's behaviour on
  light models. The `stoicho` column is read but used nowhere (complex
  stoichiometry comes from `applyComplexData`).
- **Gathered values are not kept.** Kcat lists exist in memory, or as ad hoc
  files (`DLKcat.tsv` doubles as DLKcat input and output; `OKP.csv` holds
  the OKP input and `OKP_output.csv` the raw output), each with its own
  columns. The MATLAB struct and the Python frame name the same fields
  differently. Neither holds an uncertainty or the evidence behind a value.
- **Provenance in the model is uneven.** `ec.source` is free text. CMA-ES
  tuning does not mark tuned kcats. `ec.notes` collects notes from custom
  kcats and sensitivity tuning.

## 2. Common ground for all three designs

These choices apply whichever design is chosen.

### 2.1 One record format with a stable key

One row is one candidate kcat for one reaction, enzyme and substrate from
one source. Column names are the same in Python, MATLAB and on disk.

| Column | Meaning |
|---|---|
| `rxn` | Reaction in the conventional model, `_REV` for the reverse direction (the customKcats convention). Empty: every reaction of `enzymes` |
| `enzymes` | UniProt accessions; a complex is joined by ` + ` in sorted order. Empty: every enzyme of `rxn` |
| `substrate` | Metabolite name as in `model.metNames`; empty for a reaction-level value |
| `kcat` | 1/s; 0 means searched without a result |
| `log10_sd` | Standard deviation of log10 kcat, if the source gives one |
| `source` | Normalized token: `custom`, `brenda`, `sabio_rk`, `uniprot`, `dlkcat`, `catapro`, `kinform_h`, ..., `ec_median`, `ec_tree`, `homologs`, `combined` |
| `ec_code`, `wildcard_level`, `origin` | Fuzzy BRENDA matching detail |
| `similarity` | Predictors: maximum identity to the method's training sequences |
| `identity`, `n_evidence` | Homologs: best identity; number of measurements behind the value |
| `organism`, `reference`, `note` | Measurement organism, PMID or record, free text |

Empty `rxn` or `enzymes` is meant for curated rows. Gatherers always fill
both.

### 2.2 One matching function

`matchKcatRecords(model, records)` / `match_kcat_records` maps records to
`model.ec` rows, the same way for every source:

1. `rxn` and `enzymes`: the copies of `rxn` (all `_EXP_n` rows in a full
   model, all `nnn_` rows in a light model) whose enzyme set equals
   `enzymes`.
2. `enzymes` only: every `model.ec` row with that enzyme set.
3. `rxn` only: every copy of `rxn`.

Partial enzyme-set matches (at least half) are reported and not applied,
as `applyCustomKcats` does today. This gives light models custom kcats.

### 2.3 Stays as it is

- The one-way rule: files feed `model.ec.kcat`; nothing in the model is
  written back to the files. Isozyme fills, standard kcats,
  `setKcatForReactions` and tuning change the model only.
- `applyKcatConstraints` runs last and is the only step that touches S.

## 3. Design A: one evidence table

### Files

```
data/kcats.tsv        every candidate record, all sources, curated rows included
data/kcatRuns.tsv     run_id, function, source, method, parameters, data_version, tool, created, rows
```

`kcats.tsv` has the record columns plus `run_id`.

### Custom kcats

Custom kcats become rows with `source = custom` and run key `manual`. They
are added by hand or with `addKcats(adapter, records)`. Gatherers replace
only their own run key's rows, so curated rows survive every regeneration.
`customKcats.tsv` is converted once with `convertCustomKcats`.

### Functions

- Gatherers return records and replace their own run's rows in
  `kcats.tsv`.
- `loadKcats(adapter, 'sources', ...)` reads and filters.
- `mergeKcats` (priority, from the adapter's `kcatSourcePriority`, with
  `custom` first) or `combineKcats` chooses one value per row.
- `assignKcatValues` matches and writes `ec.kcat` and `ec.source`.
- `applyCustomKcats` remains as a wrapper that loads the custom rows and
  assigns them with overwrite. The remaining model-side steps are unchanged.

### Strengths

- One file holds all evidence and is read once.
- Easy to query, for example every value for one reaction.
- Smallest change to the existing functions.

### Weaknesses

- Curated rows sit among tens of thousands of generated rows (ecYeastGEM: 92
  custom rows; one OKP method alone is 1.6 MB of output), so hand-editing is
  awkward.
- Every regeneration rewrites the whole file, giving large git diffs and
  merge conflicts when two people regenerate different sources.
- A failed write puts all sources at risk at once.

## 4. Design B: a registry of source files

### Files

```
data/kcatSources.tsv          the registry: one row per source file
data/kcats/custom.tsv         curated, hand-edited
data/kcats/brenda.tsv         gathered by fuzzyKcatMatching
data/kcats/dlkcat.tsv
data/kcats/okp_catapro.tsv    one file per OKP method
data/kcats/ec_tree.tsv
data/kcats/homologs.tsv
data/kcats/combined.tsv       derived from other sources
```

Registry columns:

- **Identity:** `name`, `file`, `kind` (`curated`, `gathered`, `derived`).
- **Selection:** `enabled`, and `rank`, where a lower rank wins and empty
  means not used in the priority selection.
- **Tier filters:** `max_wildcard_level` and `max_origin`, so BRENDA can be
  ranked twice (top and bottom tier) without a rule language.
- **Provenance:** `generator`, `parameters`, `inputs` (derived sources
  only), `data_version`, `tool`, `created`.
- **Integrity:** `rows` and `sha256`.

### Custom kcats

`data/kcats/custom.tsv` is an ordinary source in the record format, with
`kind = curated` and rank 1. It is still a separate, hand-edited file, but
it goes through the same matching and selection as everything else. There is
no special step. Gatherers never write curated files.

### Functions

- Gatherers write their own file, register or update their registry row,
  and return the records.
- `checkKcatSources(adapter)` reports missing files, files changed since
  registration (checksum), and sources built from an older data version.
- `assignKcatsFromSources(model, adapter)`:
  1. reads the enabled sources;
  2. for each `model.ec` row, takes the lowest-ranked source with a matching
     non-zero record, aggregating several substrates with `criteria` (max
     by default, as today);
  3. writes `ec.kcat` and `ec.source`, and a decision log
     (`output/kcatAssignment.tsv`: per `model.ec` row the chosen value, source and
     rank, and how many candidates other sources offered).
- `combineKcats` reads the sources named in its `inputs`, writes
  `combined.tsv` and registers it, so combination is just one more source
  with a rank.
- `mergeKcats` and `assignKcatValues` stay for in-memory use.
- Isozyme fill, standard kcat, constraints and tuning are unchanged.

### Strengths

- It is literally a TSV that tracks kcat files from different sources.
- Hand-curated and generated content stay apart, so git history is clean,
  regeneration replaces one file, and a failed run harms one source.
- Sources are switched on and off, or re-ranked, by editing one small file.
- Priority lives in a TSV rather than in the adapter, so MATLAB (adapter
  class) and Python (adapter TOML) read the same selection config.
- A source file can be reused in another project as is.

### Weaknesses

- More files.
- The registry and the files can drift apart, which `checkKcatSources`
  must catch.
- Selection config moves from the adapter to a data file, so existing
  adapters' `kcatSourcePriority` needs a one-time conversion.

## 5. Design C: a build recipe and one resolver

### Files

- Source files as in design B. The ledger of design A would also work.
- `data/kcatRecipe.tsv`: ordered stages that decide every `model.ec.kcat`
  before tuning. Example:

```
stage  action   sources                      options
1      select   custom
2      select   brenda                       max_wildcard_level=0; max_origin=2
3      combine  ec_tree, homologs, okp_*     level=K1
4      select   brenda
5      fill     isozymes
6      fill     standard
```

- `output/kcatDecisions.tsv`: one row per `model.ec` row, with the stage
  that decided it, the source, the value, the candidates that lost and their
  spread.

### Custom kcats

Custom kcats are stage 1 of the recipe. They live in their own curated file
as in design B, and their place in the order is written down in the recipe.

### Functions

- Gatherers as in design B.
- `buildKcats(model, adapter)` runs the recipe: a stage only decides rows
  that are still open, then `applyKcatConstraints` runs. The existing
  functions become stage implementations and stay callable on their own.
- Tuning stays outside the recipe and writes the model only.

### Strengths

- `model.ec.kcat` before tuning can be rebuilt from files with one call.
- The order of everything, including isozyme and standard fills, is visible
  and diffable in one place.
- The decision log feeds `reviewKcatAssignment` and the evotune prior widths
  directly.
- One parity scenario (same recipe, same files, same decisions) covers the
  whole chain.

### Weaknesses

- It is the largest change and adds a concept users must learn: a small
  stage language, which must be parsed identically in MATLAB and Python.
  Options should therefore come from a fixed list, not free expressions.
- The tutorials lose their step-by-step character unless the stages are
  also shown as individual calls.
- It is most at risk of over-engineering for projects that use one or two
  sources.

## 6. Comparison

| | A: one table | B: registry of files | C: recipe and resolver |
|---|---|---|---|
| Where evidence lives | One file | One file per source and a registry | As B |
| Custom kcats | Rows in the table | A curated source file of rank 1 | Recipe stage 1, own file |
| Selection config | Adapter | Registry (`rank`, tier filters) | Recipe |
| Isozyme and standard fills | Calls, as now | Calls, as now | Recipe stages |
| Rebuild pre-tuning kcats from files | With the protocol's calls | With the protocol's calls | One call |
| Git behaviour | Large diffs | Per-source diffs | Per-source diffs |
| Change to existing functions | Small | Moderate | Large |
| MATLAB port | Readers and writers | Plus registry and checks | Plus stage engine |
| Parity scenarios | Per function | Per function, plus registry | Plus whole-recipe scenario |

## 7. Recommendation

Design B, with design C's decision log but without its recipe:

- B matches the stated goal of a project TSV that tracks kcat files from
  different sources, which OKP and the other gatherers populate.
- Custom kcats join the shared logic (same format, same matching, a rank)
  while staying in their own hand-edited file. That removes the special
  path and its light-model gap, without mixing hand edits into generated
  files.
- The decision log costs little and gives the review and tuning steps the
  provenance they lack today.
- The recipe can be added later on top of B's files if one-call builds are
  wanted. Nothing in B has to change for that.

## 8. Decisions that apply to every design

- **D1. New model fields.** Today `model.ec` holds kcat, source and notes.
  Uncertainty (`ec.kcatSd`) and the value before tuning (`ec.kcatPrior`)
  would need new fields, which RAVEN's `writeYAMLmodel` / `readYAMLmodel`
  and geckopy's YAML I/O must learn. They read and write a fixed list of
  `ec` fields today. The alternative is to keep them in the decision log
  only.
- **D2. Tuning provenance.** CMA-ES tuning leaves `ec.source` unchanged.
  Options:
  - set `ec.source` to `tuned`, which loses the source class that evotune
    uses on a second run;
  - add `ec.kcatPrior` (D1);
  - write tuning notes to `ec.notes`, as sensitivity tuning does.
- **D3. `setKcatForReactions`.** Keep it as a model-only edit for
  interactive work, and point users to the curated file for changes that
  should survive a rebuild.
- **D4. Redistribution of the measurement table** behind `ec_tree` and
  `homologs` (BRENDA, SABIO-RK and EnzyExtractDB terms), as in the earlier
  plan.
- **D5. Migration.** Provide converters from `customKcats.tsv` and from the
  old in-memory kcat lists. Old function names keep working for one release
  with a warning.

## 9. Reconsideration, 2026-10-15

With the TOML adapter shared by both tools, and with the kcat-benchmark
results, the design was reconsidered as nine independent choices. The
option chosen is in bold; `kcat-assignment-plan.md` builds on them.

| Choice | Options |
|---|---|
| C1. What is stored | nothing (today) · **one file per source** · one table of all candidates · final decisions only · inside the ecModel · a SQLite file |
| C2. Key of a stored row | `ec.rxns` · **conventional reaction + enzyme set (+ substrate)** · enzyme + substrate + EC, without reactions · both |
| C3. Granularity | **one value per reaction per source** · every candidate per enzyme–substrate pair |
| C4. Bookkeeping | registry TSV · **self-describing files, tracked in git** · a JSON file per kcat file · a list in the TOML · none |
| C5. Order of sources | **`model_adapter.toml`** · a recipe TSV · registry columns · the user's script · named presets only |
| C6. Choosing a value | first source wins · trust weights · combine by uncertainty · fixed rule (max, median) · **stages of these, with presets** |
| C7. Gatherers | unchanged plus a save function · **one function per source, `kcatsFrom<Source>`, writing its file, plus a save function for special cases** · one dispatcher (chosen first, then dropped: each source runs differently and has its own options) |
| C8. Custom kcats | separate step (today) · **a curated source** · an override applied last |
| C9. Entry point | functions per step · dispatcher · gather then decide · **one call plus the building blocks**: `updateKcatSources` gathers what the configuration needs, `collectKcats` decides, `assignKcats` applies |

Complete plans that were weighed:

| Plan | Choices | Outcome |
|---|---|---|
| 0. Save what exists | files keyed by `ec.rxns`, script as recipe | files tied to one model build |
| K. Stable keys, order in TOML | as chosen, with a registry | chosen, with self-describing files instead of the registry |
| P2. The 2026-10-05 plan | record format v2, rewritten gatherers, recipe TSV | too much rewriting; the recipe file duplicates the TOML |
| T. One candidate table | all sources in one file | re-gathering one source rewrites a shared file |
| Q. Organism-level store | keyed by enzyme, substrate and EC | needs substrate mapping for assignment; most new code |
| E. Presets only | named presets with switches | kept as shortcuts on top of K |
| M. In the model | candidates saved in the ecModel | breaks the one-way rule |

Reference data (BRENDA, DLKcat) was weighed as: two separate BRENDA
datasets in the repositories (R1); one per-measurement table in the
repositories (R2); a versioned download (R3); related tables (R4); a slim
shipped file plus downloads (R5). Chosen: release assets in
`CompMetEng/toolbox-assets`, which raven-data becomes, reusing RAVEN's
and raven-toolbox's existing download code; all BRENDA files together in
one release, and the DLKcat files in another.
