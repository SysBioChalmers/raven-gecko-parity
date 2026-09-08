# Publishing versioned artefacts

The convention the gecko/raven repositories use for anything too large to commit:
where it is hosted, how it is versioned, how a consumer finds it, and how a new
one is published. It is a shared standard because more than one toolbox reads the
same files, and a per-repository scheme would make a published result impossible
to reproduce against a stated version.

Two other halves of this material live where the work does:

- What an end user downloads, where it is cached and how to control it is on
  [raven-docs](https://raven-docs.readthedocs.io/en/latest/installation/data-and-binaries/).
- Building the KEGG artefacts and the binary bundles is in
  [raven-toolbox's contributing guide](https://github.com/SysBioChalmers/raven-toolbox/blob/develop/CONTRIBUTING.md),
  since raven-toolbox implements that pipeline.

## The shape of it

Large artefacts are **not** committed to a code repository. They are published as
GitHub Release assets in a dedicated repository, and described by a single
language-agnostic **manifest** that every consumer reads. Every file carries a
SHA256, so a consumer verifies what it downloaded rather than trusting it.

For RAVEN and raven-toolbox that repository is
[`SysBioChalmers/raven-data`](https://github.com/SysBioChalmers/raven-data),
holding the KEGG reference data, the prebuilt HMM libraries, and the
BLAST+/DIAMOND/HMMER binaries. They are not attached to either code repository's
own releases.

Three reasons the assets live in their own repository:

- The HMM libraries are 135 to 155 MB each, past GitHub's 100 MB per-file limit
  for files in a git tree. As release assets they are stored outside the tree, so
  the limit does not apply.
- It keeps the code repositories' licences clean. KEGG's terms and the GPL-3.0
  DIAMOND binary stay with the data.
- One versioned source of truth serves every consumer, which is required when two
  toolboxes have to agree on what they read.

## Versioning: per-artefact, immutable tags

There is **no single version number** for the artefact set. Each artefact has its
own release tag, versioned by its *upstream* version, holding only that
artefact's assets:

| Tag | Assets |
|---|---|
| `kegg118`, `kegg119`, … | `kegg<NNN>_core.tar.gz`, `_taxonomy.gz`, `_prokaryotes.hmm.gz`, `_eukaryotes.hmm.gz` |
| `blast-2.17.0` | `blast-2.17.0-{linux-x86_64,macos-arm64,windows-x86_64}.zip` |
| `diamond-2.1.17` | the three DIAMOND ZIPs |
| `hmmer-3.4.0` | Linux and macOS `hmmsearch` ZIPs |
| `hmmer-3.3.2` | the native-Windows `hmmsearch` ZIP |
| `manifest-v1`, `-v2`, … | `manifest.json`, one pinned snapshot per tag |

An asset is uploaded **once** under its tag and never re-uploaded. Bumping one
tool means a new tag carrying only that tool's ZIPs; every other tag is
untouched. The snapshot of the whole set is the manifest, versioned separately,
not a release that re-bundles the binaries. So a binary is stored once and merely
re-referenced, and a consumer pinned to an older snapshot keeps getting the same
bytes.

`manifest_version` *inside* the JSON is the schema version, and is independent of
the snapshot tag.

## The manifest

```json
{
  "manifest_version": 1,
  "data":     { "<dataset>": { "version": "...", "doi": "...", "files":     { "<name>": {"url": "...", "sha256": "...", "bytes": 0} } } },
  "binaries": { "<bundle>":  { "version": "...", "provides": ["..."], "platforms": { "<os>-<arch>": {"url": "...", "sha256": "...", "bytes": 0} } } }
}
```

The schema is
[`data/manifest.schema.json`](https://github.com/SysBioChalmers/raven-toolbox/blob/develop/data/manifest.schema.json),
with a worked example alongside it.

The entries are URLs, so where a given file is hosted is a per-file decision the
consumer never sees. GitHub Releases is the default: free,
language-agnostic, and good to about 2 GB per file. Zenodo is the alternative
where a citable DOI or a file over 2 GB is needed; point that one file's `url` at
the Zenodo record and record the DOI in the entry.

**Do not re-host another project's model.** Template models such as Human-GEM and
yeast-GEM are fetched from their own repositories at a pinned release tag, which
respects their licences and avoids a stale copy.

## How consumers pin

Two consumers, two deliberate strategies, and the manifest is what lets them
coexist:

- A consumer that wants reproducibility across time bakes a snapshot of the
  manifest into its own release, so a given version always fetches the exact
  assets it was tested against. raven-toolbox does this;
  `RAVEN_PYTHON_MANIFEST` overrides it with a newer manifest.
- A consumer with no baked registry to keep in step resolves from the manifest
  URL on each call. MATLAB RAVEN does this.

They coordinate through the manifest and the SHA256 pinning, not by matching
version numbers with each other. Neither has to know what the other targets.

Reading the manifest needs nothing unusual on either side. In Python it is a JSON
load; in MATLAB `webread` and `jsondecode` read it, `websave` downloads, and
Java's `MessageDigest`, always present in MATLAB, verifies the checksum.

## Publishing a new artefact

Everything is scripted and idempotent, run from a raven-toolbox checkout. There
is no MATLAB-side publishing tool: RAVEN only consumes these releases. Re-running
skips assets already present, so bumping one tool never re-uploads the rest.

```bash
# 0. once: gh auth with write access to the data repository

# 1. BUILD the assets
python scripts/build_binary_bundles.py
python scripts/build_kegg_artefacts.py --keggdb ... --out ... --version kegg118 --hmms

# 2. PUBLISH to the data repository (idempotent, immutable tags)
python scripts/publish_to_raven_data.py binaries --dir dist/binaries
python scripts/publish_to_raven_data.py release --tag kegg118 --dir <kegg-out-dir>

# 3. UPDATE the manifest, computing each URL, SHA256 and size from the uploads
python scripts/make_registry_snippet.py manifest --target data --dataset kegg \
    --version kegg118 --dir <kegg-out-dir> --manifest data/manifest.json \
    --base-url https://github.com/SysBioChalmers/raven-data/releases/download/kegg118

# 4. SYNC the baked registries from the manifest
python scripts/make_registry_snippet.py sync

# 5. PUBLISH the manifest snapshot, then open the PR
python scripts/publish_to_raven_data.py release --tag manifest-v2 data/manifest.json
```

`--dry-run` on `publish_to_raven_data.py` prints the `gh` calls without running
them.

**The manifest is the single source of truth.** Never hand-edit a baked registry:
change `data/manifest.json` and run the `sync` step.

Two things stay manual on purpose. Building the KEGG dump needs FTP credentials,
a multi-gigabyte download and the KEGG licence, so a maintainer runs it rather
than CI. And deciding *whether* to adopt a new upstream version into a code
release is a reviewed judgement; the scripts only execute it.

## Mirroring to Zenodo, if DOIs are needed

**GitHub's native Zenodo integration does not do this.** Enabling it archives the
repository *source zipball* at the tag; it does not capture files attached to the
release. It is useful for a software DOI, not for data assets.

To mint DOIs for release assets, or to host files over 2 GB, add an Action that
uploads them to Zenodo on release. Cut a normal GitHub Release with the files
attached; the Action mirrors them and mints a version DOI, which then goes into
the manifest entry's `doi` field.

```yaml
name: Mirror release assets to Zenodo
on:
  release:
    types: [published]
jobs:
  zenodo:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - name: Download this release's assets
        run: gh release download "${{ github.event.release.tag_name }}" --dir assets
        env: { GH_TOKEN: "${{ github.token }}" }
      - name: Deposit a new version on Zenodo
        run: npx zenodraft@latest version create --publish ${{ vars.ZENODO_CONCEPT_DOI }} assets/*
        env: { ZENODO_ACCESS_TOKEN: "${{ secrets.ZENODO_TOKEN }}" }
```

The result is that only GitHub Releases is ever touched by hand, and the
archiving happens on its own.
