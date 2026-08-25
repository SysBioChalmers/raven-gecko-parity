# Plan: behavioural parity for RAVEN ↔ raven-toolbox

The ledger carries **73 rows marked `parity`** — both sides implement this and are intended to
behave the same — and the repository holds **one scenario**. Matching names prove nothing, as
the README says. This is the plan to make the claim real, and to keep it true nightly.

## What already exists

More than the single scenario suggests, and the plan builds on it rather than around it:

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
| `exchange` | `addRxnsGenesMets` / `add_reactions_from_model` | reactions transferred from the template |

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
| `scores` | `scoreComplexModel` / `score_reactions_from_genes` | exact (numeric tolerance) |
| `prep` | `prepINITModel` / `prep_init_model` | exact (prepared sets, task-essential reactions) |
| `merge_linear` | `mergeLinear` / `merge_linear` | exact (group ids, reversed reactions) |
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

`checkTasks`, `mergeModels`, `convertToIrrev`, `expandModel`, `sortModel`, `getPhylDist`, GPR
normalisation, YAML round-trip, `fillGaps`, biomass scaling. Each is seconds to run and pins a
`parity` row that is currently unverified.

### Divergences to encode, not fix

Found while building raven-toolbox's own checks; each is real and currently invisible:

| Pair | Difference |
|---|---|
| `contractModel` / `remove_duplicate_reactions` | MATLAB merges duplicates' `grRules` with `or`; Python drops the others' gene associations |
| `reporterMetabolites` / `reporter_metabolites` | one-sided p-value, z-sorted vs two-tailed ordering |
| `FSEOF` / `fseof` | slope of \|flux\| vs endpoint comparison |
| `predictLocalization` / `predict_localization` | simulated annealing vs MILP |

A scenario should *assert* each difference, so a silent change to either side fails.

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
5. **Gurobi for the MILP scenarios** — the licence comes either from the organisation secret
   `GUROBI_EDUARD`, which holds a licence file verbatim, or from the three-field
   `GUROBI_WLSACCESSID` / `GUROBI_WLSSECRET` / `GUROBI_LICENSEID` form that raven-toolbox
   uses. Both are accepted; when neither is configured the job says so and carries on, so
   solver-free scenarios still run. Only a **WLS** licence works on a hosted runner --- a
   named-user academic licence is tied to one machine --- so the step says which kind it
   found.

Still open: extend it to the **gecko pair**, which needs geckopy and GECKO scenarios first.

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

1. **Homology chain** — deterministic, shared binaries, seconds to run, covers half of one
   reconstruction route. Proves the checkpoint pattern.
2. ~~**Fix the runner**: explicit refs (RAVEN `develop3`), nightly, change detection, report
   on difference.~~ Done; the gecko pair still needs scenarios before it can join.
3. **The cheap deterministic scenarios**, in a batch — they are mostly declaration plus a
   dozen lines each.
4. **ftINIT chain**, stage by stage.
5. **Encode the four known divergences.**
6. **KEGG chain** (needs an artefact version pinned and a small proteome).
7. **Compartment-assignment feature diff**, then its chain.
8. **Branch-targeted local runs** (`--python-ref` / `--matlab-ref`, or documented worktree
   workflow) — do this as soon as step 1 proves the pattern, since it is what makes the tool
   usable day to day.

## Open questions

- **Which branch is RAVEN's parity target** — `develop3` (what the ledger and docs track) or
  `main`? Everything downstream depends on the answer, and today the two runners disagree.
- **Where do MATLAB results live between runs?** Committing them gives CI something to compare
  against without MATLAB and gives drift a history; it also means a stale committed result can
  quietly become the reference. Recording the RAVEN sha in the result and warning on mismatch
  covers that.
- **Does the ledger need a `divergence` status?** The four known differences are neither
  `parity` nor `matlab-only`, and today fit only in `notes`, which nothing validates.
- **How large should the fixtures be?** Small enough for a nightly, large enough that a
  divergence has somewhere to hide. The genome-scale comparison behind the published Jaccard
  figures is ~1 h per side and belongs in a separate, slower job.
