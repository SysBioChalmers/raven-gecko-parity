# Tracking parameter changes in an ecModel: three options

Status: decided 2026-10-05, option 2 with decisions E1 to E4 (section 8).
The plan is `kcat-assignment-plan.md`. Applies to geckopy and GECKO
alike, and to RAVEN and raven-toolbox where the model file format is
involved. Companion to `kcat-assignment-options.md`.

## 1. What should be tracked

Every change to a parameter that determines what an ecModel can do, with
the amount and the reason.

| Parameter | Changed by | Recorded today |
|---|---|---|
| kcat (`ec.kcat`) | `assignKcatValues` | `ec.source` |
| | `applyCustomKcats` | `ec.source = custom`, note appended to `ec.notes` |
| | `getKcatAcrossIsozymes` | `ec.source = isozymes` |
| | `getStandardKcat` | `ec.source = standard` |
| | `setKcatForReactions` | `ec.source = setKcatForReactions` |
| | `sensitivityTuning` | `ec.source = sensitivityTuning`, `preTuneKcat=...` in `ec.notes` |
| | CMA-ES tuning | nothing in the model; the ecYeastGEM build script writes `corrections.tsv` (with geckopy's `corrections_tsv`), `tuning_summary.txt` and `cmaes_trace.tsv` to `output/` |
| Measured enzyme concentration (`ec.concs`) | `fillEnzConcs` | nothing (the data file and column are not kept) |
| Effective enzyme bound (upper bound of the protein usage reaction) | `constrainEnzConcs`, `flexibilizeEnzConcs`, `relaxProteomicsGreedy` | only the new bounds. `flexibilizeEnzConcs` returns old and new values, ratio and number of steps, but they are not stored. `ec.concs` keeps the measured value, so the ratio can be recomputed; the reason cannot |
| Protein pool, sigma, f | `setProtPoolSize`, `updateProtPool`, `sigmaFitter` | pool bound only |

Questions a reviewer or a later run needs answered:

- **What and how much:** old value, new value, fold change.
- **Why:**
  - tuning: which data set and objective, the RMSE before and after, the
    kcat's share of the measured leverage, and its prior class and width;
  - flexibilization: growth reached against growth expected, the condition,
    the step size and the number of steps;
  - curation: the note and reference.
- **By what:** function, parameters, seed, input files and their versions,
  tool version.
- **In which order:** a kcat can be assigned, overwritten by a custom value,
  then tuned twice.

Uses:

- review, e.g. an ecModels pull request;
- re-tuning from the pre-tuning value rather than from an earlier tuned value;
- undoing one step;
- rebuilding a model and checking that the result is the same;
- condition-specific models that branch from a common parent.

All three options use the stable keys of `kcat-assignment-options.md`: a
kcat is identified by `model.ec.rxns` plus `rxn` (conventional reaction,
`_REV` for direction) and `enzymes`. An enzyme is identified by its UniProt
accession.

## 2. Option 1: provenance as state in the model

New per-parameter fields in `model.ec`, saved in the YAML file:

| Field | Per | Meaning |
|---|---|---|
| `ec.source` | kcat | Origin of the value before model-side changes (unchanged meaning, no longer overwritten by tuning) |
| `ec.kcatPrior` | kcat | Value before any tuning; NaN if never tuned |
| `ec.kcatChange` | kcat | Last change: '', `custom`, `isozymes`, `standard`, `manual`, `sensitivityTuning`, `cmaes` |
| `ec.notes` | kcat | Free text, as now |
| `ec.concsSource` | enzyme | Data file and column or condition of `ec.concs` |
| `ec.concsFactor` | enzyme | Effective bound divided by `ec.concs` (1 when not flexibilized, Inf when relaxed) |

### What it gives

- **Self-contained:** the model answers "was this kcat tuned, from what
  value, from which source" on its own.
- **Re-tuning:** CMA-ES can centre its prior on `ec.kcatPrior`.
- **Reset:** `ec.kcat = ec.kcatPrior` undoes tuning.

### What it does not give

- **No history:** a value changed twice keeps only the first prior and the
  last change.
- **No reasons:** leverage, RMSE, growth gap and seed do not fit in
  per-parameter fields; they stay in run reports in `output/`.

### Cost

- **File format:** RAVEN's `writeYAMLmodel` and `readYAMLmodel`, the
  raven-toolbox reader and writer, and geckopy all handle a fixed list of
  `ec` fields, so all of them change. Older readers must ignore the new keys.
- **Every function that adds or removes `ec` rows or enzymes** must carry
  the new arrays along (for example `removeStandardKcat`, which deletes
  `ec.kcat`, `ec.source` and `ec.notes` entries; `addNewRxnsToEC`; subset
  functions). A missed one gives misaligned arrays.
- **Variant without a format change:** write the same information as a
  fixed-format note in `ec.notes` (`tuned=cmaes; run=...; prior=6.55`).
  `sensitivityTuning` already does this. It costs nothing, but it is free text
  that tools have to parse, and enzymes have no notes field.

## 3. Option 2: a change log next to the model

All changes are events in a log that travels with the model in memory and is
saved as files next to the model.

### Contents

`changes`: one row per changed value.

| Column | Meaning |
|---|---|
| `event` | Sequence number within this model's history |
| `run` | The run that made the change |
| `parameter` | `kcat`, `conc`, `conc_bound`, `pool`, `sigma`, `f`, `flux_bound` |
| `target` | `model.ec.rxns` entry, UniProt accession, or reaction |
| `rxn`, `enzymes` | Stable key for kcats |
| `old`, `new` | Values |
| `action` | Fixed vocabulary: `assign`, `custom`, `isozyme_fill`, `standard`, `manual`, `sensitivity_tuning`, `cmaes_tuning`, `proteomics_fill`, `constrain`, `flexibilize`, `relax`, `pool_update`, `sigma_fit`, `flux_constraint` |
| `reason` | Structured `key=value` pairs for the action, e.g. `leverage_share=0.10; rank=1; prior_class=okp; prior_sd=0.5` or `growth=0.25; target=0.41; condition=glucose; steps=3` |
| `note` | Free text (curation notes, references) |

`runs`: one row per function call that changed something.

| Column | Meaning |
|---|---|
| `run` | Identifier (time and short hash) |
| `function`, `tool` | E.g. `cmaesKcatTuning`, `GECKO 4.1 / MATLAB R2023b` or `geckopy 4.0` |
| `time` | ISO 8601 |
| `parameters`, `seed` | JSON, seed |
| `inputs` | Data files with checksums (`evotuneFluxData.tsv`, `proteomics.tsv`, kcat sources) |
| `summary` | JSON: RMSE before and after, generations; growth before and after |
| `state_before`, `state_after` | Hash of the tracked parameter vectors, to detect a log that does not belong to the model |

### How functions record

Two helpers on both sides:

- `run = startChangeRun(model, functionName, parameters, inputs)`;
- `model = recordChanges(model, run, parameter, targets, old, new, action, reason, note)`.

Every function in the table in section 1 calls them. In memory the log is a
top-level model field (MATLAB `model.changeLog`, Python `model.change_log`),
so functions that rebuild `model.ec` do not drop it, and copies of the model
carry their history.

Granularity:

- CMA-ES: one event per changed kcat, not per generation.
- Sensitivity tuning and flexibilization: one event per parameter per run,
  with the number of steps in `reason`.

### Files

```
models/ecYeastGEM.yml
models/ecYeastGEM.changes.tsv
models/ecYeastGEM.runs.tsv
```

- **Saving:** `saveEcModel` writes the two files next to the model.
- **Loading:** `loadEcModel` reads them if present, and warns if they are
  missing or their `state_after` does not match the model.
- **Model file:** the YAML format does not change.
- **Review:** GitHub renders TSV files as tables, so a pull request shows
  the changes directly.

### Tools on top

- `reportChanges(model, ...)`: filtered views. `corrections.tsv` becomes the
  view for one CMA-ES run, and the flexibilization table the view for
  `flexibilize`.
- `priorValues(model)`: the last value before any tuning, for re-tuning.
- `revertChanges(model, run)`: undo one run by writing back the `old` values.
- `checkChangeLog(model, parent)`: replay the log on the parent model (e.g.
  stage 2) and confirm that the current values come out.

### Which runs are recorded

The log records the lineage of this model. Exploratory runs that are not
applied (other seeds, budgets) stay as run reports in `output/` and are not
events. A condition-specific model copies its parent's log and continues
it.

### What it gives

- full history, with order, amounts and structured reasons;
- undo and replay;
- no change to the model file format;
- the same files in MATLAB and Python.

### Cost

- **Instrumentation:** about a dozen functions on each side, plus the
  helpers.
- **Sync risk:** the files can be separated from the model, for example when
  someone shares only the YAML. The model then still works but loses its
  history. The `state_after` hash detects a mismatched log.
- **Concurrency:** parallel jobs that each change a copy of the model need
  separate logs. Only the applied result's events join the model's log.

## 4. Option 3: a change log inside the model file

The same `changes` and `runs` tables as option 2, saved inside the YAML as
two more sections (`- ec-changes:` and `- ec-runs:`).

### What it gives

- **Everything option 2 gives,** and the history cannot be separated from the
  model.
- **No sync checks:** loading a model always loads its history.

### Cost

- **The file format changes,** as in option 1: RAVEN, raven-toolbox and
  geckopy readers and writers.
- **Larger model files.** ecYeastGEM.yml is 6.95 MB. With one `assign` event
  per `model.ec` row (4,850 rows), the log adds several thousand
  YAML entries, at roughly ten lines each.
- **Noisier git history:** each tuning or curation run adds to the model
  file.
- **Equality:** two models with identical parameters but different
  histories now differ, which affects model comparison and caching.
- **Readability:** the history is not readable as a table on GitHub.

## 5. Comparison

| | 1: state fields | 2: log next to the model | 3: log inside the model |
|---|---|---|---|
| History of several changes | No, last change only | Yes | Yes |
| Reasons (leverage, growth gap, seed) | No, run reports only | Yes | Yes |
| Travels with the YAML alone | Yes | No, separate files | Yes |
| Model file format change | Yes | No | Yes |
| Every `ec` row-changing function must carry new arrays | Yes | No | No |
| Undo and replay | Reset of tuning only | Yes | Yes |
| Review on GitHub | Hidden in YAML | Readable tables | Hidden in YAML |
| Size added to ecYeastGEM | Small | Separate files | Large |

## 6. Recommendation

Option 2, plus a tuning marker in a field the model already saves:

- The full history goes into `changes.tsv` and `runs.tsv` next to the model.
  It is carried in memory as a model field and written and read by
  `saveEcModel` and `loadEcModel`.
- Every tuning function marks the kcat in `ec.source` in a fixed format,
  keeping its origin and adding the method and the pre-tuning value
  (section 10). A model shared without its log then still shows which kcats
  were tuned and from what value. No format change is needed.

Reasons:

- It answers what, how much, why, by what and in which order, for kcats and
  enzyme concentrations alike.
- It leaves the RAVEN file format and the `ec` arrays untouched.
- It turns today's separate reports (`corrections.tsv`, the flexibilization
  table) into views of one log.

