# Plan: behavioural parity for RAVEN ↔ raven-toolbox

The ledger carries **75 rows marked `parity`** — both sides implement this and are intended to
behave the same — and the repository holds **thirty-four raven-pair scenarios**, covering **43 of
those rows**.
Matching names prove nothing, as the README says. This is the plan to make the claim real, and
to keep it true nightly.

## What already exists

The scenarios, in the order they were written:

| Scenario | Covers | Verdict |
|---|---|---|
| `elemental_balance_smallyeast` | `getElementalBalance` | match |
| `homology_chain` | `getBlast`, `getModelFromHomology`, `makeFakeBlastStructure` | match |
| `gpr_dnf_rules` | `grRuleToDNF`, `isDnfGrRule` | match |
| `model_manipulation_smallyeast` | `convertToIrrev`, `expandModel`, `sortIdentifiers` | match |
| `yaml_roundtrip_smallyeast` | `readYAMLmodel`, `writeYAMLmodel` | **differs** — writer layout, see below |
| `task_list_parsing` | `parseTaskList` | match |
| `merge_models_smallyeast` | `mergeModels` | match |
| `task_checking_smallyeast` | `checkTasks` | **differs** — task LP set-up, see below |
| `gapfill_topology_smallyeast` | `gapFillTopological` | match |
| `init_scores_smallyeast` | `scoreComplexModel` | match |
| `init_merge_linear_smallyeast` | `mergeLinear`, `groupRxnScores` | match |
| `model_simplification_smallyeast` | `simplifyModel` | match |
| `merge_compartments_smallyeast` | `mergeCompartments` | match |
| `duplicate_reactions_smallyeast` | `findDuplicateRxns` | match |
| `gapfill_connect_smallyeast` | `fillGaps` | match |
| `copy_to_compartment_smallyeast` | `copyToComps` | match |
| `add_reactions_from_model_smallyeast` | `addRxnsGenesMets` | match |
| `add_reactions_from_equations_smallyeast` | `addRxns` | match |
| `add_transport_reactions_smallyeast` | `addTransport` | match |
| `remove_genes_smallyeast` | `removeGenes` | match |
| `remove_metabolites_smallyeast` | `removeMets` | match |
| `change_reaction_equations_smallyeast` | `changeRxns` | match |
| `change_gene_rules_smallyeast` | `changeGrRules` | match |
| `remove_low_score_genes_smallyeast` | `removeLowScoreGenes` | match |
| `set_variance_bounds_smallyeast` | `setParam` (var mode) | match |
| `diff_models_smallyeast` | `diffModels` | match |
| `compare_multiple_models_smallyeast` | `compareMultipleModels` | match |
| `check_model_struct_smallyeast` | `checkModelStruct` | match |
| `close_model_smallyeast` | `closeModel` | match |
| `apply_condition_smallyeast` | `applyCondition` | **differs** — reset_exchanges direction, see below |
| `assign_sbo_terms_smallyeast` | `assignSBOterms` | match |
| `standardize_gr_rules_smallyeast` | `standardizeGrRules` | match |
| `delta_g_csv_smallyeast` | `loadDeltaGCSV`, `saveDeltaGCSV` | match |
| `export_to_excel_smallyeast` | `exportToExcelFormat` | **differs** — default-bound hiding, see below |

And the machinery around them, which the plan builds on rather than around:

- `parity run` / `parity compare` — run a scenario against one implementation, diff two result
  documents within a declared tolerance.
- `.github/workflows/nightly.yml` — checks out both repos, installs MATLAB through
  `matlab-actions/setup-matlab` (licence-free for public repositories), runs every scenario on
  both sides and compares. **MATLAB in CI is already solved.**
- `parity.local.toml` — per-machine path overrides, so a local run can point at any checkout.
- Ledger rows already cross-reference the scenarios that cover them.

What is missing is scenarios, and a runner that watches all four repos on the branches the
ledger actually tracks.

## Two corrections from this round

