# GECKO (MATLAB)

Integration branch `develop4`; pull requests target it. GECKO runs on top of RAVEN
`develop3` and ships no copy of it. The Python implementation is geckopy, and the ledger is
`ledgers/gecko.yml` in raven-gecko-parity.

## Layout

- Source is in `src/` (`change_model`, `enzyme_usage`, `flux_analysis`, `gather_kcats`,
  `geckomat`, `get_enzyme_data`, `io`, `kcat_tuning`, `limit_proteins`, `model_adapter`,
  `utilities`, and others).
- Unit tests are in `test/unit_tests/geckoCoreFunctionTests.m`, a function-based test file
  with tests named `test<name>_tc000N`. The fixture model is `ecTestGEM`, loaded through
  `getGeckoTestModel.m`. A new function gets a test in this file.
- Do not edit `doc/` (m2html output).

## Code

- GECKO is pure MATLAB. A function does not call a Python interpreter (`py.*`, `pyenv`, or
  a `python` subprocess) to do its own work. Starting a separate external tool as a black
  box (for example DLKcat in a Docker container) is allowed.
- Comments and help text describe the current MATLAB behaviour. They do not mention the
  Python implementation (geckopy, raven-toolbox, "unlike the Python version") and do not
  cite parity issues. This includes test files.
- Help text is NumPy style with `Parameters`, `Name-Value Arguments`, `Returns`,
  `Examples` and `See also` sections. See `src/change_model/applyKcatConstraints.m`.
- Optional arguments are parsed with `parseGECKOargs`, positional or name-value.
- A RAVEN function that GECKO calls must exist on RAVEN `develop3`. When RAVEN renames or
  removes a function, GECKO's calls to it break without a compile-time error.
- Function names are camelCase. CI runs MATLAB R2024b.
- Branches are named `{chore,doc,feat,fix,refactor,style}/<name>`. Commit subjects use
  semantic prefixes.

Run the unit tests before reporting a change as working; the `run-tests` skill has the
commands.
