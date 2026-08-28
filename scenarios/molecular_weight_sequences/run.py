"""Python side of the molecular-weight scenario.

``calculate_mw`` takes a bare string and returns a float --- no model, no adapter, nothing
to resolve. Every sequence in the declaration is fed through it once and the results
returned in declaration order, not sorted: docs/scenarios.md's default is to sort
everything, but this fixture is a flat list of independent, hand-chosen test cases rather
than model output, and keeping input order is what makes a result that stops matching
scenario.yml's per-sequence comments easy to locate --- the same reasoning
``gpr_dnf_rules`` uses for its own rule list.

``calculate_mw`` legitimately returns NaN for a sequence with no recognisable residues.
That is not the harness's NaN --- MATLAB's ``calculateMW`` never produces one, since it
always starts from and returns at least the water mass --- so it is emitted as-is rather
than folded into a has-value/value pair the way an absent metabolite charge is elsewhere in
this repo. The point of this scenario is exactly that MATLAB says 18 and Python says NaN for
the same input; the has-value convention exists to hide a difference the *harness*
introduces, not the one being measured here.
"""

from geckopy import calculate_mw


def run(ctx):
    sequences = list(ctx["inputs"]["sequences"])
    return {
        "sequences": [{"sequence": sequence, "mw": float(calculate_mw(sequence))} for sequence in sequences],
    }
