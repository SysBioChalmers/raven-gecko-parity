# raven-gecko-parity

Keeps the MATLAB and Python implementations of RAVEN and GECKO honest about their differences.

| MATLAB | Python | Ledger |
|---|---|---|
| [SysBioChalmers/RAVEN](https://github.com/SysBioChalmers/RAVEN) | [SysBioChalmers/raven-toolbox](https://github.com/SysBioChalmers/raven-toolbox) | [`ledgers/raven.yml`](ledgers/raven.yml) |
| [SysBioChalmers/GECKO](https://github.com/SysBioChalmers/GECKO) | [SysBioChalmers/geckopy](https://github.com/SysBioChalmers/geckopy) | [`ledgers/gecko.yml`](ledgers/gecko.yml) |

Development happens mostly on the Python side; MATLAB should keep up, except where a
difference is deliberate. That policy only works if "deliberate" is written down somewhere a
machine can read, and if drifting away from it is noisy rather than silent.

## The three questions this answers

**Does every public function have a declared status?** `parity check` scans both repos and
validates them against the ledger. A new `.m` file, or a new name in a Python `__all__`, that
nobody has classified is a build failure. So is a ledger row naming a function that has since
been renamed away.

**I just changed this --- what does the other side owe?** `parity mirror` maps the files you
touched back through the ledger to the sibling functions that now need attention. Wired into
a git hook, it asks the question at the moment you would otherwise forget it.

**Do both implementations still produce the same numbers?** `parity run` / `parity compare`
execute a scenario against each implementation and diff the results within a declared
tolerance. Matching function names prove nothing on their own.

## Quick start

```bash
pip install -e ".[dev]"
```

Tell it where your checkouts are --- the defaults assume all four sit side by side, as in
`C:\Work\GitHub\`. Override per machine in `parity.local.toml` (gitignored):

```toml
[pairs.raven.matlab]
path = "D:/checkouts/RAVEN"
```

Then:

```bash
parity check                      # validate both ledgers against both repos
parity report -o build/           # render the human-readable parity documents
parity sync                       # add rows for anything newly public
```

## The ledger

One row per public function on either side, each carrying a status:

| Status | Meaning |
|---|---|
| `parity` | Both sides implement this and are intended to behave the same. |
| `python-pending` | MATLAB has it; a Python port is queued. |
| `matlab-pending` | Python has it; a MATLAB back-port is queued. |
| `matlab-only` | Deliberately MATLAB-only. Needs a `reason`. |
| `python-only` | Deliberately Python-only. Needs a `reason`. |
| `via-dependency` | The other side gets this from cobrapy or the COBRA Toolbox. Needs a `reason`. |
| `subsumed` | The other side has the capability inside another function, not as its own entry point. Needs a `reason`. |
| `internal` | Not part of the cross-implementation API --- glue, installers, helpers. Needs a `reason`. |
| `unreviewed` | Not yet triaged. Drive this to zero. |

```yaml
- matlab: getElementalBalance
  python: raven_toolbox.utils.get_elemental_balance
  status: parity
  scenarios:
    - elemental_balance_smallyeast

- python: raven_toolbox.gapfilling.fill_gaps_weighted
  status: matlab-pending
  issue: SysBioChalmers/RAVEN#123

- matlab: runDynamicFBA
  status: matlab-only
  reason: Maintained Python packages already cover dynamic FBA (dfba, reframed, mewpy).
```

The `matlab-pending` and `python-pending` rows *are* the back-port queue. The `matlab-only`,
`python-only`, `via-dependency` and `subsumed` rows *are* the divergence register. Neither
needs to be maintained separately, and `parity report` renders both.

## Local mirroring

Rather than a cross-repo bot, the mirror check runs on your machine at the two moments it
matters:

```bash
python hooks/install.py
```

That installs an advisory `post-commit` hook (what did that commit imply?) and a `pre-push`
hook (what does this branch owe before it becomes a PR?) into all four repos. Neither blocks;
set `PARITY_STRICT=1` to make `pre-push` refuse a branch that touches a function declared at
parity.

You can also ask directly, from inside any of the four repos:

```bash
parity mirror --since develop..HEAD
```

## Scenarios

A scenario is a directory under `scenarios/` holding a declaration, a Python entry point and
a MATLAB one:

```
scenarios/elemental_balance_smallyeast/
    scenario.yml                        # inputs, tolerance, which ledger rows it covers
    run.py                              # def run(ctx) -> dict
    elemental_balance_smallyeast.m      # function results = <id>(ctx)
```

Both sides get the same inputs and return the same shape; `parity compare` diffs them.

```bash
parity run elemental_balance_smallyeast --impl python
parity run elemental_balance_smallyeast --impl matlab
parity compare results/python/elemental_balance_smallyeast.json \
               results/matlab/elemental_balance_smallyeast.json \
               --scenario elemental_balance_smallyeast
```

Scenarios are for the places where the numbers matter --- ftINIT, gap-filling, localization,
kcat matching, protein pool limits. Do not try to cover everything, and do not diff MATLAB
against Python at line level.

Thirty-four cover the raven pair today, over forty-three `parity` rows; `parity scenarios` lists
them with what each one claims to cover. Thirty agree. Four report a difference on purpose, each with an open question
behind it: `yaml_roundtrip_smallyeast` (the two YAML writers preserve the same model but do not
produce the same file), `task_checking_smallyeast` (the two build a different LP for a
metabolic task, so one of six task verdicts flips), `apply_condition_smallyeast` (a
condition's exchange-reset direction is honoured by RAVEN and ignored by raven-toolbox, which
resets every exchange regardless), and `export_to_excel_smallyeast` (RAVEN leaves a bound blank in
its Excel export when it matches the model's own default; raven-toolbox always writes it
literally). See [docs/behaviour-parity-plan.md](docs/behaviour-parity-plan.md) for both and for
what is queued next.

Thirteen cover the gecko pair, over forty-five of its `parity` rows, all on GECKO's own
unit-test model. Eleven agree on content: `ec_model_expansion_ectestgem`,
`enzyme_annotation_ectestgem`, `protein_pool_ectestgem`, `ec_model_io_ectestgem`,
`model_edits_ectestgem`, `kcat_chain_ectestgem`, `okp_kcat_ectestgem`, `enzyme_usage_ectestgem`,
`ec_fva_ectestgem`, `flexibilize_concs_ectestgem` and `sensitivity_tuning_ectestgem` ---
the whole solver tier (Tier 3 of the gecko plan) is now done. Several were blocked until
recently by real GECKO bugs the scenarios themselves found: GECKO `develop4`
called RAVEN's `progressbar`, which RAVEN `develop3` had replaced with `progressReport`
([GECKO#424](https://github.com/SysBioChalmers/GECKO/issues/424), fixed by
[GECKO#425](https://github.com/SysBioChalmers/GECKO/pull/425), merged); `addNewRxnsToEC`
crashed whenever more than one new reaction in a call needed isozyme expansion
([GECKO#427](https://github.com/SysBioChalmers/GECKO/pull/427), merged); `kcat_chain_ectestgem`
found four more --- `writeDLKcatInput` silently wrote zero rows for any non-trivial reaction
subset, the ordinary, documented way to call it
([GECKO#428](https://github.com/SysBioChalmers/GECKO/pull/428), merged);
`TestGEMAdapter`'s spontaneous-reaction detection was broken twice over, first by an undefined
variable and then, once that was fixed, by a hardcoded position that didn't survive the
reaction being renumbered by ecModel expansion
([GECKO#429](https://github.com/SysBioChalmers/GECKO/pull/429), merged); and two enzyme rows
sharing a `prot_<accession>` metabolite overwrote instead of summed in `applyKcatConstraints`
([GECKO#430](https://github.com/SysBioChalmers/GECKO/issues/430), fixed by
[GECKO#431](https://github.com/SysBioChalmers/GECKO/pull/431), merged); and `enzyme_usage_ectestgem`
found a fifth --- `reportEnzymeUsage`'s default `topAbsUsage` (10) indexed past the end of any
model with fewer enzymes than that, ecTestGEM included
([GECKO#432](https://github.com/SysBioChalmers/GECKO/pull/432), merged); and
`sensitivity_tuning_ectestgem` found a sixth --- `sigmaFitter`'s 100-point grid-search loop
reassigns the model on every iteration and never re-applies the best-fitting sigma
afterward, so it returned a model sized for whichever sigma was tried last, not the one it
reported
([GECKO#433](https://github.com/SysBioChalmers/GECKO/pull/433), merged); and `okp_kcat_ectestgem`
found a seventh --- `writeOpenKineticsPredictorInput` indexed its enzyme-coupling matrix by
position within the caller's requested reaction subset instead of the matrix's own absolute
indexing, so any subset skipping an earlier reaction silently dropped a later one's enzyme and
duplicated an earlier one's instead --- the same family of bug as `writeDLKcatInput`'s own, above
([GECKO#437](https://github.com/SysBioChalmers/GECKO/pull/437), merged). `okp_kcat_ectestgem` also
started from a ledger-audit finding: `writeOpenKineticsPredictorInput` and
`readOpenKineticsPredictorOutput` were filed as having no Python counterpart at all, while their
real counterparts (`build_okp_input_csv`, `parse_okp_output`) sat separately filed the same way
--- four ledger rows each independently claiming isolation from the very function its own reason
text named. See [docs/gecko-behaviour-parity-plan.md](docs/gecko-behaviour-parity-plan.md) for
all seven bugs and the ledger correction.
`model_edits_ectestgem` also confirmed four smaller, already-documented API-shape
divergences on its other four functions --- case-sensitivity, an unknown-id lookup that raises
instead of returning empty, a kcat-source string, and whether overwriting with an empty value
clobbers an existing one --- `kcat_chain_ectestgem` confirmed three more: MATLAB's
`applyCustomKcats` leaves a reaction's source/notes untouched when it's identified by reaction
id alone, where geckopy always overwrites them; `selectKcatValue`'s `criteria='median'`/`'mean'`
is dead code in MATLAB (a two-output call `median`/`mean` don't support, confirmed to error
unconditionally); and `applyKcatConstraints`'s light formulation silently zeroes a reaction's
enzyme cost when only some of its isozymes have a kcat, rather than using the one that does ---
and `enzyme_usage_ectestgem` confirmed one more: `reportEnzymeUsage`'s `topAbsUsage` table
always pads to the requested row count with a placeholder for any enzyme that carries no flux,
where `report_enzyme_usage`'s equivalent table just leaves that enzyme out, so the two can
return a different number of rows for the same request
([raven-gecko-parity#18](https://github.com/SysBioChalmers/raven-gecko-parity/issues/18)).
`ec_fva_ectestgem` confirmed one more, already documented in geckopy's own source before this
scenario existed: on ecTestGEM's one isozyme-split reaction, MATLAB's `ecFVA` reduces each
split variant's own bound independently across every canonical reaction's LP solve and then
sums forward and subtracts reverse (an "envelope" that can combine bounds from solves that
never occurred together), where `ec_fva` reads the combined value straight off the one solve
that actually optimised it (the "diagonal", always a value some feasible flux distribution
attains) --- every other reaction in the model has at most one enzyme, so nothing about their
bounds depends on which algorithm combines them.
`flexibilize_concs_ectestgem` found one more, but only in `flexibilizeEnzConcs`'s *refinement*
pass, not in the iterative loop before it (which agrees exactly): MATLAB's refinement solve
pins growth into a narrow +/-0.25% band around the target and settles at the band's low edge
while minimising protein-pool usage; geckopy's pins growth to the target exactly, a deliberate,
already-documented choice. `loadFluxData`/`constrainFluxData`, this scenario's other two
functions, turned out to match exactly in every mode tested, correcting a more cautious
suspicion in geckopy's own source comments.
`sensitivity_tuning_ectestgem` confirmed two more, both in `findMaxValue` --- a function grep
confirms has no callers anywhere in GECKO, so documented rather than fixed: its wildcard
matching can never actually match anything (the EC-prefix slice it builds is always the
literal string `".-"`, never a substring of a real EC code), and when nothing matches at all
it mislabels the empty result as `'SA*Mw'` rather than leaving the label blank.
`sensitivityTuning` and `truncateValues`, this scenario's other two functions, matched
exactly --- the former also correcting a stale MATLAB-COMPAT note in geckopy's own source,
obsoleted by an intervening GECKO change (usage/pool reactions switched to the forward
direction in [GECKO#419](https://github.com/SysBioChalmers/GECKO/pull/419)) rather than
confirming a still-current one.
The other three scenarios are red on purpose. `ec_fseof_ectestgem` on nearly everything it
reports, the widest gap in either pair: `geckopy.ec_fseof` is a thin wrapper over
`raven_toolbox.analysis.fseof`, not a port of `ecFSEOF.m` at all, and diverges from it on
three independent axes --- the enforced production-flux levels themselves (a different
formula, not just different numbers), the candidate search space (MATLAB considers only
gene-associated reactions, geckopy considers every reaction), and the selection criterion
(strict monotonicity + top-quartile-by-slope vs correlation + slope regression, the same
divergence already recorded on the RAVEN pair for `FSEOF` itself). On ecTestGEM: MATLAB
finds one target, geckopy finds six. `molecular_weight_sequences`: eighteen sequences
chosen to isolate one variable each, and all eighteen differ --- the two mass tables agree on
the twenty standard residues but not on `X` or `B`, and the two functions disagree on
case-sensitivity and on what an empty sequence is worth
([raven-gecko-parity#11](https://github.com/SysBioChalmers/raven-gecko-parity/issues/11)).
`ec_model_io_ectestgem`: a save/load round trip agrees on every field, on both sides, but the
written *file* does not lay out the same way --- the same divergence already tracked for
RAVEN's plain-GEM writers
([raven-gecko-parity#6](https://github.com/SysBioChalmers/raven-gecko-parity/issues/6)), one
layer down. All thirteen above run on ecTestGEM, GECKO's own 7-reaction unit-test model; one more,
`ec_model_full_yeastgem`, runs the same `makeEcModel` + BRENDA kcat-assignment pipeline on the
real yeast-GEM model (4102 conventional reactions) instead, in its own weekly workflow
(`gecko-genome-scale.yml`) rather than the nightly. It found and fixed two real MATLAB bugs
that no fixture small enough to write by hand could have reached --- `sigmaFitter.m` returning
a model sized for the wrong sigma
([GECKO#433](https://github.com/SysBioChalmers/GECKO/pull/433), merged), and `fuzzyKcatMatching.m`'s
wildcard EC search matching a substring instead of a prefix, so a query for one enzyme class
could also match an unrelated one whose code happened to contain the same characters elsewhere
([GECKO#434](https://github.com/SysBioChalmers/GECKO/pull/434), merged). See
[docs/gecko-behaviour-parity-plan.md](docs/gecko-behaviour-parity-plan.md) (Tier 4) for what
still diverges even with both fixed, for the programme behind all of this, and for what the
rest of the 49 gecko `parity` rows need.

See [docs/scenarios.md](docs/scenarios.md) for how to write one, including the conventions
that avoid false differences.

## Shared artefacts

Large downloadable data --- KEGG reference tables and HMM libraries, and the
BLAST+/DIAMOND/HMMER binaries both toolboxes shell out to --- lives outside either code
repo, in [`raven-data`](https://github.com/SysBioChalmers/raven-data) releases, described
by one manifest both sides read: how that's hosted, versioned and published is in
[docs/artefact_hosting.md](docs/artefact_hosting.md), and the manifest format itself in
[docs/data_manifest.md](docs/data_manifest.md). Building the KEGG artefacts is
[docs/maintaining_kegg_data.md](docs/maintaining_kegg_data.md), with the storage-format
decision behind them in [docs/kegg_data_format.md](docs/kegg_data_format.md); building the
binary bundles is [docs/maintaining_binaries.md](docs/maintaining_binaries.md).

## CI

`ci.yml` checks out all four repos and runs `parity check` on every push and nightly.

`nightly.yml` runs the behaviour scenarios against both implementations, for both pairs, using
`matlab-actions/setup-matlab` --- which is licence-free for public repositories, and the
reason this repo needs to be public. Raven and gecko are two matrix entries, one at a time
rather than in parallel so that one entry's commit back to this repo cannot race the other's;
each does the work only when its own tracked branches have moved since its last comparison,
and each commits its own report --- [`nightly/report.md`](nightly/report.md) for raven,
[`nightly/gecko-report.md`](nightly/gecko-report.md) for gecko --- so drift has a history
instead of an artefact that expires. The gecko entry is a four-repo checkout: GECKO needs
RAVEN on the MATLAB path and geckopy depends on raven-toolbox, so both are checked out and
raven-toolbox installed from that checkout before geckopy, rather than letting geckopy's own
metadata pull a revision this repo never recorded.

Both take the branch to compare from `parity.toml`, not from each repo's default:

```bash
parity refs
```

```
gecko    matlab  SysBioChalmers/GECKO@develop4
gecko    python  SysBioChalmers/geckopy@main
raven    matlab  SysBioChalmers/RAVEN@develop3
raven    python  SysBioChalmers/raven-toolbox@develop
```

None of the four defaults to its integration branch --- RAVEN's default is `main` and GECKO's
is `main`, while the ledgers describe `develop3` and `develop4`. A workflow that takes
defaults compares a release branch against a development one and reports the normal backlog
as drift.

## Status

Both ledgers are fully triaged --- no `unreviewed` rows --- so `parity check` passes on both
pairs and every public function on all four sides carries a declared status.

| | rows | parity | queued | one-sided | not API |
|---|---:|---:|---:|---:|---:|
| raven | 302 | 75 | 38 | 169 | 20 |
| gecko | 137 | 54 | 1 | 63 | 19 |

What remains between here and `parity check --strict` is tracking issues: the queued rows
warn until each carries an `issue`. See [docs/triage.md](docs/triage.md) for how the
decisions were made and how to keep new rows honest.
