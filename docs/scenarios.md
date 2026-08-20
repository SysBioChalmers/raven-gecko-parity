# Writing a scenario

A scenario runs the same computation through both implementations and diffs the results. It
is the only thing here that checks *behaviour*; everything else checks that the two APIs line
up on paper.

## Layout

```
scenarios/<id>/
    scenario.yml     declaration: inputs, tolerance, which ledger rows it covers
    run.py           def run(ctx) -> dict
    <id>.m           function results = <id>(ctx)
```

The MATLAB file is named after the scenario, not `run.m`: `run` is a MATLAB builtin, and
per-scenario names keep two scenarios from shadowing each other on the path.

## Declaration

```yaml
id: elemental_balance_smallyeast
pair: raven
description: Elemental balance of every reaction in RAVEN's smallYeast tutorial model.

entries:
  - getElementalBalance          # ledger rows this scenario validates

inputs:
  model: "{matlab_repo}/tutorial/smallYeast.yml"
  zero_tolerance: 1.0e-9

tolerance:
  rel: 1.0e-9
  abs: 1.0e-12
```

`inputs` are passed to both sides unchanged. Strings may use `{matlab_repo}`,
`{python_repo}`, `{scenario_dir}` and `{repo_root}`; a value that resolves to an existing
path is made absolute. Pointing at a fixture inside one of the repos beats vendoring a copy:
both sides then read the same bytes, and the fixture cannot drift.

Cross-reference the scenario from the ledger row it covers, so `parity mirror` can tell you
which scenarios to re-run after a change:

```yaml
- matlab: getElementalBalance
  python: raven_toolbox.utils.get_elemental_balance
  status: parity
  scenarios:
    - elemental_balance_smallyeast
```

## Both sides must agree on shape, not just numbers

`parity compare` walks the two results structurally. Nearly every false difference comes from
the harness rather than the toolboxes, and they are all avoidable:

**Sort everything.** Model order is not a specification. Sort reaction lists by id on both
sides.

**Always emit every key.** A count of zero must be `0`, not an absent key --- otherwise a
count that happens to be zero reads as a structural difference. Where one implementation has
a category the other lacks (RAVEN's `balanceStatus == -2` has no Python counterpart), emit it
as zero on the side that lacks it. That keeps a real occurrence visible instead of folding it
into a neighbouring category.

**Use lists of records, not keyed objects,** when the keys are model identifiers. Reaction
ids are not always valid MATLAB struct field names.

**Watch `jsonencode` on a 1×1 struct array** --- MATLAB writes a bare object where you meant
a one-element array. Build such lists as cell arrays of structs.

**Declare epsilons in the scenario, not in the code.** MATLAB's matrix arithmetic leaves
~1e-15 dust where terms cancel exactly. Without a shared `zero_tolerance` the two sides
disagree about which elements are even *present* in a residual. Put the number in
`scenario.yml` so both read the same one.

**Do not set the tolerance to zero.** The two toolboxes sum the same coefficients in a
different order, so the last bits of a float legitimately differ. `rel: 1e-9` is tight enough
that nothing real hides behind it.

## Running

```bash
parity run <id> --impl python
parity run <id> --impl matlab            # needs matlab on PATH
parity compare results/python/<id>.json results/matlab/<id>.json --scenario <id>
```

Without MATLAB on PATH, run the Python side first (it writes the context file) and then, from
inside MATLAB:

```matlab
addpath('<this repo>/matlab')
addpath(genpath('<RAVEN>'))
parity_run('<this repo>/scenarios/<id>')
```

## What to cover

The places where the numbers matter and the algorithms are intricate: ftINIT, gap-filling,
localization, kcat matching, protein pool limits. Roughly 15--25 scenarios is the useful
range.

Do not aim for coverage of the whole API. A scenario over a thin wrapper costs maintenance
and tells you nothing, and a scenario over two functions that share a name but not an
algorithm --- `predictLocalization`'s simulated annealing against Python's MILP --- is
actively misleading. Check the ledger `notes` before writing one.
