# Maintaining bundled binaries (BLAST+, DIAMOND, …)

How raven-toolbox ships the external command-line tools both toolboxes rely on
(BLAST+, DIAMOND, HMMER), the minimal-footprint ZIP convention, and the
per-platform / licensing matrix. End users never read this --- they get a binary
automatically via `ensure_binary`, or use their own (system/conda) install; this is
for whoever publishes the release assets.

Building and publishing a new version is now **automated**: the current bundles are
produced from RAVEN's vetted `software/` binaries by
[`scripts/build_binary_bundles.py`](https://github.com/SysBioChalmers/raven-toolbox/blob/develop/scripts/build_binary_bundles.py)
and published with `publish_to_raven_data.py`. See
[Artefact hosting & publishing](artefact_hosting.md) for the end-to-end workflow.
This page is the reference for the ZIP **conventions** the automation follows and
the per-platform / licensing matrix behind them.

---

## 1. How binary provisioning works

Neither toolbox vendors these binaries in its own git repo or package manager.
Instead:

1. For each tool, version-pinned ZIPs are published as GitHub release assets (see
   [Artefact hosting & publishing](artefact_hosting.md)).
2. A **registry** (`src/raven_toolbox/binaries_registry.json`) maps each *bundle* to
   its version, the executables it provides, and per-platform `{asset, sha256}`.
   MATLAB RAVEN has no equivalent registry: `getBlast`/`getDiamond` resolve and
   fetch their own binaries directly, without a shared manifest of versions.
3. At run time raven-toolbox's `raven_toolbox.binaries.ensure_binary("blastp")`
   resolves a tool in this order --- and only reaches the download as a last resort:

   ```
   explicit binary= arg  →  env var (RAVEN_PYTHON_BLASTP / RAVEN_PYTHON_DIAMOND / …)
     →  shutil.which on PATH (system / conda / apt / brew)
     →  ensure_binary: download the pinned ZIP → verify SHA256 → cache → return path
     →  actionable error (with conda / manual instructions)
   ```

So a pre-installed binary always wins; the bundle is the zero-setup fallback.
Pinning the version makes reconstruction **reproducible**.

A *bundle* can provide several executables from one download (e.g. the `blast`
bundle provides both `blastp` and `makeblastdb`), so they are fetched once.

---

## 2. What's actually needed --- ship only these

Distribute the **minimum** set of executables. Everything else (other suite
tools, docs, examples, changelogs) is excluded.

| Bundle | Executables to include | Everything else |
|---|---|---|
| `diamond` | `diamond` | --- (it is a single static binary) |
| `blast` | `blastp`, `makeblastdb` | **drop** `blastn`, `tblastn`, `psiblast`, `rpsblast`, `blast_formatter`, `*_vdb`, the `doc/`, `ChangeLog`, `README`, ~30 other tools |

Confirmed against MATLAB's own `getBlast`/`getDiamond`: only `makeblastdb`+`blastp`,
and `diamond` for its `makedb`/`blastp` subcommands, are ever invoked --- so the same
minimal set serves both toolboxes. For BLAST+ this is the big win: the full NCBI
suite is ~hundreds of MB; two binaries (stripped) are a small fraction.

**ZIP convention:** `<bundle>-<version>-<os>-<arch>.zip`, flat layout, executables
at the root plus the upstream `LICENSE` --- no nested `bin/`, no extra files.
Windows ZIPs additionally carry the `.exe` and any runtime DLL the build needs
(e.g. `nghttp2.dll` for BLAST+, `cygwin1.dll` for HMMER) at the root, since
`ensure_binary` extracts flat and expects the executable at the top level, looked
up as `<name>.exe` on Windows.

---

## 3. Platform / architecture matrix & licensing

**Coverage = what's built.** `linux-x86_64` (CI default) first, then `macos-arm64`,
`macos-x86_64`, `linux-arm64`, `windows-x86_64` as capacity allows. For any
`(os, arch)` **not** in the registry, `ensure_binary` raises an actionable error
pointing to conda (`conda install -c bioconda diamond blast`) or a manual install
--- that is the documented fallback, not a failure to fix urgently.

**Licensing (must comply when redistributing):**

- **BLAST+** --- produced by NCBI (US Government); **public domain**, free to
  redistribute. Include NCBI's `LICENSE` for courtesy/provenance.
- **DIAMOND** --- **GPLv3**. Redistribution is allowed; you **must** include the
  GPLv3 licence text in the ZIP and keep the binary unmodified (or offer source).
- **HMMER** --- BSD-3-Clause; include its `LICENSE`.

Always ship the upstream licence in the ZIP, and keep a `BINARIES_PROVENANCE.md`
(or a note in the release body) recording, per asset: upstream URL, upstream
version, upstream checksum, and the SHA256 published.

### Native OS support per tool

Both toolboxes invoke each tool as a subprocess, so the real constraint is whether
a given tool has a binary that runs natively on each OS. It varies:

| Tool | Linux | macOS (incl. arm64) | Windows (native) |
|---|---|---|---|
| BLAST+ (`blastp`, `makeblastdb`) | ✅ | ✅ | ✅ (NCBI ships Windows builds; needs `nghttp2.dll`) |
| DIAMOND | ✅ | ✅ | ✅ |
| HMMER `hmmsearch` (query) | ✅ 3.4 | ✅ 3.4 | ✅ **3.3.2** (Cygwin build from RAVEN 2.10.5; needs `cygwin1.dll`) |
| HMMER `hmmbuild` (build) | ✅ 3.4 | ✅ 3.4 | ⚠️ 3.3.2 `.exe` exists (RAVEN 2.10.5) but the build also needs MAFFT/CD-HIT |
| MAFFT | ✅ | ✅ | ❌ no usable native build |
| CD-HIT | ✅ | ✅ | ❌ no Windows build exists |

(Sources for the bundled builds and versions: RAVEN `develop3` `software/` ---
BLAST+ 2.17.0, DIAMOND 2.1.17, HMMER 3.4.0 `hmmsearch` for Linux/macOS --- and RAVEN
`v2.10.5`, the last release to ship native-Windows HMMER 3.3.2
`hmmsearch.exe`/`hmmbuild.exe`.)

Implications:

- **Linux / macOS** --- everything works: `conda install -c bioconda hmmer mafft
  cd-hit blast diamond`, or point the `RAVEN_PYTHON_*` env vars (Python side) at
  your installs.
- **Native Windows --- runtime (end users) works.** BLAST+, DIAMOND, and
  `hmmsearch` all have native Windows builds, so homology reconstruction **and**
  the KEGG HMM *query* run without WSL, on either toolbox.
- **Native Windows --- the HMM *build* does not work.** Even though a 3.3.2
  `hmmbuild.exe` exists, the build pipeline also needs **MAFFT and CD-HIT**, which
  have no Windows binaries (and no bioconda Windows packages). Build on **WSL2**
  (or Linux/macOS) instead.
- raven-toolbox does not replicate RAVEN's `getWSLpath`/`wsl …` path translation:
  it calls the resolved binary directly, so mixing native-Windows Python with WSL
  binaries is unsupported --- for the build, keep the whole stack inside WSL2.
- The common end-user paths --- homology reconstruction and the KEGG species model
  --- need no HMMER/MAFFT/CD-HIT, so they are fully cross-platform on both
  toolboxes.

### Native-Windows HMMER (3.3.2 from RAVEN 2.10.5)

There is **no native-Windows HMMER 3.4** build --- upstream targets POSIX, and
RAVEN's `develop3` ships only Linux/macOS `hmmsearch` 3.4.0 (running the Linux
binary via WSL on Windows). But RAVEN **`v2.10.5`** is the last release to bundle a
**native Windows HMMER 3.3.2**, Cygwin-compiled: `hmmsearch.exe`, `hmmbuild.exe`,
and the `cygwin1.dll` they depend on --- which is why the published `windows-x86_64`
asset for the `hmmer` bundle is repackaged from that older RAVEN release rather
than built fresh.

