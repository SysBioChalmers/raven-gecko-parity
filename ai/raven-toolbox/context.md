# raven-toolbox (Python)

Integration branch `develop`; pull requests target it. This is the Python implementation of
RAVEN, and the ledger is `ledgers/raven.yml` in raven-gecko-parity. geckopy depends on this
package.

## Layout

- Source is `src/raven_toolbox/`. Subpackages follow RAVEN's folders (`analysis`,
  `annotation`, `biomass`, `comparison`, `conditions`, `curation`, `gapfilling`, `init`,
  `io`, `localization`, `manipulation`, `reconstruction`, `tasks`, `utils`).
- Tests are `tests/test_<package>_<topic>.py`, with data in `tests/data/`. Tests that
  compare against MATLAB RAVEN are in `tests/parity/`.
- `data/manifest.json` is the source of the data and binary registries. Do not edit
  `_DATA_REGISTRY` or `_REGISTRY` by hand; run `python scripts/make_registry_snippet.py sync`.
- RAVEN is GPL-licensed; no RAVEN source is copied into this repository.
- User documentation is on raven-docs, which builds its API reference from the docstrings.
  This repository has no user documentation tree.

## Code

- Module and function names are snake_case ports of RAVEN functions (`replaceMets`
  becomes `manipulation.replace_metabolite`).
- Each subpackage's `__init__.py` re-exports its public functions and lists them in
  `__all__`. A new name in `__all__` needs a ledger row.
- Docstrings are NumPy style.
- `CHANGELOG.md` entries name the new function and the RAVEN function it ports, for example
  "New: `x.y`, ported from `camelName`".

## Checks

```bash
pip install -e ".[dev,excel]"
ruff check .
mypy
pytest -v --timeout=300
```

- ruff is pinned to the version in `pyproject.toml` (line length 100, rules
  `E,F,W,I,UP,B`). mypy checks `src/raven_toolbox`.
- CI runs pytest on Python 3.11, 3.12 and 3.13 on Linux, and 3.12 on macOS and Windows.
- `pytest -m "parity and not slow"` runs the MATLAB comparison tests. They need a RAVEN
  checkout in `RAVEN_ROOT`, and several need Gurobi (`gurobipy`); without Gurobi they skip.
  The `slow` marker selects genome-scale tests.
