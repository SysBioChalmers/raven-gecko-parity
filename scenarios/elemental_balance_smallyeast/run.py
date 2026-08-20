"""Python side of the elemental-balance scenario.

Returns plain data only: `parity compare` diffs whatever this returns against whatever
run.m returns, so the two must agree on the *shape* as well as the numbers. Keep the
structure boring and sorted --- no dict ordering surprises, no floats that are really ints.
"""

from collections import Counter

from raven_toolbox.io import read_yaml_model
from raven_toolbox.utils import get_elemental_balance

#: How many unbalanced reactions to report element-by-element. Bounded so the result file
#: stays readable, sorted so the slice is deterministic.
DETAIL_LIMIT = 25


def run(ctx):
    zero_tolerance = float(ctx["inputs"]["zero_tolerance"])
    model = read_yaml_model(ctx["inputs"]["model"])
    balances = get_elemental_balance(model)

    seen = Counter(balance.status for balance in balances)
    # Fixed keys, always present: an absent key would otherwise read as a structural
    # difference rather than a count of zero. "error" has no Python counterpart today and
    # exists so RAVEN's balanceStatus == -2 shows up as a difference instead of vanishing
    # into "unknown".
    verdicts = {status: int(seen.get(status, 0)) for status in ("balanced", "unbalanced", "unknown", "error")}

    unbalanced = sorted(b.reaction_id for b in balances if b.status == "unbalanced")
    detailed = set(unbalanced[:DETAIL_LIMIT])

    # Element-level detail: enough to catch a disagreement about *how* a reaction is
    # unbalanced, not merely that it is. Lists of records rather than keyed objects, because
    # reaction ids are not always valid MATLAB struct field names.
    detail = [
        {
            "reaction": balance.reaction_id,
            "elements": [
                {"element": str(element), "amount": float(amount)}
                for element, amount in sorted(dict(balance.imbalance).items())
                if abs(amount) > zero_tolerance
            ],
        }
        for balance in sorted(balances, key=lambda b: b.reaction_id)
        if balance.reaction_id in detailed
    ]

    return {
        "n_reactions": len(balances),
        "verdicts": verdicts,
        "n_unbalanced": len(unbalanced),
        "unbalanced_reactions": unbalanced,
        "imbalance_detail": detail,
    }
