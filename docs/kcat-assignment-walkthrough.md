# Walk-through: gathering and assigning kcats (target)

How a GECKO (MATLAB) user works once `kcat-assignment-plan.md` is
implemented. geckopy works the same way with `snake_case` names. File
contents are illustrative.

## 1. The project

`createGECKOproject` writes `model_adapter.toml` with a `[kcat_assignment]`
section and an empty `data/kcats/` folder:

```toml
[kcat_assignment]
preset = "gecko_median"
isozymes = true     # fill reactions without a kcat from their isozymes
standard = true     # give the rest the standard kcat
```

```matlab
adapter = ModelAdapterManager.setDefault(projectPath);
ecModel = makeEcModel(model);
ecModel = getECfromDatabase(ecModel);
ecModel = findMetSmiles(ecModel);
```

## 2. Gather

Gather what the configuration needs; repeat until nothing is pending:

```matlab
updateKcatSources(ecModel);
```

It checks the requirements of every source first (Docker, API key,
MMseqs2) and reports them together, runs the `kcatsFrom<Source>`
functions for missing or outdated files, and lists what is still pending
(an OpenKineticsPredictor job).

Or gather one source at a time, with its own options:

```matlab
kcatsFromBrenda(ecModel, 'aggregation', 'median');   % -> data/kcats/brenda.tsv
kcatsFromDLKcat(ecModel, 'run', true);               % -> data/kcats/dlkcat.tsv (Docker)
kcatsFromOKP(ecModel, 'method', 'CataPro');          % -> data/kcats/okp_catapro.tsv when the job is done
kcatsFromECTree(ecModel);                            % -> data/kcats/ec_tree.tsv
kcatsFromHomologs(ecModel);                          % -> data/kcats/homologs.tsv (MMseqs2)
```

Each writes its file by default and returns the kcat list. A file looks
like this:

```
# source: brenda
# generator: kcatsFromBrenda (GECKO 4.1.0)
# parameters: {"aggregation":"median"}
# data: brenda-2026.1-1
# kind: gathered
# created: 2026-10-20T09:14:02Z
rxn	enzymes	substrate	kcat	log10_sd	source	detail	ec_code	note
r_0534	P04806	D-glucose; ATP	164		brenda	wc=0; origin=1	2.7.1.1	
r_0886	P16861 + P16862	D-fructose 6-phosphate; ATP	214		brenda	wc=0; origin=2	2.7.1.11	
```

Rows are keyed by conventional reaction and enzyme set, not by
`ec.rxns`, so the file stays valid when the ecModel is rebuilt or when
switching between the full and light model. With the project in git,
`git diff` shows what changed when a source is gathered again.

`saveKcatSource(ecModel, kcatList, 'mylist')` keeps any other kcat list.

## 3. Curated kcats

`data/kcats/custom.tsv` holds hand-curated values in the same format,
marked `# kind: curated`; nothing writes to it. A row without `rxn`
applies to every reaction of its enzyme set. Light models get these
values too. An old `data/customKcats.tsv` is converted once with
`convertCustomKcats`.

## 4. Look at a source (optional)

```matlab
[records, meta] = readKcatSource(fullfile(projectPath,'data','kcats','brenda.tsv'));
[kcatList, report] = loadKcatSource(ecModel, 'brenda');
report.unmatched     % file rows that fit no reaction of this model
report.partial       % rows whose enzymes only partly match a reaction
```

## 5. Choose the order

A preset, or stages for full control:

```toml
[kcat_assignment]
isozymes = true
standard = true

[[kcat_assignment.stage]]
action = "select"   # per reaction, the first listed source with a value wins
sources = ["custom", "database_top", "okp_catapro", "dlkcat", "database_bottom"]

[kcat_sources.brenda]
aggregation = "median"
```

`select` understands source names and the BRENDA tiers `database_exact`,
`database_top` and `database_bottom`; `combine` averages sources by their
uncertainty (EC tree and homologs).

## 6. Decide, then assign

```matlab
[decisions, report] = collectKcats(ecModel);   % no change to the model
ecModel = assignKcats(ecModel);                % collectKcats + write + constraints
```

`collectKcats` writes `output/<model>_kcatDecisions.tsv`:

```
ecRxn          stage  source        kcat   candidates  spread_log10
r_0534_EXP_1   1      database_top  164    2           0.00
r_0886         1      dlkcat        31.2   1
r_1027         iso    isozymes      12.0   0
r_2045         std    standard      13.7   0
```

`assignKcats` writes `ec.kcat` and `ec.source`, records one change-log
entry and applies the kcat constraints. To try another order, edit the
TOML and run `assignKcats` again; nothing is gathered twice.

## 7. Rebuild

After a change to the conventional model, run `makeEcModel` and go
straight to `assignKcats`; the files in `data/kcats/` still apply, and
rows that no longer fit are reported.

## 8. After assignment

Unchanged: fit σ with `sigmaFitter` for the level, then tune with
`sensitivityTuning` or `cmaesKcatTuning`. Tuned values stay in the model
and in `ec.source`; files in `data/kcats/` are never written from the
model.