## 7. How it connects to the kcat designs

- **Assignment decision log:** with option 2 or 3, the decision log of kcat
  design B or C becomes the `assign` events of this log. With option 1, a
  separate decision log is still needed.
- **Prior widths for tuning:** evotune can read them from the log (`reason`
  of the `assign` event: source, evidence, `log10_sd`), not only from the
  `ec.source` text.
- **One-way rule:** the log records changes; it never feeds values back into
  the kcat source files.

## 8. Decisions

- **E1 (decided): one summary entry for assignment.** Assignment writes one
  `runs` row (sources and their ranks, counts per source) and one `changes`
  row with `target = *` and the counts in `reason`. The per-row origin stays
  in `ec.source` and in the kcat source files. Per-row events start with the
  first change after assignment.
- **E2 (decided): flux constraints are optional, off by default.**
  `constrainFluxData` records its bounds when the adapter's
  `logFluxConstraints` is true.
- **E3 (decided): next to the model, same base name.** See section 9.
- **E4 (decided): `ec.source` holds the origin plus a tuning status, in a
  fixed format (choice c).** See section 10.

## 9. E3: where the log files live

| | Next to the model | In `output/` | A folder per model |
|---|---|---|---|
| Layout | `models/ecYeastGEM.yml`, `models/ecYeastGEM.changes.tsv`, `models/ecYeastGEM.runs.tsv` | `output/ecYeastGEM/changes.tsv`, `output/ecYeastGEM/runs.tsv` | `models/ecYeastGEM/model.yml`, `changes.tsv`, `runs.tsv` |
| Link to the model file | Same base name | Subfolder named after the model | Same folder |
| Stage models (`_stage1`, `_stage2`) and condition-specific models | Each saved model gets its own log | One subfolder each | One folder each |
| Copying or sharing `models/` | Keeps the history | Loses it | Keeps it |
| Risk of loss | Low | `output/` is often treated as regenerable or left out of git | Low |
| Change to path conventions | None | None | Every load and save path, and the ecModels layout |

