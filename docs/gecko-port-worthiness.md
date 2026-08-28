# Is the gecko ledger's one-sided half worth porting?

`ledgers/gecko.yml` carries 57 rows with no counterpart on the other side --- 3 `matlab-only`,
54 `python-only` (down from 61/5/56 after the OpenKineticsPredictor pair turned out to be
mis-filed; see the ledger's own history). "One-sided" does not mean "gap": most of this is a
language-idiom difference, not missing functionality. This is a pass over all 57, grouped by
*why* each is one-sided, with a verdict on whether porting it would buy anything.

## The short answer

Almost none of it is worth porting as literal, symmetrical translation. Two things are worth
doing, one of them for free:

1. **Merge `feat/geckopy-compat`'s `submitOpenKineticsPredictor.m` / `fetchOpenKineticsPredictor.m`
   into `develop4`.** These already exist, written, on a branch 84 commits ahead of `develop4`
   (see the ledger's `matlab-pending` rows for `geckopy.submit_open_kinetics_predictor` /
   `geckopy.fetch_open_kinetics_predictor`). Closes two ledger rows with zero new code.
2. **Consider extracting `makeEcModel.m`'s build steps into standalone functions**, matching
   `geckopy.ec_model.pipeline`'s 10 exported steps. This is the one category with a real,
   user-facing capability gap behind it (see below) --- and the one genuinely expensive item on
   this list.

Everything else below is either a language feature MATLAB has no equivalent for (dataclasses,
pydantic validation, a class-based model object), or genuinely dead/legacy code better removed
than ported. Where removal is the right call, that's noted per category.

## Not worth porting: language-idiom differences (41 of 57 rows)

These exist *because* Python and MATLAB structure code differently, not because one side has
capability the other lacks. Porting any of them means inventing a language feature MATLAB
doesn't have, for a behaviour both sides already agree on.

**Dataclass return types (10 rows)** --- `AddNewRxnsResult`, `EnzymeUsageReport`,
`EnzymeUsageResult`, `FlexEnzResult`, `GreedyRelaxResult`, `MapRxnsResult`, `NewEnzyme`,
`RelaxationStep`, `SigmaFitterResult`, `TunedKcatsResult`. Each wraps the return value of a
function that already has its own `parity` row. MATLAB's `[model, a, b] = f(...)` multi-output
convention *is* MATLAB's version of this --- there's nothing to add.

**Loaded-data container types (9 rows)** --- `BrendaData`, `ComplexPortalEntry`,
`DLKcatIgnoreLists`, `FluxData`, `KeggDB`, `PhylDist`, `ProtData`, `UniprotDB`,
`databases.brenda.Row`. Same reasoning: MATLAB passes parallel cell arrays and structs; these
are the dataclass wrapper around exactly that.

**Adapter plumbing (6 rows)** --- `adapter.ComplexParams`, `adapter.KeggParams`,
`adapter.UniprotParams`, `ModelParameters`, `adapter.resolve_adapter`, `adapter.resolve_param`.
pydantic-validated parameter groups; MATLAB reads the same values off `ModelAdapter` classdef
properties, which already validates by virtue of being a typed class. Porting this means
building a validation framework MATLAB has no use for.

**The model-object trio** --- `EcData`, `EcModel`, `Enzyme`. Not individually portable at all:
this is the single deepest structural difference between the two toolboxes (a RAVEN struct with
an `ec` field vs. a `cobra.Model` subclass with typed accessors), not a missing function. Treat
it as the one fact that explains why so much of this list exists, not as 3 to-do items.

**`ModelAdapterManager`** (matlab-only) --- already a *documented, deliberate* divergence, not
an oversight: geckopy has no global default adapter by design (pass `adapter=` explicitly).
Confirmed correctly classified in the audit that produced this doc. Not worth porting; porting
it would undo the design choice.

**`plotEcFVA`** (matlab-only) --- confirmed via source search: no Python plotting helper exists
anywhere in geckopy, and the migration doc is explicit that this is deliberate (plot the
`ec_fva` DataFrame directly with matplotlib/seaborn). Not worth porting: the replacement is one
line of user code, not a missing capability.

## Worth removing, not porting (3 rows)

**`updateProtPool`** (matlab-only) --- its own ledger reason already says it: obsolete since
GECKO 3.2.0, superseded by `setProtPoolSize`. Not a porting question at all; the actionable item
is removing it from MATLAB, the same call already made for the legacy BRENDA scraper
([GECKO #436]).

**`databases.brenda.aggregate_and_write` / `parse_brenda_json`** --- part of geckopy's BRENDA
JSON-to-TSV refresh pipeline. GECKO briefly had a generator of its own
(`src/geckopy/brenda_parser/`, a 2018 BRENDA-SOAP scraper, invisible to a `.m`-only ledger scan)
but it produced a different raw format from a since-defunct BRENDA access method, showed no sign
of maintenance, and is now removed ([GECKO #436]). Porting geckopy's JSON-based refresh to
MATLAB would just be a second implementation of the same maintenance job; cross-toolbox use
(run geckopy's refresh, GECKO reads the resulting snapshot the way it always has) is the
practical answer, and is now what `databases/README.md` says.

## Worth doing, small effort (6 rows)

**Explicit data loaders** --- `download_kegg`, `download_uniprot`,
`load_complex_portal_json`, `load_dlkcat_ignore_lists`, `load_pax_db`, `load_uniprot_tsv`,
`load_kegg_tsv`, `load_phyl_dist`. All exist in MATLAB today, just inlined inside the one
function that consumes each file rather than exposed as a standalone, reusable, independently
testable entry point (`loadDatabases.m` for most; `urlwrite`/local subfunctions for the two
downloaders). Real but modest value, concentrated in two of these:

- `download_kegg` / `download_uniprot` as standalone MATLAB functions would let a user refresh
  *one* snapshot without re-running all of `loadDatabases.m`. A genuine, if small,
  quality-of-life gap.
- The five plain file-readers (`load_pax_db`, `load_phyl_dist`, `load_uniprot_tsv`,
  `load_kegg_tsv`, `load_complex_portal_json`, `load_dlkcat_ignore_lists`) buy less: each has
  exactly one caller today, and extracting them mainly helps *testing* the loader in isolation
  rather than anything an end user would notice. Worth doing opportunistically (next time
  someone is already editing the relevant `.m` file), not worth a dedicated effort.

**kcat-pipeline helpers** --- `gather_kcats.extract_enzyme_substrate_pairs`,
`gather_kcats.format_kcat_source`, `gather_kcats.normalize_source`. Same shape as the loaders,
smaller scope: each is one helper geckopy exports alongside an already-parity-matched function
(`write_dlkcat_input`, `apply_kcat_list`, `merge_kcats` respectively), where MATLAB keeps the
same logic inline. Low effort, low value --- nice-to-have if touching the surrounding file for
another reason.

## Worth doing, real effort (11 rows)

**`ec_model.pipeline`'s 10 `make_ec_model` build steps** --- `add_protein_pool_exchange_reaction`,
`add_protein_pool_pseudometabolite`, `add_protein_pseudometabolites`,
`add_protein_usage_reactions`, `allocate_ec_and_coupling_light`,
`allocate_ec_for_catalyzed_reactions`, `build_rxn_enzyme_coupling`,
`invert_backwards_only_reactions`, `populate_enzyme_data`, `remove_pseudoreaction_gprs`,
`split_light_rxn_id`. This is the one category on this list with a genuine, user-facing
capability gap behind it: `makeEcModel.m` is one large function, and a MATLAB user who wants to
customize ecModel construction --- skip a step, reorder two of them, substitute their own
enzyme-coupling logic --- has to fork the whole thing. A geckopy user can already do this by
calling the pipeline steps directly. Splitting `makeEcModel.m` into composable pieces without
changing its external behaviour is real engineering work (11 extraction points, each needing its
own regression coverage), not a quick win --- worth scoping as its own effort if MATLAB-side
pipeline extensibility is something the project wants, not something to fold into an unrelated PR.

## Infrastructure, correctly one-sided (3 rows)

**`gather_kcats.OKPClient` / `OKPError`** --- an HTTP client wrapper. Not worth porting on its
own terms (MATLAB's file-based OKP flow doesn't need an HTTP client), and the real gap here
isn't "port the client" --- it's that MATLAB's own REST-capable equivalents
(`submitOpenKineticsPredictor.m` / `fetchOpenKineticsPredictor.m`) already exist, unmerged, on
`feat/geckopy-compat`. See the short answer above.

[GECKO #436]: https://github.com/SysBioChalmers/GECKO/pull/436
