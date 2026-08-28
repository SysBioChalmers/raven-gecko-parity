# Plan: behavioural parity for GECKO ↔ geckopy

The gecko ledger carries **49 rows marked `parity`** and, until now, no scenario at all: every
one of those rows was a claim about matching names. This is the plan to make the claim real,
and the companion to [behaviour-parity-plan.md](behaviour-parity-plan.md), which does the same
job for RAVEN.

## What exists now

| Scenario | Covers | Verdict |
|---|---|---|
| `ec_model_expansion_ectestgem` | `makeEcModel`, `loadConventionalGEM`, `ModelAdapter` | match |
| `enzyme_annotation_ectestgem` | `applyComplexData`, `getECfromGEM`, `getECfromDatabase` | match |
| `protein_pool_ectestgem` | `setProtPoolSize`, `calculateFfactor`, `loadProtData`, `fillEnzConcs`, `constrainEnzConcs` | match |
| `molecular_weight_sequences` | `calculateMW` | **differs**, on purpose --- see below |
| `ec_model_io_ectestgem` | `saveEcModel`, `loadEcModel` | match (content); **differs** (layout) |
| `model_edits_ectestgem` | `addNewRxnsToEC`, `copyECtoGEM`, `setKcatForReactions`, `getReactionsFromEnzyme`, `mapRxnsToConv` | match, plus four small documented divergences --- see below |
| `kcat_chain_ectestgem` | `fuzzyKcatMatching`, `loadBRENDAdata`, `writeDLKcatInput`, `readDLKcatOutput`, `mergeDLKcatAndFuzzyKcats`, `selectKcatValue`, `applyCustomKcats`, `getKcatAcrossIsozymes`, `getStandardKcat`, `removeStandardKcat`, `applyKcatConstraints` | match, plus three confirmed divergences --- see below |
| `okp_kcat_ectestgem` | `findMetSmiles`, `writeOpenKineticsPredictorInput`, `readOpenKineticsPredictorOutput` | match, plus one confirmed divergence --- see below |
| `enzyme_usage_ectestgem` | `enzymeUsage`, `reportEnzymeUsage`, `getConcControlCoeffs` | match, plus one confirmed divergence --- see Tier 3 below |
| `ec_fva_ectestgem` | `ecFVA` | match, plus one confirmed divergence --- see Tier 3 below |
| `flexibilize_concs_ectestgem` | `loadFluxData`, `constrainFluxData`, `flexibilizeEnzConcs` | match, plus one confirmed divergence --- see Tier 3 below |
| `sensitivity_tuning_ectestgem` | `sensitivityTuning`, `sigmaFitter`, `findMaxValue`, `truncateValues` | match, plus two confirmed divergences --- see Tier 3 below |
| `ec_fseof_ectestgem` | `ecFSEOF` | **differs**, on purpose --- see Tier 3 below |

