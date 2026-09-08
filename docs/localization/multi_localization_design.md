# Design: reaction-level multi-localization

**Status: solved â€” sound via flux-activity coupling (path 2).** `assign_compartments` does
**mono-localization** by default; the opt-in `multi_localization=True` flag now runs the sound
**path-2 flux-activity coupling** formulation (a placement earns its score only if it carries flux),
which is solver-independent. The earlier path-1 capability pre-pass was found **unsound** (it could
not exclude conditionally-dead placements â€” on Gurobi *and* GLPK) and was replaced. This note
specifies what reaction-level *multi*-localization should do, why a naive implementation is unsound,
what the pre-pass experiment showed (path-1 outcome), and the sound formulation that replaced it
(path-2 outcome). It exists because several attempts (the raven-toolbox Phase-2 spike, the yeast-GEM
work, and the path-1 pre-pass) all hit the same wall before path 2 resolved it.

## Goal

Let a single reaction occupy **several compartments at once** â€” but only when that is real, i.e.
when the enzyme genuinely operates in each (dual-targeting; e.g. a mitochondrial *and* cytosolic
acetyl-CoA pathway). Concretely, a reaction `r` should be placed in compartment `c` iff:

* the localization evidence supports it **and** the network can carry flux through `r` in `c`
  (it is not blocked there), **or**
* functionality *requires* `r` in `c` (a confined precursor `r` produces is consumed in `c`).

The result must stay functional and must **not** contain *dead placements* â€” `r` listed in a
compartment where it can carry no flux at all.

## Why mono-localization is already sound

With `Î£_c x[r,c] = 1`, a reaction has one home. The biomass constraint forces that home to a
compartment where the reaction can participate in a flux-carrying network *when the reaction is
needed*; when it is not needed, its single home is chosen by score and may sit inactive â€” which is
fine, because an inactive-but-present reaction is biologically ordinary. There is no *duplicate* to
be dead. Mono-localization therefore never produces a dead placement.

## The obstacle: the dead-placement exploit

Relaxing to `Î£_c x[r,c] â‰¥ 1` immediately breaks this. The MILP discovers that an **extra**
placement is free score:

> **Concrete failure (observed).** Gene `g` scores compartment `m` at 1.0. Reaction `r` (carrying
> `g`) does its real work in `c`. The solver sets `x[r,c]=1` (functional) **and** `x[r,m]=1` with
> `v[r,m]=0` â€” a placement of `r` in `m` that carries no flux, purely so the gene "is in `m`" and
> collects the 1.0 score. The materialized model gains a blocked reaction in `m`.

Scoring only a *primary* compartment does **not** fix it: the dead placement can simply *be* the
primary (`r` "homed" in high-score `m` with no flux, plus an active extra in `c`). The gene still
harvests `m`'s score through a reaction that cannot function there.

The root question is therefore per-(reaction, compartment): **can `r` carry any flux in `c` under
some feasible flux distribution?** â€” i.e. is `r`-in-`c` *blocked* or *inactive-but-capable*?

* *blocked* (no substrate/sink in `c`, ever) â†’ must be forbidden;
* *inactive-but-capable* (zero under biomass, possible under other conditions) â†’ must be allowed.

This is a flux-variability / reachability property of the **compartment-expanded network**, and
that network depends on the assignment being solved â€” so the test is **circular** with the MILP.
Requiring flux through *every* placement (the naive non-circular shortcut) is wrong: it would force
the whole model active, which a real model never is.

## Implementation paths

1. **Flux-capability pre-pass (recommended).** Before the MILP, for each candidate
   (reaction `r`, compartment `c`), test whether `r` *can* carry flux in `c` in the
   compartment-expanded network where every relocatable reaction is allowed in every compartment
   (an upper-bounding relaxation) â€” one FVA-style max-|flux| LP per candidate, or a single
   `flux_variability_analysis` over the expanded reactions. Forbid `x[r,c]` for blocked candidates
   (`fva_max â‰ˆ 0`). Then run the multi-localization MILP (`Î£x â‰¥ 1`, score per placement,
   multi-penalty) over only the capable candidates â€” no dead placements are *possible*, so the
   exploit is structurally removed. Cost: one FVA over the expanded reaction set (parallelizable);
   the relaxation may admit a few candidates that are blocked only in the final assignment, which
   the multi-penalty then declines to use.

