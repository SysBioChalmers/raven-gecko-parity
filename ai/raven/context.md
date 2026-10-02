# RAVEN (MATLAB)

Integration branch `develop3`; pull requests target it. The Python implementation is
raven-toolbox, and the ledger is `ledgers/raven.yml` in raven-gecko-parity.

## Layout

- Source is in functional folders at the repository root: `analysis/`, `annotation/`,
  `biomass/`, `comparison/`, `conditions/`, `conversion/`, `curation/`, `gapfilling/`,
  `INIT/`, `io/`, `localization/`, `manipulation/`, `omics/`, `queries/`,
  `reconstruction/`, `solver/`, `tasks/`, `utils/`.
- Tests are in `testing/function_tests/`: one class `t<Folder>.m` per source folder, each
  inheriting `RavenTestCase`.
- Do not edit `software/` (vendored GLPKmex, libSBML, m2html, SCIP and binaries) or `doc/`
  (m2html output, regenerated with `updateDocumentation`).

## Code

- RAVEN is pure MATLAB. A function does not call a Python interpreter (`py.*`, `pyenv`, or a
  `python` subprocess) to do its own work. Starting a separate external tool as a black box
  (BLAST+, DIAMOND, HMMER, a Docker container) is allowed.
- Comments and help text describe the current MATLAB behaviour. They do not mention the
  Python implementation (raven-toolbox, geckopy, "unlike the Python version") and do not
  cite parity issues. This includes test files.
- Help text is NumPy style: a summary line starting with the function name, then
  `Parameters`, `Returns`, `Examples` and `See also` sections underlined with dashes. See
  `manipulation/setParam.m`.
- Essential arguments are positional; optional arguments are parsed with `parseRAVENargs`.
- Errors use `error('RAVEN:<id>', ...)` and native `warning`; `dispEM` does not exist on
  `develop3`.
- Function names are camelCase. CI runs MATLAB R2024b; do not use functions newer than that.
- Branches are named `fix/...` or `feat/...`. Commit subjects use semantic prefixes.
- `CHANGELOG.md` has one `##` heading per version with its release date, and `###` topic
  sections below it; copy the heading format of the latest entry. The version is in
  `version.txt`.

Run the affected test classes before reporting a change as working; the `run-tests` skill
has the commands.
