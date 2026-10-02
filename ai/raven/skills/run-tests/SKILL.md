---
name: run-tests
description: Run RAVEN's MATLAB test suite headless, including MILP tests with Gurobi, and avoid the known failure modes. Use before reporting a RAVEN change as working.
---

# Running RAVEN tests

## Headless run

Clear the saved path first; otherwise another RAVEN checkout on the saved path shadows the
one under test. Test classes are named `t<Folder>.m`, and folder-based discovery does not
find them, so pass the names explicitly:

```bash
matlab -batch "restoredefaultpath; addpath(genpath('<checkout>')); cd('<checkout>/testing/function_tests'); r = runtests({'tINIT','tGapfilling'}); disp(table(r))"
```

- Exclude `tBinaries`; it downloads binaries.
- A full run is about 325 tests and takes a few minutes. CI builds the suite from every
  `t*.m` file except `RavenTestCase.m` and `tBinaries.m`.
- GLPK ships with RAVEN and is the default solver. Tests that need a MILP solver (ftINIT,
  `getMinNrFluxes`, gap-filling) are skipped through `assumeMILPSolver` unless Gurobi or
  SCIP is available. To run them, add Gurobi's MATLAB directory to the path (for example
  `addpath('C:\gurobi1302\win64\matlab')`) and select it with `setRavenSolver('gurobi')`.
  A skipped test is not a passing test; report skips.
- For a change that is meant to preserve behaviour, run the same classes on a clean
  checkout of `develop3` and compare the two results.

## Test fixtures

The fixtures used by `tINIT` (`getTstModel`, `getTstModelTasks`, `getTstModelL`) are local
functions after the `classdef` block's final `end` in `tINIT.m`. To use them from a scratch
script, append everything from `function testModel = getTstModel()` to the end of the file
onto the script; MATLAB scripts accept local functions at the end.

## Corrupted preferences

Test runs write MATLAB preferences (`RavenTestCase` sets `setpref('RAVEN', ...)`, and
`setRavenSolver` stores the solver). Two `matlab -batch` sessions running at the same time,
or one killed during a write, can truncate
`%APPDATA%\MathWorks\MATLAB\R2024b\matlabprefs.mat`. The symptoms:

- `ispref` raises `MATLAB:load:unableToReadMatFile`.
- `findRAVENroot` fails in every class's `TestClassSetup`, so the whole suite reports as
  errored or filtered, including trivial tests.
- A partly corrupted file shows first as one run with a few unexpected failures and extra
  "filtered by assumption" skips.

Delete the file (MATLAB recreates defaults) and run `setRavenSolver` again. Never run two
MATLAB batch sessions against RAVEN at the same time, and do not delete a checkout while a
background test run still uses it.
