# Reconciling the two YAML writers

`yaml_roundtrip_smallyeast` is the one scenario in this repository that reports a difference.
Both sides read the same model and both round trips are lossless, but `writeYAMLmodel` and
`write_yaml_model` do not produce the same file. This is what the difference is made of, which
way it should be resolved, and in what order.

Tracked as [SysBioChalmers/raven-gecko-parity#6](https://github.com/SysBioChalmers/raven-gecko-parity/issues/6).

## Status: resolved (Tiers 1 and 2), Tier 3 outstanding

The analysis below (evidence, the four mechanical causes, Options A/B/C) is left as written
because it is still an accurate record of what was investigated and why --- but the recommended
direction it lands on ("Option B: Python adopts RAVEN's layout") is **not what was implemented**.
Once RAVEN's reader could actually load a cobrapy-written file, the real question stopped being
"which existing layout wins" and became "does either writer need to match cobrapy's layout at
all" --- and the answer turned out to be no: nothing outside this project's own two writers reads
these files as a matched pair, so the two of them only ever need to agree with *each other*.

That reframing changes the folding trade-off in particular. Matching ruamel's line-folding would
have meant hand-porting its column-by-column wrap algorithm into MATLAB (a fragile piece of
logic neither side owns or can debug independently) for a purely cosmetic gain, and folding is
actively worse for the model repositories' diffs than not folding: a one-word edit to a long note
reflows several lines instead of changing one. So RAVEN and raven-toolbox now share their own
layout, close to cobrapy's structural shape (same keys, same `!!omap` tags, same nesting, so
plain cobrapy still reads a file written here) but not byte-identical to it:

- 2-space indentation throughout (this part *does* match ruamel's own defaults, so it cost
  nothing on the Python side).
