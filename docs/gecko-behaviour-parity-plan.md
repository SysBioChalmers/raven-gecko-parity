# Plan: behavioural parity for GECKO ↔ geckopy

The gecko ledger carries **47 rows marked `parity`** and, until now, no scenario at all: every
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

Five scenarios, fourteen of the 47 rows. Four run on GECKO's own unit-test model and agree
on content, so the base of the pipeline --- the expansion into an ecModel, the annotation of
its `ec` substructure, the protein budget that limits it, and now the save/load round trip
--- is checked rather than assumed. `enzyme_annotation_ectestgem` was blocked until
[GECKO #425] merged; see below for what that was. The other two are red by design:
`molecular_weight_sequences` on every one of its eighteen sequences ([raven-gecko-parity #11]),
and `ec_model_io_ectestgem` on the written file's layout only, not its content
([raven-gecko-parity #6], one level down from where it was already tracked).

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
| `model_edits_ectestgem` | `addNewRxnsToEC`, `copyECtoGEM`, `setKcatForReactions`, `getReactionsFromEnzyme`, `mapRxnsToConv` | queued |

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

Two things to settle before writing it. The BRENDA fixture is in two formats (above), so the
declaration has to name both files and assert they carry the same triples. And geckopy records
that its BRENDA **search order** differs from MATLAB's --- MATLAB tries organism-specific
specific-activity before some kcat candidates --- which, if it survives contact with the
fixture, is a divergence to assert rather than a bug to fix. Confirm which it is before the
scenario is written, not after it goes red.

`runDLKcat` is out of scope: it needs the DLKcat container. The scenario reads a stored
`DLKcat.tsv`, exactly as MATLAB's own test does.

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

### Tier 4 --- a real model

ecTestGEM proves the functions agree on every behaviour MATLAB itself pins down. It does not
prove they agree on yeast-GEM: 7 reactions leave a divergence nowhere to hide. The GECKO
tutorial ships `yeast-GEM.yml` and the ecModels built from it at three stages, so a slow job
--- separate from the nightly, as the RAVEN plan says for its genome-scale comparison --- can
compare a full `makeEcModel` and a full kcat assignment against MATLAB's stored output.

Do this only after tiers 1 and 2 are green. A whole-model diff on top of an unchecked base
reports hundreds of differences with one cause.

## What a GECKO nightly needs

`nightly.yml` runs the raven pair today, and the gecko pair is a matrix entry away from joining
it --- with one wrinkle that is not obvious:

**A gecko run is a four-repo job.** geckopy depends on raven-toolbox (`git+...@develop`, not yet
on PyPI), and GECKO depends on RAVEN on the MATLAB side. Installing geckopy from its own
metadata would pull raven-toolbox's `develop` HEAD, which is *not* necessarily the revision
`parity.toml` tracks, and the MATLAB side needs a RAVEN checkout on the path regardless. So the
job has to check out all four repos and install raven-toolbox from the checkout before geckopy,
or it is comparing against something it did not record. `parity.toml` already resolves the
MATLAB half of this: the gecko pair's `setup` names `{raven_matlab}`, so RAVEN goes on the
MATLAB path from wherever that pair is configured, including a `parity.local.toml` override.

Two smaller ones: `nightly/state.json` already keys revisions by pair, so change detection
generalises without a schema change; and a gecko run would be **red from its first night** until
[RAVEN #623] is followed up in GECKO. That is the correct behaviour --- the break is real ---
but it is a decision to take deliberately rather than discover.

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
   into [raven-gecko-parity #6]. `model_edits_ectestgem` is what is left of tier 1.
5. Extend `nightly.yml` to the gecko pair, once step 3 has a resolution.
6. The kcat chain, after settling the BRENDA fixture and the search-order question.
7. The solver tier.
8. A real model, in a slow job.

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