Decision: next to the model, same base name.

- `saveEcModel` writes both files and `loadEcModel` reads them, with no extra
  configuration.
- Each stage model's log describes exactly that file. The stage-2 log is the
  start of the final model's log; the duplication is small.
- A model saved under a new name (for example a condition-specific variant)
  gets its own log with the parent's history at the start.
- If a model file is renamed by hand, `loadEcModel` finds no log and warns.
  If a log of another model is placed next to it, the `state_after` hash
  does not match and it warns.

With E1 the logs are small: tens to a few hundred rows (tuned kcats, fills,
flexibilized enzymes), so two extra files per model add little.

## 10. E4: what `ec.source` means

### Who reads `ec.source` today

- **Prior groups in CMA-ES tuning.** MATLAB `resolveTunableContext` matches
  `ec.source` exactly against `kcatSources` (`strcmpi`). geckopy
  `classify_kcat_source` matches the part before ` (`. Unmatched sources
  fall into `unlabelled` and get the default prior width.
- **Standard kcats.** `getStandardKcat` (`strcmp`) and `removeStandardKcat`
  (`strcmpi`) find standard kcats by `ec.source == 'standard'`.
- **`sensitivityTuning`** skips its note when `ec.source` already reads
  `sensitivityTuning`.
- **`reviewKcatAssignment`** and the corrections report use the source to
  judge or describe a value.