- Single-quoting only where YAML requires it (also already ruamel's default behaviour).
- Every number formatted as an explicit float (`2.0`, never `2`) --- one rule for every numeric
  field, rather than tracking which fields cobra happens to treat as int vs float, which RAVEN's
  model struct (everything stored as `double`) cannot see anyway.
- Annotation keys sorted alphabetically (already cobra's own dict-conversion behaviour).
- Optional fields omitted entirely when empty, including `subsystem` --- dropping cobra's
  round-trip preservation of older RAVEN files' "single blank list entry" convention for "no
  subsystem" in favour of just not emitting the key. A reaction that does carry a subsystem is
  always written as a list, even a single one, since a reaction can have more than one.
- **No line folding, regardless of scalar length.** The one deliberate, largest-magnitude
  departure from cobrapy's own output, for the reasons above.

Implementation: [readYAMLmodel.m fix](https://github.com/SysBioChalmers/RAVEN/commit/dda689b0)
(Tier 1, the three reader bugs), `writeYAMLmodel.m`'s rewrite (Tier 2, RAVEN side) and
`raven_toolbox/io/yaml.py`'s corresponding changes (Tier 2, Python side). Verified byte-identical
between the two writers on both a plain model and one exercising every optional field
(notes, ec-code, references, deltaG, confidence_score, protein, smiles, charge), with each
side's full test suite passing.

**Tier 3 (rewriting yeast-GEM / Human-GEM to the agreed format) has not been done** --- it is a
one-time, do-it-once corpus change that should happen deliberately, in a commit that does
nothing else, once this decision has had a chance to settle.

## The short answer

**No --- "cobrapy uses ruamel" does not mean MATLAB has to adopt ruamel's output.** ruamel is a
library, not a format. cobra's dumper is `CobraYAML(typ="rt")` with every knob left at its
default, and `width` and `indent()` are per-instance settings that `raven_toolbox` can set on an
instance of its own without touching cobra. The layout is a choice nobody has made yet, not a
constraint.

But the question splits in two, and the halves have different answers:

* **The writers.** The Python side should move, not MATLAB. It is one line for the part that
  matters, it keeps the diffs on the model repositories small, and RAVEN's line-based writer
  cannot practically reproduce ruamel's line folding anyway.
* **The readers.** RAVEN has to move regardless of what any writer does. Today `readYAMLmodel`
  **cannot read a file written by cobrapy at all** --- not by `write_yaml_model`, and not by
  plain `cobra.io.save_yaml_model` either. That is a hole in RAVEN's interoperability with the
  wider cobrapy ecosystem that exists independently of this parity question, and it is the
  highest-value item here.

## What is actually at stake

Not aesthetics. Three things:

1. **Interoperability.** A file one toolbox writes has to be readable by the other. Today that
   holds in one direction only.
2. **Churn on the model repositories.** yeast-GEM (120k lines) and Human-GEM (260k lines) keep
   their models as YAML in git. If a contributor using MATLAB and a contributor using Python
   each rewrite the file, every line changes and the review is worthless.
3. **Silent corruption.** The worst case is not a crash. It is RAVEN reading a cobrapy file,
   producing a model that looks right, and getting 37 of 52 InChI strings and 2413 of 4105 EC
   code lists wrong.

## Evidence

Everything below is reproducible; the commands are at the end.

### 1. Content is already at parity

The two readers produce the same model from the same file --- ids, names, bounds, objective,
formulae, compartments, gene sets and stoichiometry all agree, on smallYeast and on yeast-GEM.
A read-write-read round trip is lossless on both sides. `cobra.io.load_yaml_model` also reads
RAVEN's output correctly (53 reactions, 52 metabolites, 61 genes on smallYeast). **Nothing
below is a disagreement about what a model is.**

### 2. RAVEN cannot read what cobrapy writes

| Reader | File | Result |
|---|---|---|
| `raven_toolbox.io.read_yaml_model` | RAVEN's output | correct |
| `cobra.io.load_yaml_model` | RAVEN's output | correct |
| `readYAMLmodel` | cobrapy's smallYeast | *silently wrong* --- 37/52 InChIs gain a leading space |
| `readYAMLmodel` | cobrapy's yeast-GEM | **hard error**: `Unknown entry in yaml file: #222)'` |

Three independent defects in `readYAMLmodel`, each isolated:

**(a) Folded scalars.** ruamel breaks a scalar that would exceed 80 columns onto a continuation
line. `readYAMLmodel` is a line parser: a continuation line matches no key pattern, so it falls
to the `otherwise` branch and either raises `Unknown entry in yaml file` or, when the break came
straight after the key, is taken as the value with its indentation still attached. Python emits
37 such lines for smallYeast and 1143 for yeast-GEM. **Plain `cobra.io.save_yaml_model` emits
exactly the same 37** --- this is not a `raven_toolbox` quirk.

**(b) Single-quoted scalars.** `readYAMLmodel` strips quotes with
`regexprep(tline_value,'^ +- "?(.*)"?$','$1')`, which knows about `"` and not about `'`. ruamel
single-quotes anything YAML requires it to. On yeast-GEM that is 1436 reaction notes and 5 names
read back with literal apostrophes: `"'[cytochrome c]-L-lysine'"`.

**(c) A list-valued `ec-code` swallows the rest of the annotation block.** `readList` is set to
`'eccodes'` and never reset, so every following line in the `annotation` block falls through to
the `eccodes` case. RAVEN's own writer happens to emit `ec-code` **last**, which masks it; the
Python side sorts annotation keys, so `ec-code` comes second and everything after it is
consumed.

Isolated by reordering that one block inside **RAVEN's own output**, leaving the other 122,360
lines byte-identical:

```
ec-code last  : eccodes = 1.1.2.4;1.1.99.-
ec-code second: eccodes = 1.1.2.4;1.1.99.-;;sce00620;sce00920;R00197;MNXR138960;SBO:0000176
```

This one is not about Python at all. It is a latent RAVEN bug that any hand-edited or
third-party file can trigger.

### 3. The writer difference decomposes into four mechanical causes

Shared lines between the two writers' output for the same model, relaxing one cause at a time
(folding already disabled on the Python side, or the raw figure would be 0.0% for both):

| Normalisation | smallYeast | yeast-GEM |
|---|---:|---:|
| raw | 0.8% | 0.0% |
| ignoring indentation | 96.1% | 30.7% |
| ...and quoting style | 99.9% | 79.6% |
| ...and `1.0` vs `1` | 99.9% | 98.3% |

So, in order of how much churn each causes:

1. **Line folding.** ruamel breaks at 80 columns; RAVEN never breaks a line. *One line of Python
   config.*
2. **Indentation.** RAVEN indents a sequence under a key by 4 and the entry keys by 2 more;
   ruamel's defaults are 2 and 2.
3. **Quoting.** RAVEN quotes nothing by default (`preserveQuotes` is opt-in) and always
   double-quotes when asked; ruamel quotes only where YAML requires it, with single quotes.
4. **Number formatting.** RAVEN writes every number as a double, so `charge: 0` becomes
   `charge: 0.0` --- 31,358 lines of yeast-GEM. Python preserves whatever type the reader
   produced, which for that file is the integer.

The residual 1.7% on yeast-GEM is key ordering (RAVEN puts `notes` before `annotation` and
`ec-code` last; Python sorts) and one spurious `- version: ` line that RAVEN emits into
`metaData` even when the model carries no version.

### 4. Both writers have already left the corpus behind

yeast-GEM and Human-GEM are in a *third* format: a `---` document header, `metaData` as a plain
mapping rather than an `!!omap`, every string double-quoted, bare integers, and reaction EC codes
and notes as top-level `eccodes` / `rxnNotes` keys. Neither current writer reproduces it --- both
have moved to `- metaData: !!omap`, to `ec-code` inside `annotation`, and to `notes`.

Round-tripping yeast-GEM through each writer, counting how many of the source's 120,443 lines
survive anywhere in the output:

| Writer | Lines out | Lines also in the source |
|---|---:|---:|
| `writeYAMLmodel`, `preserveQuotes` on | 122,362 | 82,272 (68.3%) |
| `writeYAMLmodel`, default | 122,362 | 29,818 (24.8%) |
| `write_yaml_model` | 126,754 | 6 (0.0%) |

**A one-time rewrite of the corpus is coming whichever way this is decided.** That is worth
knowing before treating "don't churn the GEMs" as an argument for the status quo --- the status
quo already churns them. What it does argue is that the rewrite should happen once, from an
agreed format, rather than twice.

## Options

**A. MATLAB adopts ruamel's layout.** `writeYAMLmodel` would have to reproduce ruamel's folding
algorithm in hand-written MATLAB, and `readYAMLmodel` would have to parse folded scalars. The
cost is concentrated in the hardest place --- a line-based emitter and parser imitating a real
YAML implementation --- and MATLAB ships no YAML library to fall back on (`yamlread` and
`yamlwrite` do not exist in R2024b; RAVEN bundles libSBML but nothing for YAML). Benefit: files
from any cobrapy tool become readable.

**B. Python adopts RAVEN's layout.** `raven_toolbox` stops dumping through cobra's shared ruamel
instance at its defaults and configures its own. The cost is small and in the easy place.
Benefit: the corpus stays legible, RAVEN's reader keeps working, and cobrapy can still read the
result --- which it can today.

One honest caveat: **exact byte-identity is not reachable through ruamel settings alone, because
RAVEN's own layout is not internally consistent.** In RAVEN's output a sequence that is a mapping
value is indented by 4 under `metabolites` and under `annotation`, but by 2 under `metaData`, and
the root sequence sits at column 0 where ruamel would put it at the configured indent.
Byte-identity therefore needs either RAVEN regularising its own indentation first, or a
hand-written emitter on the Python side.

**C. Agree a written format and make both conform.** Option B plus a short spec in RAVEN's docs
that both implementations and the GEM repositories target, so the next divergence is a spec
violation instead of an argument. This is B with the decision written down, and it is what makes
the eventual corpus rewrite a single event.

## Recommended sequence

This section is left as originally written, for the reasoning trail. See "Status" above for what
actually happened at Tier 2: not the specific `raven_toolbox`-only, RAVEN-matching config
described below, but a layout shared by (and now implemented on) both sides.

**Tier 1 --- the readers. Do this regardless of any layout decision. (Done.)** In RAVEN:

1. Accept folded scalars: join a continuation line to the value being read, stripping the
   indentation, instead of raising `Unknown entry in yaml file`.
2. Strip single quotes as well as double.
3. Reset `readList` at the end of a nested list, so a list-valued `ec-code` cannot swallow the
   rest of the annotation block. This one is a bug on its own terms --- reproducer above.

Until (1) and (2) land, RAVEN cannot open a model produced by any cobrapy-based tool, which is a
larger problem than the writer disagreement.

**Tier 2 --- the writers. (Done, but see "Status" above --- not this specific plan.)** In
`raven_toolbox`, in two steps:

1. **Stop folding.** Give `io/yaml.py` its own ruamel instance rather than importing cobra's
   module-level one --- mutating the shared instance would change `cobra.io.save_yaml_model` for
   everything else in the process --- and set `width` high. Verified: this removes all 37
   continuation lines on smallYeast and all 1143 on yeast-GEM, and RAVEN then reads the Python
   output with **zero field differences**. This is the whole of the correctness problem on the
   writer side.
2. **Then the cosmetics**, in whatever order is agreed: `indent(mapping=2, sequence=4,
   offset=2)`, double quoting, integer formatting, key order. Each is independently measurable
   against the table in section 3.

**Tier 3 --- the corpus.** Once both writers agree, rewrite yeast-GEM and Human-GEM once, in a
commit that does nothing else, and note the format in each repository's contributing guide.

## What the parity suite should assert afterwards

`yaml_roundtrip_smallyeast` compares the two writers against each other. It does not test the
thing that actually broke, because each side only ever reads its own output.

Add a **cross-read** scenario: commit two small fixtures --- one written by `writeYAMLmodel`, one
by `cobra.io.save_yaml_model` --- and have *both* implementations read *both* and emit the same
model summary. That is deterministic, needs no ordering between the two sides, and would have
caught all three reader defects. It also keeps testing RAVEN against cobrapy-native output even
if the writers converge, which is the case that has no other guard.

## Reproducing

From this repository, with MATLAB on PATH:

```bash
parity run yaml_roundtrip_smallyeast --impl python
```

```bash
parity run yaml_roundtrip_smallyeast --impl matlab
```

```bash
parity compare results/python/yaml_roundtrip_smallyeast.json results/matlab/yaml_roundtrip_smallyeast.json --scenario yaml_roundtrip_smallyeast
```

The genome-scale figures come from round-tripping `yeast-GEM/model/yeast-GEM.yml` through each
writer and reading each output back with the other implementation. The `ec-code` reproducer is
`writeYAMLmodel` output with one annotation block reordered so that `ec-code` is not last.