**Run the aligners; do not pin their output.** Both toolboxes execute the *same* binaries:
RAVEN ships them in `software/`, and raven-toolbox fetches the same builds — BLAST+ 2.17.0,
DIAMOND 2.1.17, HMMER 3.4.0 — from the **raven-data** release assets. Identical binaries on
identical inputs give identical hits, so the end-to-end route is deterministic and worth
testing directly. Confirmed: the `homology_chain` BLAST checkpoint matches exactly.

One caveat to respect: on **Windows** raven-toolbox ships HMMER **3.3.2** (no native Windows
3.4 exists) against RAVEN's 3.4. The formats are compatible, but "same binary" only strictly
holds on Linux and macOS — so aligner scenarios run on Linux, where the claim is exact.

**Test the intermediate stages as well as the result.** A whole-pipeline diff says the models
differ but never where. The chains below emit *checkpoints*: one run per implementation,
several named stages inside the result document. `parity compare` already walks results
structurally, so per-stage differences fall out of a single run — and the first stage that
diverges is the one to fix.

## The scenario programme

### Reconstruction from homology

One run per side, four checkpoints:

| Checkpoint | Covers | Compares |
|---|---|---|
| `blast` | `getBlast` / `run_blast` | hit table: query, target, e-value, identity, alignment length, bitscore |
| `orthologs` | (internal to both) | the ortholog map after cutoffs and bidirectional filtering |
| `model` | `getModelFromHomology` / `get_model_from_homology` | reaction ids, gene ids, GPRs as logic, stoichiometry, bounds |
| ~~`exchange`~~ | `addRxnsGenesMets` / `add_reactions_from_model` | **done**, as its own scenario rather than a checkpoint here: `add_reactions_from_model_smallyeast` |

Inputs: two small proteomes and a template model from the RAVEN repo, so both sides read the
same bytes.

### Reconstruction from KEGG

| Checkpoint | Covers | Compares |
|---|---|---|
| `hmmsearch` | `run_hmmsearch` and RAVEN's equivalent | per-KO hits and scores |
| `ko_assignment` | `assign_kos` | KO → gene assignment after cutoffs |
| `reactions` | reaction selection from KOs | reaction id set |
| `model` | `getKEGGModelForOrganism` / `get_kegg_model_for_organism` | reactions, genes, GPRs, compartments |

Pin the KEGG artefact version in the scenario declaration: a different HMM library is a
different question.

### ftINIT, stage by stage

The five stages fail in different ways and need different fixes, so each is a checkpoint:

| Checkpoint | Covers | Tier |
|---|---|---|
| ~~`scores`~~ | `scoreComplexModel` / `score_reactions_from_genes` | **done** — `init_scores_smallyeast` |
| `prep` | `prepINITModel` / `prep_init_model` | exact (prepared sets, task-essential reactions) |
| ~~`merge_linear`~~ | `mergeLinear` / `merge_linear` | **done** — `init_merge_linear_smallyeast` |
| `steps` | `ftINITInternalAlg`, `getINITSteps` / `run_ftinit`, `get_init_steps` | set-level per step |
| `model` | `ftINIT` / `ftinit` | set-level |
| `taskfill` | `ftINITFillGapsForAllTasks` / `fill_tasks` | set-level |

A divergence in `scores` explains everything downstream; a divergence that appears only at
`steps` is the MILP. Without the split the two are indistinguishable.

### Compartment assignment

**Needs a feature diff before a scenario.** Both sides carry the name, but the Python one has
grown certification, gap-fill coupling and flux-gated multi-localisation, and work may have
landed on either side since the port. A scenario written first would measure the gap between
two different algorithms and call it a parity failure. Diff what each does, record it on the
ledger row, *then* write checkpoints for `scores` → `placement` → `certification` → `model`.

`predictLocalization` is a declared divergence, not a parity target: MATLAB anneals, Python
solves a MILP.

### Cheap deterministic scenarios worth having anyway

Each is seconds to run and pins a `parity` row that would otherwise be unverified.

