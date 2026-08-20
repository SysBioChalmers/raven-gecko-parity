# Day-to-day workflow

Where the ledger fits into the work you were doing anyway.

## A bug is reported against MATLAB RAVEN

1. Reproduce and fix it in RAVEN as usual.
2. Before pushing, ask what it implies:

   ```bash
   parity mirror --since develop..HEAD
   ```

   The `pre-push` hook does this for you.
3. If the touched function is `parity`, check whether raven-toolbox has the same bug. It
   usually does --- the port followed the original closely. Open the sibling issue with the
   RAVEN issue linked, and record it on the ledger row while it is open:

   ```yaml
   - matlab: fillGaps
     python: raven_toolbox.gapfilling.connect_blocked_reactions
     status: parity
     notes: RAVEN#456 / raven-toolbox#789 --- same off-by-one in the weight vector.
   ```
4. If the touched function is `matlab-only` or `via-dependency`, there is nothing to mirror.
   The ledger already answered the question.
5. If the row is `unreviewed`, triage it now. A bug report is the cheapest possible moment to
   decide what a function is.

## A feature is developed in Python first

1. Build it in raven-toolbox or geckopy.
2. `parity sync` adds a row for the new export; set its status in the same PR:

   ```yaml
   - python: raven_toolbox.localization.assign_compartments
     status: matlab-pending
     issue: SysBioChalmers/RAVEN#123
     notes: Port plan --- MILP via optimizeProb/getMILPParams, reusing parseScores.
   ```

   `matlab-pending` without an `issue` is a warning, not an error: it is fine to defer the
   decision, not fine to lose it.
3. When the back-port lands, flip the row to `parity` and add the MATLAB name. `parity check`
   enforces this --- a `matlab-pending` row that names a MATLAB function is an error, because
   the status is now a lie.
4. Consider a scenario. Anything with a solver in it earns one.

## A deliberate divergence

Record it with a reason, and the question stops coming back:

```yaml
- matlab: runDynamicFBA
  status: matlab-only
  reason: Maintained Python packages already cover dynamic FBA (dfba, reframed, mewpy).
```

`parity report` renders these as the divergence register, so the rationale lives with the
decision instead of in a pull request comment from two years ago.

## Releases

Do not force version lockstep --- it produces empty releases. State the baseline instead, one
line in each CHANGELOG:

```
Parity baseline: RAVEN 2.11. Exceptions: parity/raven.yml in raven-gecko-parity.
```

Before tagging:

```bash
parity check --strict
parity report -o build/
```

and run the scenarios for anything that changed since the last tag.

## Working with a coding agent

Add this to `CLAUDE.md` (or the equivalent) in all four repos:

```markdown
## Cross-implementation parity

This repo is one half of a MATLAB/Python pair. Before closing a bug or finishing a feature,
check `raven-gecko-parity/ledgers/<pair>.yml` for the functions you touched:

- `parity` -> the same bug or feature probably applies to the other implementation. Say so
  explicitly in your summary, and open or reference a sibling issue.
- `matlab-only` / `python-only` / `via-dependency` -> deliberate; do not mirror.
- `unreviewed` -> triage it as part of this change.

New public functions need a ledger row in the same PR; `parity check` fails without one.
Run `parity mirror --since <base>..HEAD` from the repo root to see what a change implies.
```

The intent is the same as the git hooks: make the cross-check something that happens without
anyone having to remember it.