2. **Flux-active extras (partial).** Keep a mono-localization *home* (scored, may be inactive) and
   allow **extra** placements that must carry flux in the biomass solution
   (`|v[r,c]| â‰¥ Îµ` when the extra is on). This cleanly captures *function-required* dual-targeting
   (the dual-precursor case) and adds no dead extras â€” but it does **not** stop a dead *home* in a
   high-score compartment, so it must be combined with path (1)'s capability check on the home.
   Reversible reactions need a direction binary for the `|v| â‰¥ Îµ` activity constraint.

3. **Lazy cut generation.** Solve mono-localization; where a multi-localization would raise the
   objective, test the duplicate's flux-capability on demand and add it (or a no-good cut) only if
   capable. Avoids the up-front FVA but needs an incremental/callback solve loop.

## Recommendation

Path 1 (capability pre-pass) was tried first and found **unsound** â€” see the path-1 outcome below.
Path 2 (**flux-activity coupling**) was then implemented and **is** what `multi_localization=True`
now runs; it removes the dead-placement exploit by construction and is solver-independent (see the
path-2 outcome). Mono-localization (`multi_localization=False`) remains the **default**: it is the
simplest, smallest MILP and is sufficient for the common case â€” isozyme separation (`expand_model`)
already lets *different gene copies* of one reaction land in different compartments without any
dead-placement risk. Enable `multi_localization=True` when you specifically need a *single* gene's
reaction in two compartments at once (genuine dual-targeting) and can afford the larger MILP.

## Outcome (path 1 was tried)

Path 1 was implemented and tested on the dual-target toy. The finding is **negative**: the
capability pre-pass is a *necessary* but not a *sufficient* condition, so it does not remove the
dead-placement exploit "structurally" as hoped above. Two things were learned:

1. **A correctness bug worth recording.** The pre-pass forbade non-capable placements by setting the
   binary's upper bound to 0 (`x[r,c].ub = 0`). **GLPK silently ignores a 0 upper bound on a binary
   variable** (it still returns 1); only an explicit `x[r,c] == 0` *constraint* is honored across
   backends. Until that was fixed, even *always*-blocked placements leaked through on GLPK.