Done: GPR normalisation (`gpr_dnf_rules`), `convertToIrrev` / `expandModel` / `sortIdentifiers`
(`model_manipulation_smallyeast`), YAML round-trip (`yaml_roundtrip_smallyeast`). All three are
solver-free and run in seconds on RAVEN's smallYeast tutorial model, which both sides read out
of the RAVEN checkout so the fixture cannot drift.

Still to write, and what each one needs first:

`fillGaps` is done too (`gapfill_connect_smallyeast`), and it settles the MILP question the table
used to raise: on a fixture where the template is the draft plus exactly the removed reactions the
minimum repair is unique, so the chosen set is safe to compare, and SCIP against Gurobi agreed on it.
A fixture offering two ways to repair the same gap would still need the comparison moved to the size
of the repair.

| Candidate | Needs |
|---|---|
| `getPhylDist` | a pinned KEGG artefact; it belongs with the KEGG chain |
| `sortModel` | nothing — it is a `subsumed` row, so there is no Python entry point to compare it against |
| biomass scaling | a model whose biomass reaction is worth scaling; smallYeast's is not |

`checkTasks` and `mergeModels` are done. The id-collision convention was checked first, as this table
used to require: both sides rename a clash to `<id>_<source model id>`, and used to part company on a
*second* collision of the same id --- fixed in RAVEN#718 (raven-gecko-parity#68).

### Divergences to encode, not fix

Found while building raven-toolbox's own checks; each is real and currently invisible:

| Pair | Difference |
|---|---|
| `contractModel` / `remove_duplicate_reactions` | **measured, raven-gecko-parity#8**: expand-then-contract is a round trip in RAVEN (first member survives, `_EXP_N` stripped, `grRules` merged with `or`) and lossy in raven-toolbox (last member survives, keeps its expanded id and its own rule). They also disagree on whether bounds have to match for two reactions to count as duplicates. *Detection* is a separate function on both sides and is at parity |
| `reporterMetabolites` / `reporter_metabolites` | one-sided p-value, z-sorted vs two-tailed ordering |
| `FSEOF` / `fseof` | slope of \|flux\| vs endpoint comparison |
| `predictLocalization` / `predict_localization` | simulated annealing vs MILP |

A scenario should *assert* each difference, so a silent change to either side fails.

### Divergences the scenarios found

Sixteen so far. Four are asserted and currently red (`yaml_roundtrip_smallyeast`,
`task_checking_smallyeast`, `apply_condition_smallyeast`, `export_to_excel_smallyeast`); the rest
are recorded on their ledger rows because no fixture here reaches them, or because the scenario
that does exist works around the divergence rather than asserting it.

**`writeYAMLmodel` / `write_yaml_model` do not write the same file.** The *content* is at
parity — the two readers produce the same model, and a read-write-read round trip is lossless
on either side — but the layout is not, so the byte-stability `writeYAMLmodel.m` claims in its
own docstring does not hold. MATLAB reproduces the historical RAVEN layout (4-space sequence
indent, long scalars inline in double quotes) and emits an empty `version:` line into
`metaData`; the Python side dumps through cobra's ruamel instance at its defaults (2-space
indent, scalars folded at 80 columns) and quotes the date. On smallYeast that is 1415 lines
against 1571 — and MATLAB's output is within 107 lines of the input file, where Python's
differs on essentially all of it. **Open question: which layout is the target?** Deciding that
is a prerequisite to the scenario going green; until then `yaml_roundtrip_smallyeast` is the
one red scenario, deliberately.

Following that up turned out to matter more than the layout does:
[docs/yaml-reconciliation.md](yaml-reconciliation.md) takes it apart and finds that
`readYAMLmodel` cannot read a file written by *any* cobrapy-based tool --- it raises on ruamel's
folded scalars, keeps single quotes, and has a latent bug where a list-valued `ec-code` swallows
the rest of the annotation block. The report carries the reproducers and a tiered plan; the
short version is that the reader fixes belong in RAVEN and are needed whatever is decided about
the writers, and that the writer layout is cheapest to settle on the Python side.