**Is searching 3.4-built HMMs with 3.3.2 a problem? No.** The published KEGG HMM
library is a concatenated **ASCII** `.hmm` file, searched directly (no `hmmpress`,
so no version-sensitive binary `.h3m/.h3f/.h3i/.h3p`). The ASCII profile format is
`HMMER3/f`, unchanged from 3.1 through 3.4, and `hmmbuild` 3.4 writes it; `hmmsearch`
3.3.2 reads it. HMMER 3.4 is a maintenance release over 3.3.2 with no change to the
protein scoring model, so bit scores / E-values match and the calibrated KEGG
cutoffs transfer. Caveats: ship `cygwin1.dll` with the `.exe`; it's an older,
unmaintained build; and **keep publishing ASCII libraries** (don't switch to
`hmmpress`-ed binaries) to preserve this cross-version compatibility. A one-time
check --- search a fixed test set with 3.3.2 (Windows) and 3.4 (Linux) on the same
library and confirm identical hits --- is cheap insurance, recorded in the KEGG HMM
cutoff calibration study (raven-docs).

---

## 4. Binary sets, the CLI, and auto-fetch control

This section is raven-toolbox's own end-user provisioning UX --- MATLAB has no
equivalent grouping; `getBlast`/`getDiamond`/`getHMMER` just fetch whatever a given
function needs, on demand, with no set/group concept.