2. **The fundamental limitation.** Even with the forbid correctly enforced, the relaxation
   **over-approximates**: a placement `(r,c)` can be flux-capable in the maximally-permissive
   relaxation â€” because some *other* relocatable reaction is hypothetically present in `c` to
   supply/consume `r`'s metabolites â€” yet be **dead in the chosen assignment**, where that supplier
   was placed elsewhere. The pre-pass removes only *always*-blocked placements; it cannot see these
   *conditionally*-dead ones. And the MILP objective rewards a placement for its localization score
   **regardless of whether it carries flux**, so a conditionally-dead placement can *tie or beat*
   the genuinely function-driven solution.

   **This is NOT a GLPK artifact â€” Gurobi is just as unsound.** On the dual-target toy at `transport_cost=0.1`,
   Gurobi itself returns `r1 = {c, m}, r2 = {c, m}` where the `m`-copies carry **zero flux**
   (materialized FVA `r1_m = r2_m = [0, 0]`; the MILP primals show `x_r2_m = 1, v_r2_m = 0,
   y_g2_m = 1` harvesting `g2`'s `m`-score), while the live pathway runs entirely in `c`. At
   `transport_cost = 0.3` the dead-placement solution (objective 1.8) **strictly beats** the honest
   function-driven one (1.6) â€” not a tie, and unchanged across reruns/seeds/`MIPFocus`. Asserting
   `r1 âˆˆ {c, m}` alone is insufficient â€” a *dead* `r1_m` also satisfies it; the check must confirm
   the placement actually carries flux. The GLPK `ub = 0` bug is **orthogonal**: the
   dead placements pass the capability pre-pass, so the forbid never applies to them. The defect is in
   the *formulation*, not the solver.

The implementation was kept behind `multi_localization=False`. It has since been **replaced** by the
sound path-2 formulation below.

## Outcome (path 2 implemented â€” SOUND)

Path 2 (**flux-activity coupling**) was implemented and is now what `multi_localization=True` runs.
The idea: a placement earns its localization score **only if it carries flux**. Per movable reaction
`r`, compartment `c`, with the existing compartment flux `v[r,c]`:

* activity binaries `aF[r,c]`, `aR[r,c]` (reverse only for reversible `r`) gate real flux â€”
  `ÎµÂ·aF â‰¤ v[r,c]` and `ÎµÂ·aR â‰¤ âˆ’v[r,c]`, so an active binary forces `|v| â‰¥ Îµ` (`eps_flux`); `Îµ`
  defaults to `10Â·big_mÂ·integrality_tol` (`1e-5`), just above the ghost-flux floor â€” see the
  *deadzone* note below;
* a placement is materialized only as a flux-active placement or as the reaction's single inactive
  **home** â€” `x[r,c] â‰¤ h[r,c] + aF[r,c] + aR[r,c]`;
* the home exists **iff the reaction is entirely unused** â€” `Î£_c h[r,c] + used[r] = 1`, with
  `used[r] = â‹_c (aF âˆ¨ aR)`. So a *used* reaction has **no** inactive placement â€” every compartment
  it occupies carries flux â€” while an unused reaction keeps one score-driven home exactly like a
  mono reaction that is not needed for biomass.

This removes the dead-placement exploit **by construction**: no reaction can collect an extra
compartment's score through a zero-flux duplicate, so the result no longer depends on which optimum
the solver returns. On the dual-target toy both Gurobi **and** GLPK now return genuine dual-targeting
`r1 = {c, m}, r2 = {m}` with every placement flux-active (real `A`-into-`m` and `Q`-out-of-`m`
transports), and at high transport cost it correctly falls back to mono rather than inventing a dead
placement. 13/13 unit tests pass on both backends (including a regression that FVA-checks every
multi-placement carries flux), and the genome-scale yeast-GEM mono tests are unaffected.

The reverse-direction activity gate must be written as a Big-M *implication* (`aF=1 â‡’ v â‰¥ Îµ`,
vacuous when `aF=0`), **not** a hard bound `v â‰¥ ÎµÂ·aF`: the latter forces `v â‰¥ 0` whenever `aF=0` and,
together with the reverse gate forcing `v â‰¤ 0`, pins every reversible reaction to `v = 0` â€” turning a
growth-feasible model infeasible. (An early version had exactly that bug; it is fixed and covered by
a reversible-reaction regression test.)

**Cost.** Adds, per movable reaction, an activity binary per compartment (plus a reverse binary for
reversible reactions) and a home/used binary â€” a materially larger MILP at genome scale (use
`time_limit`/`mip_gap`). Benchmarked on yeast-GEM it stays sound (zero dead placements) and solves
to optimality up to ~300 relocated reactions in well under a minute (see
[yeast_validation.md](yeast_validation.md)).

**`Îµ` deadzone (why the default scales with the floor).** The threshold creates a deadzone
`(0, Îµ)`: a *used* reaction (no inactive home) that the network forces to carry a tiny but nonzero
flux in some compartment must clear `Îµ` there, or the model is **infeasible** â€” not merely mono. A
fixed `Îµ` far above the ghost-flux floor (e.g. `1e-4`) therefore makes genome-scale models with small
fluxes infeasible (yeast-GEM, biomass â‰ˆ 0.08, broke above ~80 relocated reactions). So `Îµ` defaults
to `10Â·big_mÂ·integrality_tol` (`1e-5`) â€” as small as the ghost floor safely allows, which keeps the
deadzone below yeast-GEM's meaningful fluxes while still blocking tolerance-faked activity. Models
with even smaller fluxes need `Îµ` lowered further (toward the floor).

**Residual caveat (internal cycles).** The `Îµ` threshold proves a placement carries flux *somewhere*
in the biomass solution, but flux through an **internal/futile cycle** also clears it without doing
productive work â€” so such a placement could still harvest its score. This is **not** limited to
reversible reactions: an irreversible reaction closed into a net-zero loop by a return leg (e.g. a
pinned reverse transport) clears `Îµ` just the same (demonstrated). It is the standard FBA
internal-cycle problem; eliminating it needs loopless/thermodynamic (loop-law) constraints and is
**deferred**. It is a far narrower gap than the zero-flux exploit it replaces (which scored
placements carrying *no* flux at all), but it means "earns score â‡’ genuinely functional" holds only
up to internal-cycle flux.
