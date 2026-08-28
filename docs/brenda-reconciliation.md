# Reconciling the two BRENDA fixtures

GECKO ships its BRENDA snapshot as `max_KCAT.txt` / `max_MW.txt` / `max_SA.txt`; geckopy reads
`kcat.tsv` / `mw.tsv` / `sa.tsv`. Same data, two formats, and neither loader reads the other's ---
the only place in either pair where that is true. This confirms the two ecTestGEM fixtures carry
the same triples and that `loadBRENDAdata` and `load_brenda_data` parse them into the same shape,
so the kcat-chain scenario can declare both paths without first re-deriving this by hand.

Tracked against [gecko-behaviour-parity-plan.md](gecko-behaviour-parity-plan.md), Tier 2.

## The short answer

**Yes --- the ecTestGEM fixtures are the same five (EC, substrate, organism, value) triples,
written in two formats, and both loaders parse them the same way.** There is no divergence to
resolve here, unlike the YAML writers. The one thing worth recording is that the fixture happens
not to exercise the SA-derived-kcat join on either side, and a stale unit comment in MATLAB's
loader.

## The two formats

MATLAB's rows are five tab-separated fields, EC codes carry an `EC` prefix, and the organism field
is a `name//taxonomy;lineage//abbreviation` triple joined on `//`:

```
EC1.1.1.1	m1	testus testus//*//*	1	*
EC1.1.1.1	m2	testus falsus//*//*	10	*
EC1.1.2.2	m1	testus testus//*//*	100	*
```

geckopy's rows are a header plus explicit columns, EC codes are bare, and the organism field is
already just the name:

```
ec_code	substrate	organism	kcat_max	kcat_median	n	references
1.1.1.1	m1	testus testus	1.0	1.0	1	*
1.1.1.1	m2	testus falsus	10.0	10.0	1	*
1.1.2.2	m1	testus testus	100.0	100.0	1	*
```

`loadBRENDAdata.m` strips the `EC` prefix with `extractAfter(KCATcell{1},2)` and the taxonomy
suffix with `regexprep(data_cell{3},'\/\/.*','')`. Once both are stripped, the two files above are
the same three rows. The same holds for `max_MW.txt` / `mw.tsv` (one row: EC `1.1.1.1`, organism
`testus testus`, weight `50010`) and `max_SA.txt` / `sa.tsv` (one row: EC `1.1.1.1`, organism
`acetobacter pasteurianus`, value `2`).

## Evidence

### 1. The loaders agree on the direct table

Running `load_brenda_data` against `examples/ecTestGEM/data/` in Python:

```
=== kcat_max ===
   ec_code substrate       organism   kcat  n
0  1.1.1.1        m1  testus testus    1.0  1
1  1.1.1.1        m2  testus falsus   10.0  1
2  1.1.2.2        m1  testus testus  100.0  1
```

Running `loadBRENDAdata` against `TestGEMAdapter` in MATLAB:

```
=== KCATcell ===
1.1.1.1	m1	testus testus	1
1.1.1.1	m2	testus falsus	10
1.1.2.2	m1	testus testus	100
```

Same three rows, same order, same EC codes, substrates, organisms and values, once `KCATcell`'s
`EC` prefix is stripped by the loader itself.

### 2. Both loaders' SA-join is untested by this fixture, and that's fixture data, not a bug

geckopy's `sa_max` (the specific-activity table joined against molecular weight) comes back empty:

```
=== sa_max (SA joined with MW) ===
Empty DataFrame
Columns: [ec_code, organism, kcat, mw, n]
Index: []
```

That is correct, not a loader defect: `sa.tsv`'s only row is organism `acetobacter pasteurianus`;
`mw.tsv`'s only row is organism `testus testus`. `_join_sa_with_mw` matches on (EC, organism)
case-insensitively, and these organisms don't match, so the join legitimately drops the row.

MATLAB's `loadBRENDAdata.m` runs the equivalent join (`containers.Map` on EC, then
`strcmpi` on organism within that EC's rows) against `max_SA.txt` and `max_MW.txt` --- the same
EC (`EC1.1.1.1`), the same mismatched organisms (`acetobacter pasteurianus` vs `testus testus`).
Executed against `TestGEMAdapter`, it reports:

```
=== SAcell (derived kcat) ===
rows: 0
```

The two loaders are given the same non-match by their respective fixtures and produce the same
empty result.

This means the ecTestGEM fixture as it stands cannot be used to check the SA-derived-kcat value
itself, only that both loaders correctly decline to join when the organism doesn't match. Whoever
writes the `fuzzy` checkpoint should either accept that gap and note it, or add a second SA/MW
pair with a matching organism to both fixtures at the same time --- not as part of this
reconciliation, since it would mean hand-authoring new BRENDA-shaped numbers rather than
confirming existing ones.

### 3. A stale unit comment, found in passing

`loadBRENDAdata.m` computes the derived kcat as `SA{4}(i)*mwEC{2}(org_index)`, commented
`%[1/hr]` (line 58). Both scaling factors applied earlier in the same function are documented as
producing SI-per-second units --- `1/60` for `[umol/min/mg] -> [mmol/s/g]` and `1/1000` for
`[g/mol] -> [g/mmol]` --- and `[mmol/s/g] * [g/mmol] = [1/s]`, not `[1/hr]`. A second comment two
lines above (`Old: 60 [umol/min/mg] -> [mmol/h/g]`) confirms the function used to work in hours
and was changed to seconds; the `%[1/hr]` on the product line reads like a leftover from before
that change. geckopy's docstring already states the derived value is `[1/s]`, matching the
arithmetic rather than the stale comment. No behaviour depends on the comment, and the fixture
doesn't exercise this code path (see above), so this is noted rather than filed.

## What this unblocks

The kcat-chain scenario's `fuzzy` checkpoint can declare both fixture pairs
(`max_KCAT.txt`/`max_MW.txt`/`max_SA.txt` and `kcat.tsv`/`mw.tsv`/`sa.tsv`) knowing they assert
the same triples, and can compare `KCATcell`/`kcat_max` directly. The SA-join path stays
untested until the fixture gains a matching-organism pair, which is a scenario-design decision,
not a reconciliation finding.

The other prerequisite, the BRENDA **search-order** difference in `fuzzyKcatMatching` /
`fuzzy_kcat_matching`, is unrelated to fixture format and is not addressed here.

## Reproducing

Python:

```bash
python -c "from geckopy.databases.brenda_loader import load_brenda_data; d = load_brenda_data('examples/ecTestGEM/data'); print(d.kcat_max); print(d.sa_max)"
```

MATLAB, with RAVEN and GECKO on the path:

```matlab
adapter = ModelAdapterManager.getAdapter(fullfile(geckoPath, 'test', 'unit_tests', 'ecTestGEM', 'TestGEMAdapter.m'));
[KCATcell, SAcell] = loadBRENDAdata(adapter);
```