- **People reading the model,** who take `ec.source` as the origin of the
  value.

### Behaviour today

- `sensitivityTuning` overwrites `ec.source` with `sensitivityTuning` and
  writes `preTuneKcat=...` to `ec.notes`.
- CMA-ES tuning leaves `ec.source` as it was.
- `assignKcatValues` writes `brenda` in MATLAB and
  `brenda (wc=0, origin=1)` in geckopy for the same match.

### Problems this causes

1. **A tuned kcat loses its prior group.** A kcat moved by
   `sensitivityTuning` and then tuned with CMA-ES falls into `unlabelled` and
   gets the default width instead of its evidence class's. Its prior is also
   centred on the already tuned value, so tuning compounds.
2. **The two tuning methods disagree.** After CMA-ES, a tuned value still
   reads `brenda`, so a reader cannot tell that it was fitted and may reuse it
   as a database value. After `sensitivityTuning`, the origin is gone.
3. **A tuned standard kcat is no longer recognised as standard.** If tuning
   wrote its own token, as `sensitivityTuning` does, `removeStandardKcat` and
   `getStandardKcat` would no longer find it.
4. **The two implementations disagree.** MATLAB and geckopy write
   different strings for the same match and match them differently.

### Three choices

- **a. Current value.** `ec.source` names the last step that wrote
  `ec.kcat`, tuning included (CMA-ES would write `cmaesTuning`). This keeps
  the label honest but loses the origin, which breaks problems 1 and 3 for
  every tuned kcat (up to 400 after CMA-ES).
- **b. Origin only.** Tuning never writes `ec.source`; the tuning status
  goes to the log and a note. This keeps the tools working, but the model
  alone misleads readers (problem 2), because notes are rarely read.
- **c. Origin plus status, in a fixed format** (decided):

```
<origin>[ (<detail>)][ | tuned=<method>[+<method>] (prior=<value>)]

brenda (wc=0, origin=2)
custom
brenda (wc=0, origin=2) | tuned=cmaes (prior=6.55)
okp_catapro (similarity=42) | tuned=sensitivity+cmaes (prior=5.48)
```

### Rule for every function

- **A step that replaces the value with new evidence or a rule sets the
  origin and clears any status:** `assign`, `custom`, `isozymes`,
  `standard`, `manual` (today `setKcatForReactions`).
- **A step that adjusts an existing value to fit data keeps the origin and
  adds or extends the status:** every tuning method. `prior` is the value
  before the first tuning.

### Arguments for choice c

- **Tools and readers.** It is the only choice where the model alone gives
  tools the origin (problems 1 and 3) and readers the fact that a value was
  fitted (problem 2).
- **No format change.** `prior` makes the pre-tuning value available without
  the log and without adding `ec` fields. Re-tuning can centre the prior on
  the evidence value, and tuning can be reset from the model alone.
- **One parser.** A single `parseKcatSource` / `parse_kcat_source`,
  identical on both sides, replaces the exact matching in MATLAB and the
  token matching in geckopy, which removes problem 4.

### Costs of choice c

- **Every reader of `ec.source` must use the parser:**
  - prior grouping on both sides;
  - `getStandardKcat` and `removeStandardKcat`;
  - `sensitivityTuning`;
  - `reviewKcatAssignment`;
  - the corrections report.
  Third-party code that compares `ec.source` with `brenda` already fails on
  models built with geckopy.
- **Migration of saved models:** `ec.source = sensitivityTuning` becomes
  `<origin> | tuned=sensitivity (prior=<value>)`, using the
  `preTuneKcat=...` note that `sensitivityTuning` wrote. `ec.notes` then
  holds only curation notes.
- **Detail fields per origin must be fixed:** `brenda` (`wc`, `origin`),
  predictors (`similarity`), `homologs` (`identity`), `combined` (`sd`).
  Isozyme and standard fills keep their own origin, which the adapter can
  give its own prior width.