Thirteen scenarios, forty-five of the 49 rows. Five of the first six run on GECKO's own unit-test
model and agree on content, so the base of the pipeline --- the expansion into an ecModel, the
annotation of its `ec` substructure, the protein budget that limits it, the save/load round
trip, and everyday edits to a built model --- is checked rather than assumed.
`enzyme_annotation_ectestgem` was blocked until [GECKO #425] merged, and
`model_edits_ectestgem` until [GECKO #427]; see below for both. `molecular_weight_sequences`
and `ec_model_io_ectestgem` are red by design: the former on every one of its eighteen
sequences ([raven-gecko-parity #11]), the latter on the written file's layout only, not its
content ([raven-gecko-parity #6], one level down from where it was already tracked).
`kcat_chain_ectestgem` closes out the whole kcat pipeline --- eleven functions across five
stages on one flowing ecModel --- and was blocked until three real MATLAB bugs it found along
the way were fixed; see Tier 2 below for all three. `okp_kcat_ectestgem` covers OKP, the newer,
REST-submitted alternative to DLKcat kcat prediction, and started life as three ledger rows
wrongly filed as one-sided (`matlab-only`/`python-only` with no counterpart named, despite each
side's own reason text naming the other) --- see the fixed ledger rows themselves for the
correction, and Tier 2 below for the one real MATLAB indexing bug this scenario found and fixed
along the way. `enzyme_usage_ectestgem` is the first
scenario in this pair to need an LP solver, `ec_fva_ectestgem` the second,
`flexibilize_concs_ectestgem` the third, `sensitivity_tuning_ectestgem` the fourth and
`ec_fseof_ectestgem` the fifth and last --- Tier 3 is complete; see below for all five
fixtures and the confirmed divergences each one found. `ec_fseof_ectestgem` is also red by
design, on nearly everything it reports --- the widest-reaching divergence in either pair,
already visible on the RAVEN side before this scenario existed.

## The fixture

`test/unit_tests/ecTestGEM` in the GECKO checkout: 7 reactions, 5 genes, and a hand-written
UniProt / KEGG / Complex Portal / BRENDA / proteomics snapshot. It is the model MATLAB's
`geckoCoreFunctionTests.m` pins its expected values against, and geckopy carries a port of that
suite (`tests/test_gecko_matlab_parity.py`) against its own copy under `examples/ecTestGEM`.

Both sides of a scenario read the **GECKO** copy. geckopy's adapter is loaded from its own
`model_adapter.toml` --- that file is one of the things being compared --- and only its `path`
and `conv_gem` are repointed at the GECKO fixture, so the parameter values stay geckopy's while
the data bytes are shared. Where the two would otherwise read different files, the scenario
declaration says so.

Three consequences worth stating up front:

**The SBML readers get tested for free.** MATLAB's own tests build the test model in code
(`getGeckoTestModel.m`) rather than reading `models/testModel.xml`. A scenario cannot do that
--- the two sides have to start from the same bytes --- so both read the SBML file, one through
RAVEN's `importModel` and one through cobrapy. That is why `ec_model_expansion_ectestgem` emits
a `conventional` checkpoint before it emits anything about `makeEcModel`: a divergence there is
the readers, not GECKO. Today they agree on every reaction, bound, metabolite, gene association
and stoichiometric coefficient.

**The adapters get compared, not assumed.** The same scenario emits an `adapter` checkpoint, so
a drift between GECKO's `TestGEMAdapter.m` and geckopy's `model_adapter.toml` is reported
rather than silently changing what the rest of the scenario measures.

**BRENDA is the one fixture that cannot be shared.** GECKO ships it as
`max_KCAT.txt` / `max_MW.txt` / `max_SA.txt`; geckopy reads `kcat.tsv` / `mw.tsv` / `sa.tsv`.
Same data, two formats, and neither loader reads the other's. The kcat scenarios below therefore
have to declare two paths and say why --- the only place in either pair where that is true.
Confirmed equivalent, by execution on both sides: [docs/brenda-reconciliation.md](brenda-reconciliation.md).

## Resolved: GECKO did not run against RAVEN `develop3`

Filed as [GECKO #424], fixed by [GECKO #425], **merged to `develop4`** on 2026-08-26
(`d053ca94`). Left here because the pattern --- a cross-repo removal that only running code
detects --- is worth recognising the next time it happens.

`applyComplexData` calls `progressbar`, which RAVEN removed when it replaced ad-hoc progress
reporting with the `progressReport` class ([RAVEN #623]). It is not one function: on
`develop4`, eight GECKO sources call it in 22 places.

| GECKO function | Call sites |
|---|---:|
| `applyComplexData` | 3 |
| `findMetSmiles` | 3 |
| `getComplexData` | 2 |
| `fuzzyKcatMatching` | 2 |
| `getECfromDatabase` | 2 |
| `loadDatabases` | 2 |
| `ecFSEOF` | 6 |
| `ecFVA` | 2 |

On the branch pair the ledger tracks --- GECKO `develop4` against RAVEN `develop3` --- each of
these errors before it computes anything. `parity check` cannot see this, because a call to a
function that no longer exists is not a change in either repo's public API; only running the
code finds it, which is exactly what the scenarios are for.

It was not only the parity scenarios this stopped. Running GECKO's own
`geckoCoreFunctionTests` against RAVEN `develop3` errored on `tc0003`, `tc0004`, `tc0007` and
`tc0010`; three further cases called the same functions, so 7 of the suite's 13 cases could not
pass. That was the strongest argument in [GECKO #424], and it was worth checking before
filing: a break in GECKO's own tests needs no parity harness to justify fixing.

Confirmed twice: behind a local no-op stand-in for `progressbar`, before the fix landed, and
again against the merged `develop4` commit itself, with nothing local on the path.
`enzyme_annotation_ectestgem` matches on all six of its checkpoints and all thirteen cases of
`geckoCoreFunctionTests` pass. So this was a build break, not a behavioural divergence --- the
numbers were never in question, only whether the code could run at all. The stand-in is deliberately *not* committed --- shimming it here would hide a break that
every GECKO user on RAVEN `develop3` is hitting too.

## The scenario programme

Ordered by what each one needs, cheapest first. Every tier below is one scenario per row of the
table unless it says otherwise, and each emits checkpoints rather than a single verdict, so the
first stage that diverges is the one to fix.

### Tier 1 --- deterministic, offline, solver-free

| Scenario | Covers | Status |
|---|---|---|
| `ec_model_expansion_ectestgem` | `makeEcModel`, `loadConventionalGEM`, `ModelAdapter` | done, matching |
| `enzyme_annotation_ectestgem` | `applyComplexData`, `getECfromGEM`, `getECfromDatabase` | done, matching |
| `protein_pool_ectestgem` | `setProtPoolSize`, `calculateFfactor`, `loadProtData`, `fillEnzConcs`, `constrainEnzConcs` | done, matching |
| `molecular_weight_sequences` | `calculateMW` | done, red on purpose --- see below |
| `ec_model_io_ectestgem` | `saveEcModel`, `loadEcModel` | done, content matches, layout doesn't --- see below |
| `model_edits_ectestgem` | `addNewRxnsToEC`, `copyECtoGEM`, `setKcatForReactions`, `getReactionsFromEnzyme`, `mapRxnsToConv` | done, matching (plus [GECKO #427]) --- see below |

`molecular_weight_sequences` turned out to carry more than the one documented divergence.
Eighteen sequences, each isolating one variable; all eighteen differ. The twenty standard
residues agree between the tables to the gram-mole --- confirmed, not assumed, since that is
exactly the kind of thing an eighteen-line PASS would have hidden a regression in. What
differs:

- the water-mass constant, `18` against `18.01528`, on every sequence with any residue at all;
- `X` ("any residue"): MATLAB's `126.50`, an unsourced historical constant, against geckopy's
  live mean of its own standard-residue table, `118.885` --- 7.615 Da apart in the table, not
  the 7.11 Da geckopy's own comment claims, worth reconciling one way or the other;
- `B` ("D or N"): MATLAB's pre-rounded `114.60` against geckopy's computed `114.595` --- half a
  hundredth of a Dalton, and not previously documented as a divergence at all, since nothing
  had run the two functions on the same input before this scenario did;
- shape: `calculateMW` matches case-sensitively, so a lowercase letter is ignored like a digit,
  where `calculate_mw` upper-cases first and counts it as a real residue; and `calculateMW`
  returns `18` for a sequence with no recognised residues at all, where `calculate_mw` returns
  `NaN` by design, precisely so an empty sequence cannot read as an 18 Da protein.

`J`, `O`, `U` and `Z` were checked too, and agree exactly --- the divergence is `X` and `B`
specifically, not non-standard codes in general. Filed as [raven-gecko-parity #11], in the
same "measured, not assumed" shape as the RAVEN plan's own divergence write-ups: what the
decision is, not a recommendation, since none of the three questions in it has an answer that
does not amount to picking a reference.

`ec_model_io_ectestgem` turned out to be exactly the GECKO analogue of
`yaml_roundtrip_smallyeast` it was expected to be: `saveEcModel` / `save_ec_model` are thin
wrappers around `writeYAMLmodel` / `write_yaml_model`, `loadEcModel` / `load_ec_model` around
the matching readers, so the divergence already tracked at that layer
([raven-gecko-parity #6]) propagates unchanged. Confirmed rather than assumed, on a freshly
built full ecModel (17 reactions after expansion): the model before any write, and the model
after write-then-read, agree on every field on both sides --- reactions, bounds, gene
associations, stoichiometry, and every `ec.*` array down to the coupling matrix, zero
differences, each side's own round trip independently lossless. The written *file* does not:
352 lines / 6980 characters against 295 / 6011 for the same model, the same 2-space-vs-4-space
layout question one level down, plus a GECKO-specific wrinkle --- `save_ec_model` writes a
`metaData` provenance block (`date`, `geckopy_version`, `description`) that `saveEcModel`
shapes differently. Recorded as a comment on [raven-gecko-parity #6] rather than a new issue:
same open question, not a new one.

One difference from `yaml_roundtrip_smallyeast` worth stating for whoever extends this
scenario: ecTestGEM ships no pre-existing `ecModel.yml`, so this scenario's `direct`
checkpoint is a freshly *built* ecModel, not one read off disk the way `yaml_roundtrip`'s is
from `smallYeast.yml`. Reading a real, larger ecModel --- the tutorial's `ecYeastGEM.yml`,
written by MATLAB --- on both sides remains open, and is a materially different question: it
would test today's readers against a file that may carry the legacy quirks
`raven_toolbox.io.read_yaml_model`'s own docstring says it normalises on load (a top-level
`smiles` field, reverse-direction `usage_prot_*` / `prot_pool_exchange`), none of which a
freshly-built model exercises. Worth its own scenario later, not a substitute for this one.

`model_edits_ectestgem` found the same shape of thing three times over: a real, previously
unknown crash directly in one of its five target functions, plus four small, already-typical
API-shape divergences the individual docstrings had already called out but nothing had run.

The crash: `addNewRxnsToEC` raised `Index in position 2 is invalid` whenever more than one new
reaction in a single call needed isozyme (OR-grRule) expansion --- including one *reversible*
reaction with an isozyme grRule on its own, since the reversibility split duplicates that
grRule onto a second entry before the isozyme split runs. The split loop mutated the arrays it
was iterating over using indices computed before any mutation, so each removal shifted every
later entry's position and a later index silently stopped pointing at the reaction it was
meant to. Fixed in [GECKO #427], merged: compute every split's replacement rows from the original,
unmutated arrays first, remove every original that needed splitting in one indexed operation,
append the replacements after. `geckoCoreFunctionTests.m` had no test for `addNewRxnsToEC` at
all; one is added with the fix. Confirmed against the fix: adding a reversible,
isozyme-catalysed reaction (the exact combination the bug needed) and comparing against
geckopy's `add_new_rxns_to_ec` on the same input, the two agree on the reactions added, the
enzymes added, and every field --- reactions, gene associations, stoichiometry, every `ec.*`
array --- of the resulting model.

The four divergences, each confirmed on the parts that agree as well as the parts that don't:

- `getReactionsFromEnzyme` / `get_reactions_from_enzyme`: the known-enzyme case matches
  exactly. MATLAB matches protein ids case-insensitively and returns empty outputs for an
  unknown one; geckopy is case-sensitive and raises `ValueError` for both a case-mismatched
  known id and a genuinely unknown one.
- `setKcatForReactions` / `set_kcat_for_reactions`: kcat values match exactly for a suffixed
  id and for a base name broadcasting one scalar across its isozymes. `ec.source` reads
  `'setKcatForReactions'` in MATLAB, `'manual'` in geckopy. And MATLAB accepts a per-isozyme
  kcat list for an unsuffixed base name, relying on `ec.rxns` order to line the values up;
  geckopy refuses this and asks for the suffixed ids explicitly.
- `copyECtoGEM` / `copy_ec_to_gem`: filling an empty eccode, and leaving a populated one alone
  under `overwrite=false`, both match exactly. Under `overwrite=true`, MATLAB clobbers an
  existing annotation with an *empty* `ec.eccodes` entry; geckopy treats an empty entry as
  nothing to propagate and never clobbers with emptiness, `overwrite=true` or not.
- `mapRxnsToConv` / `map_rxns_to_conv`: matches exactly, no divergence --- checked with a
  synthetic per-reaction flux vector keyed by id (the alphabetical rank of each ecModel
  reaction's own id, so the comparison never assumes the two sides agree on row order,
  only on the set of ids), rather than a solved flux distribution, keeping the whole
  scenario solver-free.

None of the four is new: every one is already a `MATLAB-COMPAT` comment in geckopy's own
source. What this scenario adds is running the two side by side on the same input, which is
what turns "documented in a comment" into "asserted, and fails if either side moves".

`protein_pool_ectestgem` turned up two real bugs in `calculateFfactor`, both fixed and
**merged** in [GECKO #426]: it called `loadDatabases` for its UniProt database
unconditionally, even when a `protData` struct is supplied directly and that call's result
goes unused, and its documented no-data fallback (`f = 0.5`) was unreachable --- execution
fell through past it and crashed instead of returning. Confirmed on both counts, twice:
before merging, and again against the merged `develop4` commit itself with nothing local on
the path. `runtests('geckoCoreFunctionTests')` passes all fourteen cases including a new one
for the crash, and `protein_pool_ectestgem` matches identically, since the removed call was
never used on the path this scenario exercises. One shape difference remains and is not
worth closing: MATLAB's function still needs a `modelAdapter` in every call, to read
`params.path`, where geckopy's `calculate_f_factor` needs one only when there is no
`prot_data` at all --- harmless, since resolving that path does no I/O of its own.

### Tier 2 --- the kcat chain

One scenario, checkpoint per stage, on ecTestGEM. This is where GECKO's numbers come from and
where a divergence is most expensive to find late.

| Checkpoint | Covers |
|---|---|
| `fuzzy` | `fuzzyKcatMatching`, `loadBRENDAdata` |
| `standard` | `getStandardKcat`, `removeStandardKcat` |
| `dlkcat` | `writeDLKcatInput`, `readDLKcatOutput`, `mergeDLKcatAndFuzzyKcats` |
| `selection` | `selectKcatValue`, `applyCustomKcats`, `getKcatAcrossIsozymes` |
| `constraints` | `applyKcatConstraints` |

Two things to settle before writing it. ~~The BRENDA fixture is in two formats (above), so the
declaration has to name both files and assert they carry the same triples.~~ Settled: both
fixtures are the same five triples and both loaders parse them the same way, confirmed by
execution --- [docs/brenda-reconciliation.md](brenda-reconciliation.md). One gap that reconciliation
surfaced: the ecTestGEM fixture's SA and MW rows don't share an organism, so the SA-derived-kcat
join is untested by either loader on this fixture; the `fuzzy` checkpoint either accepts that gap
or the fixture grows a matching pair first.

The other thing to settle: geckopy records that its BRENDA **search order** differs from
MATLAB's --- MATLAB tries organism-specific specific-activity before some kcat candidates.
Settled, also by execution, also not a divergence: geckopy's search order and its `origin`
output both match MATLAB's exactly ---
[docs/brenda-search-order.md](brenda-search-order.md).

`runDLKcat` is out of scope: it needs the DLKcat container. The scenario reads a stored
`DLKcat.tsv`, exactly as MATLAB's own test does.

**Done: `kcat_chain_ectestgem`.** One flowing ecModel (the stock fixture plus two reactions:
`R2a`, same GPR shape as `R2` but no EC code, so it has to go through DLKcat and isozyme-fill;
`R6`, no GPR at all, the one shape the stock fixture lacks, needed for the
new-standard-pseudo-protein path) walked through all eleven functions in pipeline order,
checkpointed at each stage. Content matches exactly except three confirmed, asserted
divergences:

- **`applyCustomKcats`**, mode A (reaction id only, no protein listed): MATLAB only writes
  `ec.kcat`, leaving `ec.source`/`ec.notes` at whatever they already were; geckopy shares one
  write path across all three modes and always sets `source='custom'` and appends the note.
  Not flagged as a MATLAB-COMPAT note upstream --- found by reading both implementations side
  by side, not from any existing documentation.
- **`selectKcatValue`**, `criteria='median'`/`'mean'`: dead code in MATLAB.
  `[selectedKcats(i),j] = median(...)`/`mean(...)` requests a two-output form neither function
  supports (only `max`/`min` do); confirmed by direct execution to error unconditionally with
  *"Too many output arguments"*. GECKO's own `test/VerificationMatrix.tsv` already flags this
  function as under-tested, and no call site anywhere in the codebase --- including the
  function's own docstring example --- ever passes `criteria='median'`/`'mean'`. geckopy's
  `apply_kcat_list` has no such restriction.
- **`applyKcatConstraints`**, light formulation, partial isozyme coverage: when only some
  isozymes of a reaction have a kcat, MATLAB corrects an unassigned isozyme's `Inf` cost
  (`MW/0`) to `0` *before* taking `min()` across isozymes, so the fabricated zero always wins
  --- silently writing a zero enzyme cost for the whole reaction even though another isozyme has
  a real, valid kcat. geckopy skips invalid isozymes before the comparison instead. Not
  reachable through the shared ecTestGEM fixture (every isozyme there ends up with a kcat by
  the time constraints are applied), so this is a small, isolated, purpose-built model within
  the scenario rather than a fixture addition.

Two more real divergences were found along the way but are not asserted by the scenario, since
neither is reachable through the ecTestGEM fixture without a fixture change that would cost more
than it teaches here: `getStandardKcat`'s per-subsystem kcat is MATLAB's arithmetic mean against
geckopy's median (deliberate on the Python side --- kcats span orders of magnitude, so a mean is
dominated by the largest member --- a >100x difference on a skewed sample; the ecTestGEM fixture
has no `subSystems` data at all, so this code path is currently unreachable on either side), and
`readDLKcatOutput`'s unrecognised-substrate handling is fatal in MATLAB (aborts the whole read)
but a non-fatal per-row drop in geckopy (only the case-sensitivity half of this is a documented
MATLAB-COMPAT note upstream). Both are recorded in `ledgers/gecko.yml`.

Four real bugs were found and fixed along the way, three in files the scenario's own execution
needed to touch, one (below) found the same way but confirmed and fixed separately since it
isn't reachable through the shared fixture:

- `writeDLKcatInput.m` silently wrote **zero rows** for any non-trivial `ecRxns` subset --- the
  ordinary, documented way to call it (e.g. "only the reactions fuzzy matching couldn't find a
  kcat for"). The function reuses the name `ecRxns` for three different index spaces across its
  body; once the substrate/reaction matrix is pre-filtered to the requested subset, later code
  that still treats those as *global* `model.ec.rxns` indices silently selects the wrong rows
  (or, after a first, insufficient fix attempt, the wrong *columns* clear correctly but the
  wrong reaction names get attached to them). Fixed by threading the caller's requested indices
  through explicitly rather than reusing the emptied variable. [GECKO #428], merged.
- `TestGEMAdapter.m`'s `getSpontaneousReactions` referenced an undefined variable
  (`rxns_tsv.rxns`) --- would crash unconditionally, and `getStandardKcat` is the only caller of
  this method anywhere in GECKO, so `getStandardKcat` could never run against `TestGEMAdapter`
  at all. Fixed to `model.rxnNames(spont)`, matching the template adapter's own pattern. That
  alone was not enough: the hardcoded position it set (`spont(5) = true`, valid only for the
  7-reaction *conventional* model) breaks once `getStandardKcat` calls it with the
  already-expanded *ecModel*, where R4's position has moved. Fixed to match by reaction id
  instead, mirroring geckopy's own `TestGEMAdapter.get_spontaneous_reactions` port, which already
  solved this the same way with the same reasoning in its own comment. [GECKO #429], merged.
- `applyKcatConstraints.m`, full formulation: two enzyme rows mapping to the same
  `prot_<accession>` metabolite (distinct genes sharing one UniProt entry) got MATLAB's
  last-write-wins instead of summed, since a plain indexed assignment on a repeated linear index
  in MATLAB keeps only the last value written; geckopy explicitly sums, with its own regression
  test for exactly this. Confirmed by direct execution before either filing or fixing. Not
  reachable through the shared ecTestGEM fixture, so filed separately as [GECKO #430] rather than
  asserted by the scenario, then fixed by accumulating per unique linear index (`unique` +
  `accumarray`, not a naive `accumarray` over the whole matrix, which would allocate a dense
  array sized to it). [GECKO #431], merged, closes [GECKO #430].

`getStandardKcat.m`/`removeStandardKcat.m` had no MATLAB test coverage at all before this ---
`test/VerificationMatrix.tsv` records the former with empty Verification/Comments columns, and
the latter isn't listed there at all. This scenario is the first thing, on either side, to
actually run them.

**Done: `okp_kcat_ectestgem`.** OpenKineticsPredictor (OKP) is the newer, REST-submitted
alternative to DLKcat --- `findMetSmiles` feeding `writeOpenKineticsPredictorInput`'s CSV-building
(both `onlyWithSmiles` branches), then `readOpenKineticsPredictorOutput` parsing a result file
back into a kcat list, on ecTestGEM. Stops at the CSV boundary on both sides rather than the real
OKP API, same reasoning DLKcat's own neural network is out of scope for `kcat_chain_ectestgem`
and `ec_model_full_yeastgem`.

This scenario exists because of a ledger-audit finding, not a gap in the scenario programme's own
plan: `writeOpenKineticsPredictorInput`/`readOpenKineticsPredictorOutput` were filed as
`matlab-only` with no counterpart named, while their real Python counterparts
(`build_okp_input_csv`/`parse_okp_output`) sat separately filed as `python-only` --- four rows
each independently claiming isolation, even though each side's own `reason` text named the other
function. Fixed by re-pairing them as `parity` rows (see `ledgers/gecko.yml`); this scenario then
confirmed the pairing behaviourally.

Content matches exactly except one confirmed, asserted divergence: MATLAB's `kcatSource` prefixes
each entry's provenance with `OKP-` (e.g. `OKP-CataPro`, stripped of OKP's own leading
`Prediction from `); geckopy's `parse_okp_output` keeps the same stripped value un-prefixed
(`CataPro`). Confirmed by direct execution; recorded, not normalized away.

Found and fixed one real MATLAB bug along the way, in the same family as `writeDLKcatInput.m`'s
own subset-indexing bug above --- both functions build a CSV from a caller-chosen `ecRxns`
subset, and both got the subset's own index space confused with `ec.rxns`' absolute one, just in
different ways. `writeOpenKineticsPredictorInput.m` indexed `model.ec.rxnEnzMat` with
`reactionIdxs`, a position *within the requested subset* (`1..numel(ecRxnsIdx)`), instead of
mapping it back through `ecRxnsIdx` to `ec.rxns`' own absolute position
(`1..numel(model.ec.rxns)`). The two only coincide when the subset is "everything, in `ec.rxns`
order" --- any subset excluding an earlier `ec.rxns` entry shifts every later entry's subset
position below its absolute position. Concretely, on ecTestGEM: `ec.rxns` order is `[R2_EXP_1,
R2_EXP_2, R2_REV_EXP_1, R2_REV_EXP_2, R3, R5]`; this scenario's own `write` checkpoint requests
`{R2_EXP_1, R2_EXP_2, R3}`, skipping the two `REV` entries in between, so `R3`'s subset position
(3) no longer equals its absolute position (5) --- the bug read `rxnEnzMat` row 3
(`R2_REV_EXP_1`'s genes) instead of row 5 (`R3`'s own gene): `R3`'s enzyme never appeared in the
output, and an earlier isozyme's genes appeared as a spurious duplicate instead. geckopy's
`build_okp_input_csv` has no equivalent bug, confirmed by direct execution on the identical
subset. Fixed by mapping `reactionIdxs` back through `ecRxnsIdx` before indexing `rxnEnzMat`.
[GECKO #437], merged.

### Tier 3 --- the solver tier

Needs Gurobi, which `nightly.yml` already provisions for the RAVEN pair. Compare at set level
and on magnitudes, not on the exact vertex an LP happened to land on.

| Scenario | Covers |
|---|---|
| `enzyme_usage_ectestgem` | `enzymeUsage`, `reportEnzymeUsage`, `getConcControlCoeffs` |
| `ec_fva_ectestgem` | `ecFVA` |
| `flexibilize_concs_ectestgem` | `flexibilizeEnzConcs`, `constrainFluxData`, `loadFluxData` |
| `sensitivity_tuning_ectestgem` | `sensitivityTuning`, `sigmaFitter`, `findMaxValue`, `truncateValues` |
| `ec_fseof_ectestgem` | `ecFSEOF` |

`ecFSEOF` already carries a recorded divergence on the RAVEN side of the house (slope of |flux|
against endpoint comparison); check whether the ecModel version inherits it before writing the
scenario.

**Done: `enzyme_usage_ectestgem`.** A real LP was the first obstacle, not the last: with both of
ecTestGEM's parallel m1->m2 routes (R2, R4) left open, MATLAB and geckopy each solve to a
*different*, equally optimal vertex of the same LP --- same growth rate to nine significant
figures, different per-protein usage, a different capacity-saturated enzyme --- once real
proteomics data (loaded the same way `protein_pool_ectestgem` does) narrows every protein's own
usage cap and leaves the shared protein-pool budget with slack. That is a genuine degeneracy in
this fixture, confirmed by direct execution, not a bug on either side and not fixable by
choosing different kcats (the pool budget, not the kcats, is what would normally arbitrate
between the routes, and it isn't the binding constraint here). The scenario blocks R2 and R4,
leaving R3 --- ecTestGEM's only single-gene, single-isozyme reaction --- as the sole route,
which removes the degeneracy structurally rather than by tuning around it. With R3 alone, P5's
measured concentration (the tightest of the five) becomes the sole binding constraint on growth,
which is what gives `getConcControlCoeffs` something real to report.

Found and fixed one real MATLAB crash along the way: `reportEnzymeUsage`'s default `topAbsUsage`
(10) indexed past the end of any model with fewer enzymes than that --- ecTestGEM has 5 --- so
the function crashed outright on the default call. [GECKO #432], merged.

One confirmed divergence, asserted rather than avoided: `reportEnzymeUsage`'s `topAbsUsage`
table always returns exactly the requested row count, padding any enzyme with no
flux-carrying reaction with a placeholder row (a `isscalar(find(carriedFlux))` check that treats
"zero reactions carried flux" the same as "more than one," which is arguably itself a second,
smaller bug); `report_enzyme_usage`'s `top_abs_usage` table instead skips such an enzyme outright,
so it can return fewer rows than requested. Both sides agree exactly on every enzyme that does
carry flux. [raven-gecko-parity #18].

`getConcControlCoeffs` carries its own documented algorithmic difference (MATLAB's 2x
finite-difference probe vs. geckopy's default LP-shadow-price read, see geckopy's own
MATLAB-COMPAT note) that this fixture's one cleanly-binding enzyme does not expose --- both
methods agree here because nothing else becomes binding within the probe's 2x range. Recorded
on the ledger row rather than re-demonstrated by a second fixture.

**Done: `ec_fva_ectestgem`.** No new fixture obstacle this time --- unlike enzyme_usage_ectestgem,
FVA does not need a unique optimal point, so R2 and R4 are both left open on purpose, and R2's
two isozymes (`G1 and G2`, forming a complex, or `G3` alone) get distinct kcats to give the
solver a real trade-off between them. That trade-off is exactly what exposes the one confirmed
divergence geckopy's own source already documents (`MATLAB-COMPAT` note, `ec_fva.py`): MATLAB's
`ecFVA.m` reduces each split ec-reaction's own bound with min/max across every canonical
group's LP solve first, then sums the (already independently reduced) forward variants and
subtracts the reverse ones --- the "envelope". geckopy instead reads a canonical reaction's
combined forward-minus-reverse value directly off the one solve that actually optimised it ---
the "diagonal", always a value some single feasible flux distribution attains, where MATLAB's
forward and reverse variants can each be reduced against a different combination of the other,
not necessarily one jointly achievable together. Confirmed by direct execution: every reaction
with a single enzyme or none (`R1`, `R3`, `R4`, `R5`, `S1`, `S2`) agrees exactly; `R2`, the one
isozyme-split reaction, does not --- MATLAB reports `[-3927.27, 0]`, geckopy reports
`[-6000, 3272.73]`. MATLAB's range happens to sit inside geckopy's here, but that is this
fixture's arithmetic, not a general property of the two algorithms, so the ledger and scenario
both describe the mechanism rather than calling one side "tighter".

**Done: `flexibilize_concs_ectestgem`.** Two independent checkpoints. `loadFluxData` +
`constrainFluxData` needed no fixture engineering and turned up no real divergence, only a
corrected suspicion: geckopy's own MATLAB-COMPAT note flags RAVEN's `setParam('var', ...)`
(used for `constrainFluxData`'s percentage-variance mode) as a "soft slack-variable
formulation" that might not match `apply_flux_data_constraints`'s hard bound-set. Read directly
against RAVEN's actual `setParam.m` rather than taken on faith: its `'var'` case just sets
`lb`/`ub` with the same sign-aware arithmetic geckopy already uses --- no slack variable at
all. Confirmed by direct execution: both the `'loose'` and percentage modes match exactly.

`flexibilizeEnzConcs` reuses `enzyme_usage_ectestgem`'s own R2/R4-blocked fixture rather than
deriving a new one, since it already has exactly one unambiguous growth-limiting enzyme (P5) ---
precisely what the "find the worst enzyme by control coefficient, relax it, repeat" loop needs
to run a short, deterministic trajectory rather than risk depending on `getConcControlCoeffs`'s
own separately-documented finite-difference-vs-shadow-price divergence. It didn't: both sides
flex exactly one protein (P5), the same number of times (1), from the same starting
concentration. The divergence that did turn up is downstream of the loop, in the refinement
pass that runs after it: MATLAB's refinement solve pins growth into a narrow band around
`expGrowth` (RAVEN's `setParam('var', bioRxn, expGrowth, 0.5)`, +/-0.25%) and, since the
objective there is to minimise protein-pool usage, settles at the band's low edge rather than
at `expGrowth` itself; geckopy's refinement solve pins growth to `exp_growth` exactly (a
deliberate, already-documented MATLAB-COMPAT choice in `flexibilize_enz_concs.py`). Confirmed
by direct execution: P5's flexed concentration and the final growth rate both differ by a
small, fully explained amount (`flexConcs` 0.173177 vs 0.173611; growth 2.49375 vs 2.5).

Found one bug in this scenario's own harness code, not in either GECKO or geckopy: MATLAB's
`jsonencode` collapses a one-element numeric array (this fixture has exactly one flux-data
condition) to a bare scalar rather than a one-element JSON array --- the same pitfall
`docs/scenarios.md` already warned about for a 1x1 *struct* array, but for plain numbers.
Fixed with `num2cell`, and the doc note extended to cover both cases.

**Done: `sensitivity_tuning_ectestgem`.** Four checkpoints, on the widest range of fixture
shapes any Tier-3 scenario has needed: `sensitivityTuning` and `sigmaFitter` reuse the same
R2/R4-blocked, single-route fixture shape as `enzyme_usage_ectestgem` and
`flexibilize_concs_ectestgem` (each in its own model instance, with its own kcats), while
`findMaxValue` and `truncateValues` need no ecModel or solver at all --- the first takes a
BRENDA-shaped table directly (no file I/O), the second is plain rounding.

`sensitivityTuning` matches exactly: same reaction and enzyme bumped (`R3`/`P4`), the same old
and new kcat. It also corrects a stale comment rather than confirming a fresh one: geckopy's
own `MATLAB-COMPAT` note describes MATLAB as picking the reverse-direction usage reaction with
the *most negative* flux, where geckopy picks the most positive. Read against the actual
`sensitivityTuning.m` on this repo's `develop4`, that description no longer holds --- protein
usage and pool reactions were switched to the forward direction in GECKO#419, after which
MATLAB's own code already reads `[~,sel] = max(drawFluxes)`, the same choice geckopy makes.
Confirmed matching by direct execution, not by re-reading either source a second time.

`sigmaFitter` found a second real MATLAB bug this tier, and it is genuinely a bug, not a
documented choice: the fitted `sigma` value matches exactly (both sides run the identical
100-point grid search --- geckopy's `fit_sigma` called with `method='grid'` rather than its own
faster bisection default, specifically so the two are comparable step for step), but the
*returned model* did not, because the grid-search loop reassigns `model` on every one of its
100 iterations and never re-applies the best-fitting sigma afterward --- so the model coming
back was sized for whichever sigma the loop tried *last* (`sigma=1`), not the one the function
itself reports. On this fixture: `sigma=0.11` both sides; MATLAB's returned pool bound `2000`
(`= Ptot*f*1*1000`) against the correct `220` (`= Ptot*f*0.11*1000`). geckopy's own
`MATLAB-COMPAT` note already flagged this as a known MATLAB bug it deliberately does not
replicate; this scenario is the first time it was confirmed with real numbers rather than
taken on faith. Filed and fixed: [GECKO #433], merged.

`truncateValues` matches exactly across one value per order-of-magnitude regime, a negative
value, and a value small enough to round away to zero.

`findMaxValue` turned up two more confirmed bugs, in a function grep confirms has no callers
anywhere in GECKO --- documented here rather than fixed, the same judgment call
`kcat_chain_ectestgem` made for `selectKcatValue`'s dead `'median'` branch. First, its wildcard
branch never actually matches anything: the EC-prefix slice it builds
(`EC_cell{i}(strfind(EC_cell{i},'-')-1:end)`) keeps only the character immediately before the
dash plus the dash itself, and for any `"X.Y.Z.-"`-shaped wildcard that character is always a
dot, so the search string is always the literal `".-"` --- never a substring of a real EC code.
Second, when neither the kcat nor the SA table matches at all, comparing `0 > 0` is false, so
the function falls into the "SA won" branch and labels the (empty) result `'SA*Mw'` instead of
leaving the parameter blank, the same way geckopy does. Confirmed by direct execution: three of
five queries (two exact matches and a multi-EC query) agree exactly; the wildcard query and the
no-match query both diverge exactly as described.

**Done: `ec_fseof_ectestgem`. Tier 3 is complete.** Red on purpose, and more thoroughly than
any other scenario in either pair: `geckopy.ec_fseof` is a thin wrapper over
`raven_toolbox.analysis.fseof`, not a port of `ecFSEOF.m`'s own algorithm at all, and its own
`MATLAB-COMPAT` notes already said as much before this scenario existed. What those notes did
not say --- and what direct execution on ecTestGEM confirms --- is how *wide* the resulting gap
is, on three separate, independent axes:

1. The enforced production-flux levels themselves differ, before any target selection can even
   begin. MATLAB's `alpha` runs from the biomass-optimal production flux (whatever the target
   reaction naturally carries when only growth is maximised --- `0` here, since the cheaper of
   two isozyme routes covers all of it) up to 90% of the reaction's theoretical maximum.
   `raven_toolbox`'s levels instead run from `target_max/n_steps` to `target_max`, with no
   reference to the biomass-optimal point at all. Confirmed: MATLAB's six levels are
   `[0, 259.2, 518.4, 777.6, 1036.8, 1296.0]`; geckopy's are `[216, 432, 648, 864, 1080, 1296]`
   --- the same top end (both derive it from the same theoretical-maximum solve), a different
   everything else.
2. `ecFSEOF.m` restricts its *candidate search space* to gene-associated reactions only, applied
   before target selection even starts; `raven_toolbox`'s classifier considers every reaction in
   the model. On this fixture that difference alone changes the target list from one reaction to
   six --- uncatalysed and exchange reactions (`R1`, `R4`, `S1`, `S2`) are structurally
   ineligible on the MATLAB side and freely eligible on the Python side.
3. Even restricted to the same candidates, the selection *criterion* differs: MATLAB requires
   `|flux|` to be strictly monotonic across every one of the scan's steps, then keeps only the
   top quartile by slope; `raven_toolbox` regresses flux against the enforced level and keeps
   reactions clearing both a correlation and a slope threshold --- deliberately more tolerant of
   one noisy step from an LP's alternative optima, per its own `IMPROVEMENTS` notes (FS1--FS4).
   This is the same divergence already recorded on the RAVEN pair itself, for `FSEOF` vs
   `raven_toolbox.analysis.fseof` directly (`docs/behaviour-parity-plan.md`'s "Divergences to
   encode, not fix" table, "slope of \|flux\| vs endpoint comparison") --- confirmed here, for
   the first time, to carry all the way through both ecModel-specific wrappers too.

Confirmed by direct execution: MATLAB finds exactly one target (`R5`) on this fixture; geckopy
finds six (`R1`, `R3`, `R4`, `R5`, `S1`, `S2`). Output *shape* differs further still and is not
asserted at all, since geckopy's side has nothing to compare it against: `ecFSEOF.m`
additionally computes a per-gene essentiality column (one knockout LP per gene) and splits
results into `rxnTargets` vs `transportTargets`; `ec_fseof` does neither, pointing callers at
`cobra.flux_analysis.single_gene_deletion` and a subsystem/metabolite check instead.

### Tier 4 --- a real model

ecTestGEM proves the functions agree on every behaviour MATLAB itself pins down. It does not
prove they agree on yeast-GEM: 7 reactions leave a divergence nowhere to hide. The GECKO
tutorial ships `yeast-GEM.yml`, so a slow job --- separate from the nightly, as the RAVEN plan
says for its genome-scale comparison --- compares a full `makeEcModel` and a full BRENDA-based
kcat assignment against it.

**Done: `ec_model_full_yeastgem`**, in its own workflow
(`.github/workflows/gecko-genome-scale.yml`, weekly). DLKcat is out of scope --- a separate
neural-network tool with its own PyTorch environment, not part of GECKO or geckopy, and BRENDA
fuzzy matching alone is already a substantial genome-scale test of the shared pipeline. Two
pieces of scenario-side data preparation were needed that no ecTestGEM-scale scenario in this
pair has needed before: `cobra.io.load_yaml_model` (what `load_conventional_gem` calls for a
`.yml` file) does not populate `reaction.annotation['ec-code']` from yeast-GEM.yml's own
`eccodes` reaction field, confirmed by direct execution --- the Python side reads the file a
second time with a plain YAML parse to recover it, restoring parity input rather than working
around a divergence in what is compared. And `fuzzyKcatMatching`'s organism-closeness
escalation needs a real KEGG taxonomy artefact this repo does not vendor or download; a small,
purpose-built two-organism `PhylDist.mat` stand-in (`YeastGEMAdapterParity.m`) exercises the
same code path without it, at the cost of leaving that one escalation tier under-exercised ---
see below.

This scenario justified itself immediately: it found and fixed two real, generalizable MATLAB
bugs neither reachable through any fixture small enough to avoid them by chance.

- **`sigmaFitter.m`** returned a model sized for the wrong sigma --- its 100-point grid-search
  loop never re-applies the best-fitting sigma after the loop ends, so the returned model was
  sized for whichever sigma was tried last (`sigma=1`), not the one the function itself
  reports. Found while building `sensitivity_tuning_ectestgem` (Tier 3), not this scenario ---
  see there for the full account. [GECKO #433], merged.
- **`fuzzyKcatMatching.m`**'s wildcard EC search matched a substring instead of a prefix: its
  optimized path (used on every real call) searched for whether a truncated EC prefix like
  `1.` appeared *anywhere* in a candidate EC string, not just at the start, so a query for
  enzyme class 1 also matched an unrelated class-4 code that happened to contain the same two
  characters elsewhere (`4.2.1.1` contains `1.` between its third and fourth levels). Confirmed
  by direct execution against real BRENDA data: fixing this changed the matched kcat for
  hundreds of yeast-GEM reactions. [GECKO #434], merged.

With both fixes applied, two confirmed divergences remain. `getECfromGEM`'s ledger row has the
first: `fill_eccodes_from_gem`'s EC-string validation is stricter than MATLAB's (none at all),
dropping 36 of 4671 reactions' kcats entirely, including real BRENDA "new/undefined subclass"
codes like `1.1.1.n12`. The second is a further ~119 reactions whose matched kcat *value*
differs on each side without either being missing --- the leading hypothesis, not exhaustively
confirmed for every one of the 119, is that this scenario's own necessarily sparse
two-organism `PhylDist.mat` stand-in makes the organism-closeness escalation tier close to
arbitrary at genome scale (both sides' organism-filtering logic were read side by side and are
faithful ports of each other), rather than a third algorithmic difference. See
`scenarios/ec_model_full_yeastgem/scenario.yml` for the full account of both.

Do this only after tiers 1 and 2 are green. A whole-model diff on top of an unchecked base
reports hundreds of differences with one cause. Tier 3 finished first, so all four preceded
this.

## The GECKO nightly

Done: `nightly.yml` runs both pairs now, as two entries in one matrix, one at a time rather
than in parallel --- both entries commit `nightly/` back to this repo, and a concurrent push
from the other entry would race it, which running sequentially avoids without needing retry
logic. Each writes its own state and report (`nightly/state.json` / `nightly/report.md` for
raven, unchanged; `nightly/gecko-state.json` / `nightly/gecko-report.md` for gecko), so
neither entry's history overwrites the other's.

**A gecko run is a four-repo job.** geckopy depends on raven-toolbox (`git+...@develop`, not yet
on PyPI), and GECKO depends on RAVEN on the MATLAB side. Installing geckopy from its own
metadata would pull raven-toolbox's `develop` HEAD, which is *not* necessarily the revision
`parity.toml` tracks, and the MATLAB side needs a RAVEN checkout on the path regardless. So the
gecko entry checks out all four repos and installs raven-toolbox from the checkout before
geckopy (`pip install --no-deps` on geckopy itself, then its other dependencies read out of its
own `pyproject.toml` rather than duplicated by hand, so the workflow cannot drift out of sync
with them), or it would be comparing against something it did not record. `parity.toml` already
resolves the MATLAB half of this: the gecko pair's `setup` names `{raven_matlab}`, so RAVEN goes
on the MATLAB path from wherever that pair is configured, including a `parity.local.toml`
override. RAVEN and raven-toolbox are checked out unconditionally, in both matrix entries, so
the gecko entry always has them available even though raven is not the pair under test there.

`parity refs --format shell` gained a `<pair>_<side>_repo=` line alongside its existing `_ref=`
one while building this, so the workflow can check out or `git ls-remote` a pair without a
second, hand-maintained copy of its repo name --- `parity.toml` stays the one place that fact
is written down.

The **red from its first night** worry the plan carried here is gone: [RAVEN #623] was followed
up in [GECKO #425], merged before this joined the nightly. What is red instead is exactly the
seven scenarios that are red on purpose --- `molecular_weight_sequences`, `ec_model_io_ectestgem`,
`ec_fseof_ectestgem` (nearly all of it) and (one or a few fields each of)
`enzyme_usage_ectestgem`, `ec_fva_ectestgem`, `flexibilize_concs_ectestgem` and
`sensitivity_tuning_ectestgem` --- the same shape of "red is the correct, documented answer"
the raven nightly has already lived with since
`yaml_roundtrip_smallyeast` and
`task_checking_smallyeast`.

## Order of work

1. ~~Prove the pattern on the smallest deterministic thing: the expansion.~~ Done
   (`ec_model_expansion_ectestgem`), matching.
2. ~~The annotation layer.~~ Done (`enzyme_annotation_ectestgem`), matching.
3. ~~**Report the `progressbar` break to GECKO.**~~ Filed as [GECKO #424], fixed by
   [GECKO #425], merged to `develop4`. Everything in tiers 2 and 3 runs through
   `loadDatabases` or `fuzzyKcatMatching`, so this unblocks more of the programme than it
   looks like it does.
4. ~~Protein pool.~~ Done (`protein_pool_ectestgem`), matching. ~~Molecular weight.~~ Done
   (`molecular_weight_sequences`), red on purpose --- filed as [raven-gecko-parity #11].
   ~~ecModel I/O.~~ Done (`ec_model_io_ectestgem`), content matches, layout doesn't --- folded
   into [raven-gecko-parity #6]. ~~Model edits.~~ Done (`model_edits_ectestgem`), matching
   behind [GECKO #427], merged. Tier 1 is complete.
5. ~~Extend `nightly.yml` to the gecko pair.~~ Done: a second matrix entry, four-repo
   checkout, its own state/report files.
6. ~~The BRENDA fixture.~~ Confirmed equivalent ([docs/brenda-reconciliation.md](brenda-reconciliation.md)).
   ~~The search-order question.~~ Confirmed matching, also by execution
   ([docs/brenda-search-order.md](brenda-search-order.md)). ~~The kcat chain.~~ Done
   (`kcat_chain_ectestgem`), matching except three confirmed, asserted divergences; found and
   fixed four real MATLAB bugs along the way (`writeDLKcatInput.m`'s subset selection,
   `TestGEMAdapter.m`'s spontaneous-reaction detection twice over, `applyKcatConstraints.m`'s
   duplicate-accession summation). ~~OKP.~~ Done (`okp_kcat_ectestgem`), matching except one
   confirmed, asserted divergence; re-paired three ledger rows that were wrongly filed
   one-sided on both sides at once, and found and fixed a fifth real MATLAB bug, the same
   family as `writeDLKcatInput.m`'s own (`writeOpenKineticsPredictorInput.m`'s subset
   indexing, [GECKO #437]). Tier 2 is complete.
7. The solver tier. ~~`enzyme_usage_ectestgem`.~~ Done, matching except one confirmed, asserted
   divergence ([raven-gecko-parity #18]); found and fixed one real MATLAB crash along the way
   (`reportEnzymeUsage.m`'s unclamped `topAbsUsage` indexing, [GECKO #432], merged).
   ~~`ec_fva_ectestgem`.~~ Done, matching except one confirmed, already-self-documented
   divergence (the isozyme-split envelope-vs-diagonal difference geckopy's own `ec_fva.py`
   already names). ~~`flexibilize_concs_ectestgem`.~~ Done: `loadFluxData`/`constrainFluxData`
   match exactly in both bound-setting modes (correcting an over-cautious MATLAB-COMPAT
   note); `flexibilizeEnzConcs` matches except one confirmed, already-self-documented
   divergence in its post-loop refinement pass. ~~`sensitivity_tuning_ectestgem`.~~ Done:
   `sensitivityTuning` and `truncateValues` match exactly (the former also correcting a
   stale MATLAB-COMPAT note, obsoleted by GECKO#419); found and fixed one real MATLAB bug
   along the way (`sigmaFitter.m` returning a model sized for the wrong sigma, [GECKO
   #433], merged); `findMaxValue` confirmed two more bugs, in a function with no callers
   anywhere in GECKO, documented rather than fixed. ~~`ec_fseof_ectestgem`.~~ Done, red on
   purpose on nearly everything it reports: the enforced-flux levels, the candidate search
   space, and the selection criterion all differ, the last of which is the same divergence
   already recorded for `FSEOF` on the RAVEN pair itself, now confirmed to carry through
   both ecModel-specific wrappers too. **Tier 3 is complete.**
8. ~~A real model, in a slow job.~~ Done: `ec_model_full_yeastgem`, its own weekly workflow
   (`gecko-genome-scale.yml`). Found and fixed two real MATLAB bugs
   (`sigmaFitter.m`, [GECKO #433]; `fuzzyKcatMatching.m`'s wildcard substring match,
   [GECKO #434]); both merged into `develop4`. Two confirmed divergences remain (EC-validation strictness; kcat-value
   differences on ~119 reactions, most likely a fixture-sparsity artifact rather than a
   third algorithmic difference). See Tier 4 above.

## Open questions

- ~~**Does GECKO `develop4` target RAVEN `develop3`?**~~ Answered while fixing the break, and
  the answer was hiding in GECKO's CI: its `Checkout RAVEN` step took no `ref`, so it tested
  against RAVEN's *default* branch, `main`. That is a release branch against a development one
  --- exactly the mistake `parity refs` exists to prevent --- and it is why the break was green
  in CI while `develop3` users could not call `applyComplexData` at all. [GECKO #425] pins it to
  `develop3`, which is what `parity.toml` already assumed.
- **Which ecModel YAML layout is the target?** The same question RAVEN's plan asks about
  `writeYAMLmodel`, and the answers should not diverge: geckopy writes the `ec-*` sections
  through raven-toolbox's writer, so whatever is decided there decides this too.
- **Is the BRENDA search-order difference deliberate?** It changes which kcat a reaction gets,
  which changes every flux downstream. Answering it is a prerequisite to tier 2, not part of it.
- **How much of MATLAB's multi-output API is a divergence worth asserting?** `applyComplexData`
  returns `foundComplex` / `proposedComplex` tables that geckopy only logs; `applyCustomKcats`
  and `findMetSmiles` are the same shape of difference. None of it changes a model, so no
  scenario can see it --- it belongs on the ledger rows, and today only some of it is there.

[RAVEN #623]: https://github.com/SysBioChalmers/RAVEN/pull/623
[GECKO #424]: https://github.com/SysBioChalmers/GECKO/issues/424
[GECKO #425]: https://github.com/SysBioChalmers/GECKO/pull/425
[GECKO #426]: https://github.com/SysBioChalmers/GECKO/pull/426
[raven-gecko-parity #11]: https://github.com/SysBioChalmers/raven-gecko-parity/issues/11
[raven-gecko-parity #6]: https://github.com/SysBioChalmers/raven-gecko-parity/issues/6
[GECKO #427]: https://github.com/SysBioChalmers/GECKO/pull/427
[GECKO #428]: https://github.com/SysBioChalmers/GECKO/pull/428
[GECKO #429]: https://github.com/SysBioChalmers/GECKO/pull/429
[GECKO #430]: https://github.com/SysBioChalmers/GECKO/issues/430
[GECKO #431]: https://github.com/SysBioChalmers/GECKO/pull/431
[GECKO #432]: https://github.com/SysBioChalmers/GECKO/pull/432
[raven-gecko-parity #18]: https://github.com/SysBioChalmers/raven-gecko-parity/issues/18
[GECKO #433]: https://github.com/SysBioChalmers/GECKO/pull/433
[GECKO #434]: https://github.com/SysBioChalmers/GECKO/pull/434
[GECKO #436]: https://github.com/SysBioChalmers/GECKO/pull/436
[GECKO #437]: https://github.com/SysBioChalmers/GECKO/pull/437
