# The BRENDA search-order question

geckopy's `fuzzy_kcat_matching` carries a `MATLAB-COMPAT` note claiming MATLAB's search order
inside `mainMatch` tries an organism-specific specific-activity match ("org-SA") *before* a
looser any-organism direct-kcat match ("any-org-kcat"), and that when both are available for a
reaction, MATLAB's `kcatList.origin` reports the org-SA match as origin `5` --- geckopy replicates
this. [gecko-behaviour-parity-plan.md](gecko-behaviour-parity-plan.md) flagged this as needing
confirmation before the kcat-chain scenario is written: is it a real MATLAB behaviour geckopy is
right to copy, or a misreading of a MATLAB bug that would need fixing upstream instead?

Tracked against gecko-behaviour-parity-plan.md, Tier 2.

## The short answer

**geckopy is right. There is no divergence here.** Confirmed by executing both implementations on
the same purpose-built case: MATLAB really does try org-SA before any-org-kcat, org-SA really does
win when both are available, and MATLAB's own final `origin` output really is `5` for that match
--- exactly what geckopy's `MATLAB-COMPAT` note says and exactly what geckopy's own test suite
already asserts. The `fuzzy` checkpoint can compare `origin` directly with no special-casing.

The one thing worth recording is *why* this took two rounds to confirm: `fuzzyKcatMatching.m`
computes the origin number twice, through two independent numbering schemes that partially
disagree with each other, and reading only the first one gives the wrong answer.

## Evidence

### MATLAB's two origin numbers

Inside `mainMatch` (the function that actually walks the six match levels), each successful branch
sets a local `origin` variable directly:

```matlab
%If no match, try to match organism but for any substrate (SA*MW):
[kcat,matches] = matchKcat(EC,subs,substrCoeff,KCATcell,name,false,true,...)   % org + SA
if matches > 0
    origin = 4;
    %If no match, try any organism and any substrate:
else
    [kcat,matches] = matchKcat(EC,subs,substrCoeff,KCATcell,'',false,false,...)  % any-org + kcat
    if matches > 0
        origin = 5;
```

Read on its own, this says org-SA is `4` and any-org-kcat is `5` --- the *opposite* of the
top-of-file docstring, which documents `4: any organism, any substrate, kcat` and
`5: correct organism, specific activity`. This is the reading that led to a wrong prediction
before executing anything (see "What went wrong first," below).

But this local `origin` value never reaches the caller directly. `iterativeMatch` (the function
that calls `mainMatch` once per wildcard level) uses it only to decide *which named boolean flag*
to set:

```matlab
dir.org_sa(i)  = matches*(origin == 4);
dir.rest_ns(i) = matches*(origin == 5);
```

And `fuzzyKcatMatching` (the outer function) then computes the number it actually returns from the
*column position* of each named flag in a fixed array, unrelated to the local `origin` values that
set those flags:

```matlab
origin = [kcatInfo.info.org_s kcatInfo.info.rest_s kcatInfo.info.org_ns kcatInfo.info.rest_ns kcatInfo.info.org_sa kcatInfo.info.rest_sa];
for i=1:6
    kcatList.origin(find(origin(:,i))) = i;
end
```

`org_sa` is the **5th** entry in that array and `rest_ns` is the **4th** --- so a match that set
`dir.org_sa` (via local `origin == 4`) is reported to the caller as **origin 5**, and a match that
set `dir.rest_ns` (via local `origin == 5`) is reported as **origin 4**. The second renumbering
exactly undoes the first. MATLAB's own authors flag the awkwardness in a comment right above it:
`% This can be refactored, iterativeMatch and their nested functions can just directly report the
origin number.` --- they did not.

### Executed, not just read

A model with one reaction (`r1`, EC `1.1.1.1`, one substrate `alpha`), organism `yeast`, and a
BRENDA fixture built so that:

* `max_KCAT.txt` has one row for EC `1.1.1.1`: substrate `different_substrate`, organism `ecoli`,
  kcat `100` --- available only via the any-org-kcat level (wrong substrate for the org+substrate
  levels, wrong organism for the org-only levels).
* `max_SA.txt` / `max_MW.txt` have one matching pair for EC `1.1.1.1`, organism `yeast`, scaled to
  derive kcat `23` --- available via the org-SA level.

Both candidates are reachable; only their search order decides which one is returned. Run against
`fuzzyKcatMatching` on `develop4` (`2937e0b3`):

```
=== kcatList ===
kcat:   23
origin: 5
wildcardLvl: 0
```

org-SA wins (kcat `23`, not the ecoli row's `100`), and MATLAB's own `kcatList.origin` for it is
`5`. geckopy's existing `test_org_sa_wins_over_any_org_kcat_when_both_present`
(`tests/test_fuzzy_kcat_matching.py`) builds the equivalent case and asserts exactly this: kcat
`23.0`, origin `5`. Same winner, same value, same label.

### What went wrong first

The first pass at this question read only `mainMatch`'s local `origin = 4` / `origin = 5` lines,
cross-checked them against `iterativeMatch`'s `dir.org_sa` / `dir.rest_ns` naming, and concluded
MATLAB's real output must be the reverse of geckopy's --- org-SA as `4`, any-org-kcat as `5`. That
cross-check was real but insufficient: it confirmed *which flag* each local origin value sets, not
what number the outer function assigns to that flag afterwards. Only running `fuzzyKcatMatching`
end to end surfaces the second renumbering. Recorded here as the reason this document exists at
all rather than a one-line "confirmed" note --- the wrong reading was plausible enough to have
shipped in a less careful pass, and the fixture-only ecTestGEM data (all `sa_max` / `kcat_max`
join to nothing, see [brenda-reconciliation.md](brenda-reconciliation.md)) can't be used to catch
it, since it never reaches the org-SA level at all.

## What this means for the kcat chain

Nothing needs fixing on either side, and the `fuzzy` checkpoint does not need to assert a
divergence for the search order or for `origin`. It should still assert `origin` (not just `kcat`)
at that checkpoint, precisely because it is derived through the confusing double-renumbering above
--- a future refactor of `mainMatch`/`iterativeMatch` on the MATLAB side (the kind the function's
own comment invites) could easily fix the *local* numbering while leaving the *external* one
unchanged, or vice versa, and only a scenario that checks the actual returned value would notice.

The ecTestGEM fixture does not exercise the org-SA level at all (its SA and MW rows don't share an
organism --- see brenda-reconciliation.md), so the `fuzzy` checkpoint's own fixture will need a
matching-organism SA/MW pair if it is meant to exercise this path, same gap noted there.

## Reproducing

The repro model, adapter and fixture are not committed (purpose-built for this question, not part
of any scenario). Rebuild by pointing a `ModelAdapter` at a folder containing:

`max_KCAT.txt`: one row, EC `1.1.1.1`, a substrate the model reaction doesn't use, an organism
other than the model's.

`max_SA.txt` / `max_MW.txt`: one matching pair, EC `1.1.1.1`, the model's own organism.

```matlab
kcatList = fuzzyKcatMatching(model, 'modelAdapter', adapter);
```

Python, using geckopy's own test:

```bash
pytest tests/test_fuzzy_kcat_matching.py::test_org_sa_wins_over_any_org_kcat_when_both_present -v
```
