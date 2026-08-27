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

**Do not set the tolerance to zero** where anything is summed. The two toolboxes add the same
coefficients in a different order, so the last bits of a float legitimately differ. `rel: 1e-9`
is tight enough that nothing real hides behind it. A scenario that only copies, negates or
clamps numbers --- or that compares no numbers at all --- may declare zero, and saying so in
the declaration is how the reader knows which kind it is.

**Sort multi-key lists the way Python does.** Sorting records by `(reaction, metabolite)` is
the obvious thing and the easy thing to get wrong: joining the keys with a printable separator
does not reproduce Python's tuple comparison. `'|'` is above `'_'`, so `ACS|x` sorts *after*
`ACS_EXP_1|y` where Python puts `ACS` first, and a scenario that expands isozymes hits this on
its first run. Join with `char(1)` instead --- below every character an identifier can contain,
so a shorter key still sorts before a longer one that extends it.

**A missing number is not NaN.** MATLAB's `jsonencode` writes NaN as `null`; the Python side
canonicalises it to the string `"NaN"`. An absent metabolite charge therefore reads as a
difference between the two *harnesses*. Emit a flag and a zero (`has_charge`, `charge`) so
absence is a value both sides can state.

**Where order is the result, do not sort it.** The rule above is "sort everything", and the
exception is a function whose whole output is an ordering --- `sortIdentifiers`, or a writer's
line-by-line output. Sorting those before comparing them compares the harness against itself.

**`jsonencode` refuses a sparse value.** Indexing a model's `S` gives a sparse scalar, and the
harness dies with *"Unable to encode sparse objects of class double as JSON-formatted text"* --- at
the very end of the run, after all the work. Wrap it in `full()`. `find(S)` returns full values, so
this only bites when a scenario reads a coefficient by position.

**Declare the solver; do not inherit it.** A scenario that needs an LP or a MILP will otherwise
compare RAVEN's solver preference against whatever cobrapy found on the machine, and the first
question anyone asks of a difference is whether the solver explains it. Name the solver in
`scenario.yml` and set it on both sides --- `setRavenSolver` in MATLAB, `cobra.Configuration().solver`
*before* any model is read, since a cobra model takes its solver at construction. RAVEN's default is
glpk, which cannot solve a MILP at all. And restore the previous preference on the way out: it is
global, and the nightly runs several scenarios in one MATLAB session.

**Emit text as lines, not as a digest.** A hash tells you two files differ; a list of lines
tells `parity compare` where. It reports a length mismatch once rather than per line, so the
failure stays readable even when the two files are nothing alike. Normalise the line endings
first: MATLAB writes CRLF on Windows, which is the harness's doing, not the writer's.

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

A gecko scenario needs **both** toolboxes on the MATLAB path --- GECKO is built on RAVEN and
ships no copy of it --- with RAVEN first, so that GECKO wins where the two define the same
name. `parity prepare` emits that automatically: the pair's `setup` in `parity.toml` names
`{raven_matlab}`, which resolves to wherever the raven pair is configured, `parity.local.toml`
included.

```matlab
addpath(genpath('<RAVEN>')); addpath(genpath('<GECKO>'))
```

## What to cover

The places where the numbers matter and the algorithms are intricate: ftINIT, gap-filling,
localization, kcat matching, protein pool limits. Roughly 15--25 scenarios is the useful
range.

Do not aim for coverage of the whole API. A scenario over a thin wrapper costs maintenance
and tells you nothing, and a scenario over two functions that share a name but not an
algorithm --- `predictLocalization`'s simulated annealing against Python's MILP --- is
actively misleading. Check the ledger `notes` before writing one.
