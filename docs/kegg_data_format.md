# KEGG relational-table storage format

This records *why* the published KEGG-derived relational tables --- consumed by both
raven-toolbox and MATLAB RAVEN --- are gzipped TSV, and what other options were
deliberately deferred. It covers the maintainer-built KEGG artefacts: the
`ko_reaction`, `organism_gene_ko`, KO-name, and reaction-flag tables. The pipeline
that builds them is implemented in raven-toolbox (Python) --- see
[Maintaining KEGG data](maintaining_kegg_data.md) --- but the output format choice
below is a shared decision, since MATLAB RAVEN reads the same published files.

The reference GEM itself is stored as **gzipped RAVEN/cobra YAML**
(`reference_model.yml.gz`) --- RAVEN-native and MATLAB-readable, gzipped to match the
tables (the YAML I/O transparently gzips on a `.gz` suffix). On the real KEGG dump
this is ~1.1 MB (vs ~30 MB as SBML) for the full 12k-reaction gene-free model.

End users do not build any of this: the published artefacts are fetched and cached
under `~/.cache/raven-toolbox/data/kegg-<version>/` by raven-toolbox's `ensure_data`
on the Python side, or downloaded directly by `getKEGGModelForOrganism` on the MATLAB
side (see [Artefact hosting & publishing](artefact_hosting.md)). The core tables and
the reference model are distributed together as a single `<version>_core.tar.gz`;
the per-file format below is unchanged. The HMM libraries and the `taxonomy` file are
separate, individually-fetched artefacts.

## Decision (current)

- **All tables** (`ko_reaction`, `ko_names`, `rxn_flags`, and the large
  `organism_gene_ko`): **gzipped TSV (`.tsv.gz`)**. Published assets are
  version-prefixed, e.g. `kegg116_organism_gene_ko.tsv.gz`.
- The large `organism_gene_ko` table keeps its rows **sorted by `(organism, gene)`**.

Why everything is gzip --- even the big table. `organism_gene_ko` carries KEGG's
~9M gene↔KO associations and dominates the artefact set. Sorting by
`(organism, gene)` before writing makes gene IDs from one organism adjacent
(shared locus-tag/numeric prefixes), which both helps the compressor and matches
the by-organism query pattern in raven-toolbox's `get_kegg_model_for_organism` /
MATLAB's `getKEGGModelForOrganism`; the sort is an external merge sort bounded to
`chunk_rows` in memory, so it stays scalable. On the real dump this lands around
~74 MB.

The table was previously xz-compressed (≈27 MB, ~2.9× smaller). It was switched to
**gzip** so the *same* artefact is readable by MATLAB's built-in `gunzip` with no
external tool --- the artefacts are shared with MATLAB RAVEN, and `.xz` would force
an external `xz`/`unxz` dependency on the MATLAB side, which has none today. The
size cost (~74 vs ~27 MB on a once-per-release download) buys a dependency-free,
cross-tool, cross-platform read; xz's larger dictionary is not worth a MATLAB
toolchain requirement.

- **Python:** pandas reads/writes gzip with zero extra dependencies --- compression
  is inferred from the `.gz` suffix; `gzip` is stdlib, so this works natively on
  Windows, macOS, and Linux with no external binary.
- **MATLAB:** `readtable` reads every table after a built-in `gunzip`, with no
  external binary on any platform.

## Options considered

| Format | Python cost | MATLAB cost | Notes |
| --- | --- | --- | --- |
| **Gzipped TSV** ✅ | none (stdlib/pandas) | none (`readtable`) | Universal, text, types re-specified on read. Chosen. |
| Parquet | `pyarrow` or `fastparquet` (~40–60 MB wheel) as a `raven-toolbox[kegg]` extra | needs ≥ R2019a (`parquetread`, native) | Smaller, faster, typed, columnar. Win mainly at scale / repeated random access. |
| SQLite | none (stdlib `sqlite3`) | **needs Database Toolbox** | Rejected: the MATLAB-side toolbox requirement breaks the "same files, both languages, no extra deps" goal. |

## When to revisit

Reconsider Parquet (or SQLite) if any of these become true:

- The `organism_gene_ko` table grows large enough that load *time* (not just
  size --- the sort above already keeps on-disk size in check) becomes a real
  bottleneck. The remaining inefficiency is that building one species' model
  still loads all ~9M rows; sorted order makes a `searchsorted`/row-group
  by-organism read the natural next step before reaching for Parquet.
- Either side starts doing repeated random-access / columnar reads rather than a
  single load-once-per-run pattern.
- A typed, self-describing schema becomes valuable (TSV loses dtypes; they are
  re-specified on read).

If revisited, prefer **Parquet** over SQLite (no MATLAB toolbox dependency; MATLAB
reads Parquet natively from R2019a). On the Python side it could be offered as an
optional `raven-toolbox[kegg]` extra (pyarrow) alongside the TSV default, rather
than replacing it --- keeping the dependency-free path intact for users who don't
opt in.