**`changeGrRules` leaves an unparseable grRule behind when appending onto a reaction with no GPR yet
(raven-gecko-parity#12).** It unconditionally builds `"(old) or (new)"`, so on an empty `old` that is the
literal string `"() or (new)"` — not a valid gene, complex or isozyme. It does not raise: `rxnGeneMat` comes
out correctly populated, but the *text* is left broken, and anything that re-parses it later —
`grRuleToDNF`, `isDnfGrRule`, `expandModel` — throws `RAVEN:badGrRule` far from the call that caused it.
`change_gene_reaction_rules` explicitly guards this case. `change_gene_rules_smallyeast` covers the two paths
that do agree (replace outright; append onto an existing GPR) and does not assert this one.

**A metabolite created by rewriting a reaction's equation is nameless on the Python side, same as
`addRxns` / `add_reactions_from_equations` (raven-gecko-parity#9).** `changeRxns` and
`change_reaction_equations` share the same metabolite-matching machinery those two do, so the same gap
shows up here rather than being a separate bug. Not re-filed; `change_reaction_equations_smallyeast`
creates a metabolite as part of its fixture and does not compare its name, pointing at #9 instead.

**`compareMultipleModels`'s similarity statistic is not `compare_models`'s.** RAVEN's `structComp` is
`(1 - Hamming distance)`, counting "both models lack this reaction" as agreement; `compare_models`'s is
Jaccard, counting only shared presence. Two models that mostly agree by both lacking most of a big
universal reaction set score high on one, low on the other. RAVEN also has no metabolite/gene presence
matrix at all (reaction-space only, by its own docstring) and reads only a reaction's first subsystem
where Python joins every one with `;`. `compare_multiple_models_smallyeast` cross-validates the one thing
that does line up — the reaction presence matrix, on three models covering every presence pattern.

**`removeMets`'s cleanup flags have no Python counterpart, and cobra's `destructive` is not a
substitute for them.** RAVEN never deletes a reaction just because a metabolite it needed is gone —
`removeUnusedRxns=true` only prunes one left with literally zero metabolites. `remove_metabolites`
offers only cobra's `destructive`, which deletes every reaction touching the removed metabolite
outright, whatever else that reaction still has — a much more aggressive removal, not the same
behaviour under another name. `remove_metabolites_smallyeast` runs both sides at their shared
non-destructive default, where they agree exactly, including a reaction reduced to zero metabolites
and left in the model on both sides rather than pruned.

**`removeGenes` and `remove_genes` default to different policies for a reaction a deletion
blocks.** RAVEN's `removeBlockedRxns=false` (its default) matches the Python side's
`blocked_reactions="constrain"`, not its own default (`"remove"`) — so comparing each side's own
default would compare bounding a reaction to (0, 0) against deleting it outright and call the
difference parity. `remove_genes_smallyeast` names the policy explicitly on both sides instead. Python
also has a third, one-sided policy (`"keep"`) with no RAVEN equivalent.

**`addTransport` crashes on its own natural default call.** Asked to transport every metabolite from
one compartment when not all of them exist in the target, it builds the new reaction names from the full
requested list and the reactions themselves from the filtered subset, then concatenates arrays of two
different lengths. Not a Python-side difference — a latent bug, reproducible on RAVEN's own tutorial
model. Filed as raven-gecko-parity#10; `add_transport_reactions_smallyeast` uses an explicit metabolite
subset to avoid it and has no coverage of the default path until it is fixed.

**A metabolite created from an equation comes out nameless on the Python side.** `addRxns` sets its
`metNames` to the id; `add_reactions_from_equations` leaves the name empty. Tracked as
raven-gecko-parity#9, and worth more than its size suggests: a nameless metabolite defeats the
name-keyed matching that `merge_compartments` and `add_reactions_from_model` both depend on.

**The two name compartment copies differently, in both directions.** `copyToComps` appends the
target compartment to the id a metabolite already has (`ADP_c` → `ADP_c_p`) where
`copy_to_compartment` rewrites the suffix (`ADP_p`); `mergeCompartments` keeps the first copy's id
where `merge_compartments` rewrites it to the merged compartment. Both scenarios compare metabolites
as (name, compartment) as a result, which leaves everything else about the transform under test.

**`mergeCompartments` renames merged metabolites on one side and not the other**, reserves
pre-existing single-metabolite reactions on one side and not the other, and returns something other
than what its docstring describes. All three are on the ledger row; the scenario compares by species
name and runs with `deleteRxnsWithOneMet` off, which leaves the merge itself — grouping, coefficient
summing, cancellation — comparable and matching.

**`simplifyModel`'s dead-end pass consults the bounds on one side and not the other.** RAVEN reads
dead ends off the sign pattern of S, with reversible reactions counted in both directions; the Python
side additionally consults the bounds, so a reaction locked at zero flux does not count as a producer.
Run alone against smallYeast, whose exchanges ship shut, the Python pass removes 5 reactions where
RAVEN removes none (21 against 2 on a stranded model). Composed after `deleteZeroInterval` — the order
RAVEN documents and ftINIT uses — the two agree exactly, so this is a precondition rather than a
disagreement about the pass, and `model_simplification_smallyeast` compares the composed form.
Recorded on the ledger row.

**`checkTasks` and `check_tasks` build a different LP.** RAVEN relaxes the metabolite balance
(`model.b`) for a task's declared inputs and outputs and leaves the model's own reactions alone; the
Python side closes the model's boundary reactions and works through exchange reactions. A metabolite
the model can already excrete through its own open exchange therefore stays available to a RAVEN task
that does not list it. On smallYeast that flips one of six task verdicts. Tracked as
raven-gecko-parity#7, asserted by `task_checking_smallyeast`, and the second scenario that is red on
purpose. It matters beyond `checkTasks`: this is the task layer under ftINIT, `fitTasks` and
`ftINITFillGapsForAllTasks`, so the ftINIT chain should not be written until it is settled.

**`gapFillTopological` and `analyse_topology` default their seeds and targets differently.** RAVEN
seeds from every exchange reaction whose bounds allow uptake and targets the substrates of the
objective reaction; the Python side seeds from one-metabolite reactions with `lower_bound < 0` and
targets every metabolite in the model. `gapfill_topology_smallyeast` passes both explicitly, since a
scenario on the defaults would measure the defaults rather than the traversal. Recorded on the ledger
row.

**The two GPR parsers accept different syntax.** RAVEN's tokeniser takes `&&`, `||` and
mixed-case operators (`Or`); cobra's parser takes only `&`, `|` and fully uppercase `AND`/`OR`,
and anything else warns and yields an *empty* GPR — so the reaction loses its genes silently
rather than raising. `gpr_dnf_rules` covers the syntax both accept and leaves those spellings
out on purpose: they are a difference in accepted input, not in behaviour, and asserting them
would leave the scenario permanently red over a triviality.

**`applyCondition` and `apply_condition` disagree about what a condition's exchange-reset
direction means (raven-gecko-parity#15).** `applyCondition` forwards `prelude.reset_exchanges`
straight through to `getExchangeRxns` as a direction filter — `"out"` resets only the reactions
where the boundary metabolite is a product, leaving every other exchange, including uptakes,
untouched. `apply_condition` cannot make this distinction at all (cobra has no concept of
RAVEN's in/out split) and resets every exchange it finds for any truthy value, whatever
direction was actually named. On smallYeast (three uptake reactions shipped shut), applying the
identical condition takes maximum growth from unreachable on the RAVEN side to ~90 on the
Python side — glucose and oxygen uptake silently reopened, neither of which the condition
named. Not a toy case: `applyCondition`'s own docstring names yeast-GEM as its first consumer
and uses `"out"`, not a bare boolean, as its own worked example — exactly the shape of condition
a real yeast-GEM file plausibly writes. `apply_condition_smallyeast` asserts the split directly
and is the third deliberately red scenario.

**`exportToExcelFormat` hides a bound that equals the model's own declared default;
`export_to_excel` always writes it literally (raven-gecko-parity#17).** The two are a faithful,
deliberate port on layout — same sheets, same headers, same column order, even RAVEN's own
unusual "RXNS' ID column is the real id but METS' ID column is name[comp]" convention reproduced
exactly. `exportToExcelFormat` hides a LOWER BOUND / UPPER BOUND cell when it equals
`model.annotation.defaultLB`/`defaultUB`, and separately hides an irreversible reaction's lower
bound whenever it is exactly 0; `export_to_excel` has no equivalent logic and always writes the
literal bound. Not a corner case: smallYeast's bounds are drawn entirely from `{-1000, 0, 1000}`
(its own declared defaults plus zero), so nearly every reaction's bound cells hit one of RAVEN's
hiding rules — of five reactions tested, three come back fully blank from RAVEN and fully
populated from raven-toolbox, and the other two agree only on the one bound that happens to
differ from the default. `export_to_excel_smallyeast` asserts the split directly and is the fourth
deliberately red scenario.

## How it runs

### Nightly, across all four repos, only when something moved

`nightly.yml` runs at 05:00 daily for the **raven pair**, and:

1. **Skips when nothing moved.** `nightly/state.json` holds the revisions of the last real
   comparison; the job resolves both tracked branches with `git ls-remote` and stops there if
   the pair is unchanged. `workflow_dispatch` takes a `force` input for when you want the run
   anyway.
2. **Uses the branches the ledger tracks.** Both workflows get them from `parity refs`, which
   reads `parity.toml`. Not one of the four repos defaults to its integration branch: RAVEN
   and GECKO both default to `main` while the ledgers describe `develop3` and `develop4`, so
   taking defaults compared release branches against development ones.
3. **Writes a report, not just a red tick.** `nightly/report.md` is regenerated and committed
   each time the comparison actually runs, so drift has a history.
4. **Distinguishes a crash from agreement.** A scenario whose result file is missing is
   recorded as `ERROR`, never as a match, and the job goes red. One scenario failing does not
   stop the others.
5. **Gurobi for the solver scenarios** — `task_checking_smallyeast` (LP) and
   `gapfill_connect_smallyeast` (MILP) both name it explicitly on both sides rather than
   inheriting a preference, so a difference cannot be blamed on the solver. The consequence is
   that those two, alone among the raven scenarios, do not run without a licence. The licence
   comes either from the organisation secret
   `GUROBI_EDUARD`, which holds a licence file verbatim, or from the three-field
   `GUROBI_WLSACCESSID` / `GUROBI_WLSSECRET` / `GUROBI_LICENSEID` form that raven-toolbox
   uses. Both are accepted; when neither is configured the job says so and carries on, so
   solver-free scenarios still run. Only a **WLS** licence works on a hosted runner --- a
   named-user academic licence is tied to one machine --- so the step says which kind it
   found.

Done: the **gecko pair** joined the nightly as a second matrix entry --- see
[gecko-behaviour-parity-plan.md](gecko-behaviour-parity-plan.md) for its own scenarios. Its
entry checks out all four repos, because geckopy installs raven-toolbox from git and would
otherwise be compared against a revision the run never recorded; RAVEN and raven-toolbox are
resolved unconditionally in both entries so the gecko one can depend on them, and each pair
writes its own `nightly/*state.json` / `nightly/*report.md` so a push from one entry cannot
race a push from the other --- the matrix runs one entry at a time for the same reason.

### On demand, on any branch, locally

The same comparison must be runnable against work in progress — that is what makes it useful
before a merge rather than after:

```bash
parity run ftinit_smallmodel --impl python --python-ref feat/my-branch
parity run ftinit_smallmodel --impl matlab --matlab-ref fix/their-branch
parity compare results/python/... results/matlab/... --scenario ftinit_smallmodel
```

Two ways to reach that, and the choice is worth making deliberately: resolve refs by checking
out a git worktree per ref (isolated, no effect on the user's checkout, needs disk), or keep
using `parity.local.toml` paths and let the user switch branches themselves (simplest, but
silently compares whatever happens to be checked out). The worktree route is the one that
makes a result reproducible from the command alone; every result document should record the
four commit shas it came from either way.

A `parity verify` wrapper that runs both sides and compares in one command would make the
local path a single step instead of three.

## Order of work

1. ~~**Homology chain** — deterministic, shared binaries, seconds to run, covers half of one
   reconstruction route. Proves the checkpoint pattern.~~ Done; two of its four checkpoints
   (`blast`, `draft`) are in, `orthologs` and `exchange` are not.
2. ~~**Fix the runner**: explicit refs (RAVEN `develop3`), nightly, change detection, report
   on difference.~~ Done; the gecko pair still needs scenarios before it can join.
3. ~~**The cheap deterministic scenarios**, in a batch — they are mostly declaration plus a
   dozen lines each.~~ Done: `gpr_dnf_rules`, `model_manipulation_smallyeast`,
   `yaml_roundtrip_smallyeast`, `task_list_parsing`, `merge_models_smallyeast` and
   `task_checking_smallyeast`. Only `fillGaps` and the two that need a decision or an artefact
   are left — see the table above.
4. **ftINIT chain**, stage by stage. Started: the `scores` checkpoint is in
   (`init_scores_smallyeast`) and matches, so a divergence appearing further down the chain is
   not coming from the scoring. The stages that follow are **blocked on raven-gecko-parity#7**
   from `prep` onwards: ftINIT's task layer runs through `checkTasks`, and until the two agree
   on what a task constrains, a difference in an ftINIT model cannot be attributed to ftINIT.
   `merge_linear` was the one later checkpoint that touches no tasks, and it is now done
   (`init_merge_linear_smallyeast`, which covers `groupRxnScores` alongside it). The gene-pruning step
   at the far end of ftINIT is also task-free and is now done too (`removeLowScoreGenes` /
   `remove_low_score_genes_smallyeast`). Everything still outstanding in between runs through the task
   layer.
5. **Encode the four known divergences.**
6. **KEGG chain** (needs an artefact version pinned and a small proteome).
7. **Compartment-assignment feature diff**, then its chain.
8. **Branch-targeted local runs** (`--python-ref` / `--matlab-ref`, or documented worktree
   workflow) — do this as soon as step 1 proves the pattern, since it is what makes the tool
   usable day to day.

## Open questions

- **Which branch is RAVEN's parity target** — `develop3` (what the ledger and docs track) or
  `main`? Everything downstream depends on the answer, and today the two runners disagree.
- **Which YAML layout is the target** — RAVEN's historical one, which `writeYAMLmodel`
  reproduces and the tutorial fixtures are written in, or cobra's ruamel defaults, which
  `write_yaml_model` emits? `yaml_roundtrip_smallyeast` is red until this is answered, and it
  is the only scenario in the repository that is.
  See [docs/yaml-reconciliation.md](yaml-reconciliation.md) for the evidence and a
  recommendation --- in short: the Python side moves, and neither writer matches the
  yeast-GEM / Human-GEM corpus today.
  Tracked as raven-gecko-parity#6.
- **Where do MATLAB results live between runs?** Committing them gives CI something to compare
  against without MATLAB and gives drift a history; it also means a stale committed result can
  quietly become the reference. Recording the RAVEN sha in the result and warning on mismatch
  covers that.
- **Does the ledger need a `divergence` status?** The four known differences are neither
  `parity` nor `matlab-only`, and today fit only in `notes`, which nothing validates.
- **How large should the fixtures be?** Small enough for a nightly, large enough that a
  divergence has somewhere to hide. The genome-scale comparison behind the published Jaccard
  figures is ~1 h per side and belongs in a separate, slower job.
