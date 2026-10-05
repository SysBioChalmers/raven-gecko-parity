---
name: parity-ledger
description: How to check and update the RAVEN and GECKO parity ledgers in raven-gecko-parity. Use when fixing a bug or adding, renaming or removing a public function in RAVEN, GECKO, raven-toolbox or geckopy, or when a change may need mirroring to the other language.
---

# Parity ledger

Each pair has one ledger in
[raven-gecko-parity](https://github.com/SysBioChalmers/raven-gecko-parity):

| Pair | Ledger |
|---|---|
| RAVEN and raven-toolbox | `ledgers/raven.yml` |
| GECKO and geckopy | `ledgers/gecko.yml` |

Every public function on either side has one row. A row names the MATLAB function, the
Python function (as a dotted path), or both, and carries a status:

| Status | Meaning |
|---|---|
| `parity` | Both sides implement the function and are intended to behave the same. |
| `python-pending` | MATLAB has it; a Python port is queued. |
| `matlab-pending` | Python has it; a MATLAB port is queued. |
| `matlab-only` | Deliberately MATLAB-only. Needs a `reason`. |
| `python-only` | Deliberately Python-only. Needs a `reason`. |
| `via-dependency` | The other side gets this from cobrapy or the COBRA Toolbox. Needs a `reason`. |
| `subsumed` | The other side has the capability inside another function. Needs a `reason`. |
| `internal` | Not part of the cross-implementation API. Needs a `reason`. |
| `unreviewed` | Not yet triaged. |

## After a change

1. Find the rows for the functions you touched. From inside any of the four repositories,
   with raven-gecko-parity installed (`pip install -e .` in its checkout):

   ```bash
   parity mirror --since <base-branch>..HEAD
   ```

   Without the tool, search the ledger file for the function name.
2. Act on the status:
   - `parity`: the sibling implementation probably has the same bug or needs the same
     feature. State this in your summary, and open or reference a sibling issue. While that
     issue is open, record it in the row's `notes`.
   - `matlab-only`, `python-only`, `via-dependency`: deliberate. Do not mirror.
   - `unreviewed`: triage the row as part of the change.
3. A new public function (a new `.m` file in RAVEN or GECKO, a new name in a Python
   `__all__`) needs a row in the same change; `parity check` fails without one. Run
   `parity sync` to add rows, then set each status. A `matlab-pending` or `python-pending`
   row carries an `issue` for the port.
4. When a port lands, change the row to `parity` and fill in the other side's name.
5. Behaviour with a solver in it gets a scenario under `scenarios/` that runs both sides on
   the same input and compares the results. See `docs/scenarios.md` in raven-gecko-parity.

Ledger edits are pull requests to raven-gecko-parity against `develop`, separate from the
pull request in the code repository.

## Commands

```bash
parity check              # validate both ledgers against the four checkouts
parity sync               # add rows for newly public functions
parity mirror --since develop3..HEAD
parity scenarios          # list scenarios and the rows they cover
parity refs               # the branch compared for each repository
```

`parity.toml` assumes the four checkouts sit next to raven-gecko-parity. Override paths per
machine in `parity.local.toml`.
