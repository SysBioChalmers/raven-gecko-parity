# Triage: getting the `unreviewed` count to zero

Seeding pairs up what it can by name and leaves the rest as `unreviewed`. That is a starting
point, not an answer: the tool matched *names*, and only a human can confirm *behaviour*.

Until the count reaches zero the ledger is still useful --- it already fails CI when a brand
new function appears undeclared. It becomes a hard invariant once you can add `--strict`.

## The question for each row

For a row with both sides filled in:

> Do these two functions do the same thing, such that a bug in one is probably a bug in the
> other?

If yes, `status: parity`. If they merely share a name, break the pairing and treat them as
two separate rows.

`predictLocalization` is the instructive case. MATLAB's is simulated annealing; Python's is a
score-driven MILP. Same purpose, different algorithm, results not expected to match
numerically. That is `parity` in the sense that both exist and a *conceptual* bug affects
both --- but it must never get a scenario asserting equal numbers. Say so in `notes`.

For a one-sided row, pick the reason it is one-sided:

* the other side genuinely needs it → `python-pending` / `matlab-pending`, with an `issue`;
* cobrapy or the COBRA Toolbox already covers it → `via-dependency`, with the replacement
  named in `reason`;
* it is a deliberate omission → `matlab-only` / `python-only`, with the rationale in `reason`;
* it is not really public API --- an installer, a path helper, internal glue → `internal`.

Be willing to use `internal`. A MATLAB repo has plenty of functions that are public only in
the sense that MATLAB has no other visibility mechanism.

## Working through them

`parity report` groups everything awaiting triage, with the seeder's suggestions:

```bash
parity report --pair raven -o build/
```

The `notes` on an unpaired row name the closest candidates on the other side, so most rows
are a yes/no rather than a search:

```yaml
- matlab: getRxnsFromKEGG
  status: unreviewed
  notes: 'no confident pairing; closest Python exports: parse_kegg_reactions'
```

Triage by subsystem rather than alphabetically --- localization, then gap-filling, then I/O.
Related functions share reasoning, and a subsystem finished is a subsystem you can stop
thinking about.

## Prior art worth mining

Both Python repos already document parity decisions in prose. `scripts/import_migration_md.py`
converts raven-toolbox's `docs/reference/migration.md` into ledger rows automatically, which
is where the initial `parity` and `matlab-only` entries came from. Still worth reading:

* `raven-toolbox/docs/reference/matlab_raven_backports.md` --- deliberate omissions and the
  back-port queue;
* `raven-toolbox/docs/reference/improvements.md` --- what is a candidate to upstream;
* `geckopy/docs/internal/raven_inventory.md` --- which RAVEN calls cobrapy already covers;
* `geckopy/docs/migrating_from_gecko_matlab.md`.

As rows move out of `unreviewed`, those documents become redundant: `parity report` generates
the same content from the ledger and cannot go stale. Replace them with the generated report
rather than maintaining both.

## When the count hits zero

Add `--strict` to the CI step:

```yaml
- run: parity check --strict
```

From then on, a new public function must be classified in the same PR that introduces it.