End users don't need every tool, so raven-toolbox groups the executables into two
**sets** (`raven_toolbox.binaries.BINARY_SETS`) for the two audiences:

| Set | Executables | Audience |
|---|---|---|
| `runtime` | `blastp`, `makeblastdb`, `diamond`, `hmmsearch` | end users --- homology + KEGG HMM query |
| `build` | `hmmbuild`, `mafft`, `cd-hit` | maintainers --- KEGG HMM-library build |

Provisioning is decoupled from `pip install` (none of these tools except HMMER are
on PyPI, and downloading binaries during install breaks offline/locked-down setups)
into two layers:

1. **Explicit fetch (console script).** After `pip install`, run:
   ```bash
   raven-toolbox-binaries --set runtime   # blast + diamond + hmmsearch for this OS
   raven-toolbox-binaries --set build     # hmmbuild + mafft + cd-hit
   raven-toolbox-binaries --list          # show the sets for this platform
   ```
   It fetches via `ensure_binary` (SHA256-verified, cached), **skips tools already
   on PATH**, and reports any with no bundle for this OS/arch (with a conda/WSL2
   hint) instead of failing.
2. **Lazy first-use download.** Any wrapper that needs a tool calls
   `resolve_binary`, which downloads the bundle on first use if it isn't already
   resolvable. This is the zero-setup default.

**Turning auto-fetch off.** Set `RAVEN_PYTHON_AUTOFETCH=0` (also `false`/`no`/`off`)
to stop `resolve_binary` ever reaching the network: resolution then ends at
arg → env var → PATH and raises an actionable error otherwise. For air-gapped or
strictly conda/system-managed environments. (The `raven-toolbox-binaries` command
still fetches when run explicitly.)

---

## 5. Registering a new or updated bundle

After building the per-platform ZIPs (§2) and uploading them via the automated
workflow in [Artefact hosting & publishing](artefact_hosting.md), generate the
`_REGISTRY` entry --- checksums and URLs --- with
[`scripts/make_registry_snippet.py`](https://github.com/SysBioChalmers/raven-toolbox/blob/develop/scripts/README.md):

```bash
python scripts/make_registry_snippet.py binary --bundle blast --version 2.16.0 \
    --provides blastp makeblastdb --dir zips \
    --base-url https://github.com/SysBioChalmers/raven-data/releases/download/blast-2.17.0
```

It prints the ready-to-paste `_REGISTRY["blast"]` block, using the same SHA256
helper `ensure_binary` verifies with, so the checksums always match. Adding a new
tool (e.g. a future HMMER bump) needs no new provisioning code --- just a bundle
entry with the right `provides` list and ZIPs built to the §2 convention; the
wrappers call `ensure_binary("hmmsearch", …)` through the same resolution order.
