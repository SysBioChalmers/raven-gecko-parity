---
name: run-tests
description: Run GECKO's MATLAB unit tests headless with RAVEN develop3 on the path. Use before reporting a GECKO change as working.
---

# Running GECKO tests

GECKO needs a RAVEN `develop3` checkout on the path before `GECKOInstaller.install` runs.
RAVEN goes on the path first, so GECKO's own functions take precedence where the two define
the same name.

```bash
matlab -batch "restoredefaultpath; addpath(genpath('<raven-checkout>')); cd('<gecko-checkout>'); GECKOInstaller.install; setRavenSolver('glpk'); cd('test/unit_tests'); r = runtests('geckoCoreFunctionTests'); disp(table(r))"
```

- CI uses the same sequence: it checks out RAVEN `develop3`, runs `GECKOInstaller.install`,
  selects GLPK and runs `geckoCoreFunctionTests`.
- `restoredefaultpath` removes other RAVEN or GECKO checkouts from the saved path; without
  it, a different checkout can shadow the one under test.
- To run one test, pass its name:
  `runtests('geckoCoreFunctionTests', 'ProcedureName', '<testName>')`.
- Genome-scale behaviour (yeast-GEM) is covered by the `ec_model_full_yeastgem` scenario in
  raven-gecko-parity, not by the unit tests.

## Hazards

- Two `matlab -batch` sessions running at the same time can corrupt
  `%APPDATA%\MathWorks\MATLAB\R2024b\matlabprefs.mat`. The symptom is that every test fails
  in setup with `MATLAB:load:unableToReadMatFile` or "Cannot find RAVEN Toolbox". Delete
  the file and run `setRavenSolver` again.
- Do not delete a RAVEN checkout or worktree while a background test run has it on the
  path. MATLAB reads files from it throughout the run, and the run fails with "Cannot find
  RAVEN Toolbox in the MATLAB path".
