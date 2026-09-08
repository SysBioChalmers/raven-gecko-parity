# CarveFungi assignment head-to-head: our transport cost on CarveFungi's own carve MILP

A genuine empirical comparison of CarveFungi's compartment-**assignment** objective against ours, run
on CarveFungi's own intermediate state with **CarveFungi's own carve MILP** (its `minmax_reduction`,
in CPLEX). This fixes the three flaws that made an earlier quick emulation a strawman (see
[carvefungi_analysis.md](carvefungi_analysis.md)) and is honest about what a hard, loosely-bounded
MILP can and cannot support.

* Drivers:
  * [`scripts/run_carvefungi_cplex.py`](https://github.com/SysBioChalmers/raven-toolbox/blob/develop/scripts/run_carvefungi_cplex.py)
    â€” runs CarveFungi's **own** `minmax_reduction` (CPLEX), unmodified; the definitive comparison.
  * [`scripts/benchmark_carvefungi_milp.py`](https://github.com/SysBioChalmers/raven-toolbox/blob/develop/scripts/benchmark_carvefungi_milp.py)
    â€” an independent Gurobi re-implementation, used to study the formulation (tighter indicator coupling).
  * [`scripts/analyse_carvefungi_transports.py`](https://github.com/SysBioChalmers/raven-toolbox/blob/develop/scripts/analyse_carvefungi_transports.py)
    â€” the transport-fidelity investigation below (curated match, functional impact, connectivity).
* CarveFungi: [github.com/SandraCastilloPriego/CarveFungi](https://github.com/SandraCastilloPriego/CarveFungi),
  bioRxiv [2023.08.23.554328](https://doi.org/10.1101/2023.08.23.554328).

## Design â€” the intermediate-state swap

Hold CarveFungi's **real intermediate state** fixed and swap only the assignment objective:

* **Candidate set:** CarveFungi's universal model `bigModelv2.21b.sbml` (5602 reactions, 8
  compartments) â€” each reaction exists only in the compartments the DB instantiates it in.
* **Scores:** CarveFungi's *unmodified* scoring code on the shipped *S. cerevisiae* annotations, run to
  produce the exact per-(reaction, compartment) score dict it feeds its carve MILP.
* **Both arms** run CarveFungi's `minmax_reduction` on the *same* scores â€” `SÂ·v=0`, big-M reversibility
  coupling, hard biomass â‰¥ 0.1 and ATP-maintenance â‰¥ 0.1. Only the objective's parsimony differs:
  * **Arm A (CarveFungi):** `max Î£ score(r,c)Â·y[r,c]` â€” no transport cost.
  * **Arm B (ours):** the same, with each inter-compartment transport reaction's score reduced by 0.3
    (our transport-minimisation term, fed through their objective â€” no constraint or variable changed).

An independent adversarial review confirmed the harness is **faithful â€” not a strawman**: the runner
imports and calls CarveFungi's `minmax_reduction` untouched; the only deviations are the three
disclosed here (a CPLEX time limit; Arm B's âˆ’0.3 transport coefficient; the DeepLoc score injection
below), and Arm B perturbs only objective coefficients on existing binaries. Each kept reaction copy's
compartment is read from its **metabolites** (ground truth), not its id suffix â€” the universal model's
suffixes are mixed-case (`_C`/`_m`/`_x`/`_M` â€¦) and overloaded with transport codes (`_TCE` â€¦), so
suffix parsing both mislabels compartments and double-counts a reaction's copies.

## A repro bug in CarveFungi's shipped example: inert localisation

Run literally, CarveFungi's shipped yeast `loc_pred` is **inert**: it is keyed by RefSeq `NP_` ids
while the annotations use SGD ORF names â€” **zero overlap** â€” so its localisation layer never fires and
every reaction gets only its EC score, identical across all its compartments (0/5200 differentiated).
Reproducing its localisation needs the Zenodo TensorFlow models. We therefore **injected DeepLoc 2.1**
(ORF-keyed) into CarveFungi's *unmodified* scoring â€” this reactivates the localisation gate (16.8% of
scores change; 521 reactions become compartment-differentiated; spot-checks sensible, e.g.
enolaseâ†’cytosol, succinyl-CoA ligaseâ†’mito). Both arms use these same scores, so it is a clean,
disclosed substitution that isolates the objective.

## A hard big-M MILP â€” solved with CarveFungi's own CPLEX

CarveFungi's `minmax_reduction` uses **big-M** reversibility coupling, which gives a weak LP
relaxation. The carve is consequently hard: even full academic **CPLEX** leaves the bound loose
(**18â€“27% gap** here, not closing within 20 min); the Gurobi re-implementation with *tighter* indicator
coupling reaches ~10â€“14%. CarveFungi's nominal 0.1% pool gap is **not attained** on this instance by
any solver we tried.

Crucially, the result is still **deterministic and time-budget-stable.** In deterministic mode CPLEX
finds one incumbent within ~25 s (Arm A obj 288.46) that **never changes** as the bound slowly
descends â€” the kept set is byte-for-byte identical at 120 s (46.7% gap), 500 s (26.8%) and a 1200 s
run. So each arm's solution is reproducible and independent of the time budget. It is **not, however,
a *proven* optimum**: a constant incumbent under a still-falling bound is consistent with either
optimality or an early lock-in, and the two arms terminate at *different* gaps. We therefore report the
achieved gap with every number and lean only on what is robust to this (below).

**Running full CPLEX (reproduction note).** The licensed CPLEX Studio install shipped without its
Python API. We installed the PyPI `cplex` (version-matched 22.2.0.0, but Community-capped at 1000
constraints) and replaced its bundled `_internal/cplex2220.dll` with the Studio runtime's full
`cplex2220.dll` of the same version â€” academic binaries are unlocked, so the matching pip bindings then
load at full capacity. No Gurobi needed.

## Result: a leaner transport network at no detectable accuracy cost

Compartments from metabolites; accuracy = EC-mapped against curated yeast-GEM compartments, on the
**common** kept set (same denominator both arms). Numbers are the deterministic incumbents (identical
across time budgets); gaps are the achieved bounds at 500 s.

| | Arm A (CarveFungi) | Arm B (+ our transport cost) |
|---|--:|--:|
| base reactions kept | 877 | 830 |
| inter-compartment transports | 138 | **81** (41% fewer) |
| transports per base reaction | 0.157 | **0.098** (â‰ˆ1.6Ã— fewer) |
| recall vs curation (n=463) | 86.0% | 85.5% |
| exact-set match (n=463) | 62.6% | 61.6% |
| identical compartment set (common, both assigned) | â€” | 93.1% (683/734) |
| achieved gap @ 500 s | 26.8% | 18.1% |

Two takeaways, scoped to what the data supports:

* **Transport parsimony â€” large and direction-robust.** Adding our transport cost cuts inter-
  compartment transports 41% (0.157 â†’ 0.098 per base, ~1.6Ã—). The *direction* is mechanistically
  guaranteed (the âˆ’0.3 cost dwarfs CarveFungi's ~1e-11 transport scores) and the per-base
  normalisation controls for Arm B keeping fewer reactions; the *exact magnitude* is conditional on
  these loose-gap (but deterministic) solutions.
* **No detectable assignment-accuracy cost.** The accuracy difference is within noise â€” Arm A
  (unmodified CarveFungi) is nominally higher on both metrics, but by ~2 reactions (recall) and ~5
  (exact), non-significant (best-case paired McNemar p = 0.50 recall, p â‰ˆ 0.06 exact). The honest
  statement is *"no detectable accuracy gain or loss from our objective"*, not a neutral tie. 93.1% of
  the placements the two arms share are identical.

"Free" here means *in compartment-assignment accuracy*. Whether the leaner transport network is also
*biologically better* is a separate question â€” investigated next.

## Is less better? A transport-fidelity investigation

Arm B drops 66 of Arm A's 138 transports (72 are shared, 9 are B-only), concentrated on
cytosolâ†”mito (27), cytosolâ†”extracellular (20, mostly sugar/polyol export), cytosolâ†”ER (7) and
cytosolâ†”peroxisome (7). The cargo includes textbook shuttles â€” citrate, (S)-malate, oxaloacetate,
2-oxoglutarate (the malateâ€“aspartate and citrate shuttles), plus trehalose/fructose/mannose export.
Three checks ask whether dropping them is an improvement. Driver:
[`scripts/analyse_carvefungi_transports.py`](https://github.com/SysBioChalmers/raven-toolbox/blob/develop/scripts/analyse_carvefungi_transports.py).

**1. The reduction is *not selective.*** Match each carved transport (metabolite + compartment pair)
against the curated, literature-backed yeast-GEM transportome. If the cut were "smart", dropped
transports would match curation *less* than kept ones. They don't:

| transport set | matches a curated yeast-GEM transport |
|---|--:|
| shared (both arms keep) | 39% |
| **dropped by Arm B** | **42%** |
| kept by Arm A (all) | 41% |

Arm B sheds real and spurious transports at the same rate (classifiable n = 46/59/105; these are
qualitative rates, not a significance test). This is expected: the carve has **no transporter-level
evidence** (transport scores are ~1e-11), so a blanket âˆ’0.3 penalty just removes whatever the network
can do without while keeping biomass feasible.

**2. The dropped transports are functionally load-bearing.** Map the dropped transports to their
curated counterparts (31 yeast-GEM reactions) and delete them from yeast-GEM â€” a *proper* model with
GPRs and validated growth (baseline 0.081). Growth collapses to **0**, and **5 are individually
essential**: 2-oxoadipate/2-oxoglutarate, 2-dehydropantoate (a CoA precursor), NADPâº, NADPH, and
serine transport. The *shared* (kept-by-both) transports are equally load-bearing â€” their 24 curated
counterparts also collapse growth when removed, with 3 individually essential â€” so essential transports
are spread across kept and dropped alike. That is precisely the **indiscriminate** point: Arm B's cut
is not concentrated on the dispensable ones. This measures importance in *curated* biology â€” Arm B
itself stays feasible (biomass â‰¥ 0.1 by construction; the carve routes around the cuts), so the finding
is that its network *diverges* from curated yeast, not that it fails to grow. (Gene essentiality cannot
be tested on the carved models themselves â€” the universal DB has 0 GPRs â€” which is why this uses
yeast-GEM.)

**3. Connectivity barely changes â€” the carve re-routes through exchanges.** Structurally (internal
network, exchanges excluded; the carve guarantees *flux*-connectivity *with* exchanges by its Îµ-flux
coupling, so this exposes the latent gaps exchanges otherwise hide):

| | Arm A | Arm B |
|---|--:|--:|
| connected components | 2 (giant + a 3-rxn island) | 2 (giant + the same island) |
| dead-end metabolites | 186 (17.3%) | 194 (18.6%) |

Dropping transports does **not** fragment the network into isolated sub-networks. It does strand
modestly more metabolites: 19 are mass-balanced in A but dead-end in B (vs 8 the other way), localised
to cytosol (8), mito (7), peroxisome (3), ER (1) â€” exactly the dropped-transport cargo (2-dehydro-
pantoate, formate, butyrate, peroxisomal citrate/ammoniumâ€¦). These then lean on boundary exchanges
(secrete/import) rather than internal transport to stay balanced â€” feasible, but less biologically
self-contained.

**Verdict: less is more *parsimonious*, not more *correct*.** The reduction is indiscriminate, removes
functionally essential curated transports, and modestly raises dead-ends â€” though it does not break
global connectivity, because the carve re-routes via the (artificial) environment. The root cause is
that the transport penalty is a blanket prior applied **without transporter-level evidence.**

## Toward evidence-aware transport scoring

**Shipped.** This section is kept as the original design rationale; the scoring it proposes is
now implemented as `localization.evidence_aware_transport_cost`, with the Pfam/hmmsearch and
TCDB/diamond evidence back-ends (`annotate_proteome`) and DeepLoc-compartment matching all
live â€” see [transport_evidence_scoring.md](https://github.com/SysBioChalmers/raven-toolbox/blob/develop/docs/reference/transport_evidence_scoring.md) for the
current status and [yeast_validation.md](yeast_validation.md) for it in production use. Only
the orthology consensus/refinement step below remains open.

The fix follows directly: make the transport cost *evidence-aware*, so the reduction becomes selective
â€” penalise transports with **no** transporter support while retaining those with sequence-level
evidence. This mirrors how the localisation module already scores *metabolic* reactions by gene
localisation; it simply extends the same predictor-agnostic, sequence-derived evidence to transport.

**Evidence sources â€” every carrier, every membrane.** All four are sequence-, HMM-, or
orthology-derived, so they cover *any* transporter family across *any* membrane (the dropped transports
span câ†”mito 27, câ†”extracellular 20, câ†”ER 7, câ†”peroxisome 7 â€” the scoring must not privilege one
membrane):

* **Transporter family (Pfam / hmmer) â€” the backbone.** One `hmmscan` against the transporter clans
  flags carrier genes of all families: the mitochondrial carrier family (MCF, `PF00153`/SLC25 â€” the
  câ†”mito carriers Arm B dropped), major facilitator (MFS), ABC, amino-acid/sugar permeases,
  aquaporins, P-type ATPases, and so on. Family identity also gives a coarse substrate class.
* **Transporter classification (TCDB, via DIAMOND).** A `diamond blastp` against TCDB assigns a TC
  number â†’ substrate class **and** mechanism (uni/sym/antiport): the substrate-specific gold standard.
* **Compartment placement (DeepLoc, already in-pipeline).** *Which* membrane a carrier sits on follows
  from the gene's predicted **compartment** â€” the reliable organelle outputs (trust 0.78â€“0.88), *not*
  the noisy membrane-*type* output (`mm` â‰ˆ 0.86 but `erm`/`gm`/`vm` â‰ˆ 0). A carrier-family gene
  predicted in compartment *X* supports transports across *X*'s boundary; this generalises to every
  compartment.
* **Orthology (already available).** EggNOG/KEGG orthogroups flag transporter orthologs with
  substrate/direction.

**Scoring.** Replace the constant `transport_cost` with a per-transport cost. For a candidate transport
*t* moving metabolite *m* across membrane *M* = {câ‚,câ‚‚}:

```
evidence(t)       = max over genes g of  conf_transporter(g) Â· compartment_match(g, M) Â· substrate_match(g, m)
transport_cost(t) = base_cost Â· (1 âˆ’ evidence(t))      # supported â†’ cheap; unsupported â†’ full prior
```

`conf_transporter` from the Pfam/TCDB hit strength, `compartment_match` from the DeepLoc compartment,
`substrate_match` from the TC/family substrate class vs *m*'s class. It drops straight into the
assignment MILP objective (the transport term becomes per-reaction), symmetric with the existing
per-gene localisation scoring, and recovers today's constant âˆ’0.3 when `evidence = 0`.

**Organism-agnostic by design.** None of the evidence is a species-specific transporter table â€” they
are universal HMMs (Pfam), a cross-organism sequence DB (TCDB), cross-species orthogroups (EggNOG/KEGG),
and a eukaryote-wide predictor (DeepLoc). The only per-organism input is the **proteome FASTA**; the
compartment set comes from the target model (the module already maps cross-kingdom compartments, e.g.
plastid for plants). So the same pipeline runs unchanged on any eukaryote â€” consistent with the
module's cross-kingdom DeepLoc validation (yeast, *Arabidopsis*, *Chlamydomonas*, human). yeast-GEM is
only the *benchmark* here, not a dependency.

**Phased implementation** (by evidence maturity â€” all-carrier from the start, not membrane-by-membrane):

1. **Family scan** (Pfam/hmmer) over all transporter clans â†’ per-gene "is a carrier" + coarse substrate
   + compartment placement from DeepLoc. Covers every membrane immediately.
2. **TCDB** (DIAMOND) â†’ TC-number substrate specificity + mechanism â†’ substrate-matched scoring.
3. **Consensus/refinement** â€” combine family + TCDB + orthology + DeepLoc, add transport
   directionality, resolve conflicts.

Mitochondria are merely the cleanest *validation* exemplar (the one membrane where DeepLoc's
membrane-type output independently corroborates, and whose curated essential carriers â€” malate/2-OG/
citrate â€” are textbook); the scoring itself is membrane- and organism-agnostic.

**Validation.** Reuse this study's benchmark â€” curated transport precision/recall plus the functional
(essentiality) test â€” before vs after. Success criteria: the kept-transport curated-match rate rises
*above* the dropped rate (the cut becomes selective), the 5 individually-essential transports are
retained, and the gains reproduce on a **non-fungal** model (e.g. AraCore) to confirm
organism-agnosticism.

**Design caveats.** Substrate matching (metabolite â†’ substrate class) is the hard part; start coarse
(sugars / amino acids / organic acids / ions / nucleotides / lipids). Absence of evidence â‰  absence of
a transporter, and annotation completeness varies by organism â€” so keep a *mild, tunable* prior on
unsupported transports; never hard-forbid.

## What this does and doesn't show

* **Not proven optima.** Each arm is a stable, deterministic incumbent at 18â€“27% gap, not a certified
  optimum; the arms stop at different gaps. A tighter solve could shift the magnitudes (it cannot flip
  the transport direction, which is forced by the objective).
* **The kept *set* changed substantially** (877 vs 830, common 796): the "93.1% unchanged" is over the
  common bases assigned in both arms and is conditioned on the subset least likely to change.
* **Compartment-mapping asymmetry:** the gold side can yield compartments (`ce`/`v`) the universalâ†’yeast
  mapping can never produce (21/616 ECs), capping achievable exact-match â€” but this applies equally to
  both arms, so it does not affect the comparison.
* Arm B still keeps 81 transports despite the penalty (consistent with the biomass/ATPM feasibility
  constraints; not separately tested).

## Bottom line

Running CarveFungi's **own** carve MILP, adding our transport-minimisation term yields a materially
leaner transport network (~1.6Ã— fewer transports per reaction, 41% fewer overall) with **no detectable
assignment-accuracy cost** and 93% identical placements. But "leaner" is not automatically "better":
the cut is **indiscriminate** â€” it drops curated, functionally essential transports (â‰¥5 individually
essential in yeast-GEM) at the same rate as spurious ones, because the carve has no transporter-level
evidence. The actionable conclusion is the **evidence-aware transport scoring** proposed above:
penalise only *unsupported* transports. The carve's big-M formulation is hard enough that neither CPLEX
nor a tighter Gurobi port proves optimality, so these are deterministic near-optimal incumbents,
reported with their gaps. The clean, *tight-gap* same-task head-to-head for the paper remains
[`predictLocalization`](https://github.com/edkerk/raven-docs/blob/main/docs/parameter-tuning/studies/predictlocalization-comparison.md) (raven-docs; same lineage, solves fast, deterministic);
CarveFungi is related work of a different kind, and this is a faithful, honest comparison against it.
