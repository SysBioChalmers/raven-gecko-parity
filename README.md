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

See [docs/scenarios.md](docs/scenarios.md) for how to write one, including the conventions
that avoid false differences.

## CI

`ci.yml` checks out all four repos and runs `parity check` on every push and nightly.

`nightly.yml` runs the behaviour scenarios against both implementations, using
`matlab-actions/setup-matlab` --- which is licence-free for public repositories, and the
reason this repo needs to be public. It only does the work when a tracked branch has moved
since the last comparison, and it commits [`nightly/report.md`](nightly/report.md) so drift
has a history instead of an artefact that expires.

Both take the branch to compare from `parity.toml`, not from each repo's default:

```bash
parity refs
```

```
gecko    matlab  SysBioChalmers/GECKO@develop4
gecko    python  SysBioChalmers/geckopy@develop
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
| raven | 301 | 73 | 32 | 158 | 38 |
| gecko | 138 | 47 | 6 | 61 | 24 |

What remains between here and `parity check --strict` is tracking issues: the queued rows
warn until each carries an `issue`. See [docs/triage.md](docs/triage.md) for how the
decisions were made and how to keep new rows honest.
