"""Python side of the variance-bounds scenario.

``set_variance_bounds`` and ``setParam``'s "var" mode take the same three
numbers per reaction --- a measured value, a percent, the reaction itself ---
and compute the same sign-dependent band. Only this one mode of setParam is
covered; see scenario.yml for why the other six are not.

Reactions outside the two checkpoints are fingerprinted before and after: the
function mutates by reaction identity, and a miscounted index would move a
bound on the wrong reaction, which only checking "everything else" catches.
"""

from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import set_variance_bounds


def run(ctx):
    inputs = ctx["inputs"]
    model = read_yaml_model(inputs["model"])

    touched = set(inputs["distinct"]["values"]) | set(inputs["broadcast"]["reactions"])
    before_other = {
        rxn.id: (float(rxn.lower_bound), float(rxn.upper_bound))
        for rxn in model.reactions
        if rxn.id not in touched
    }

    distinct = inputs["distinct"]
    rxn_ids = sorted(distinct["values"])
    values = [float(distinct["values"][rxn_id]) for rxn_id in rxn_ids]
    set_variance_bounds(model, rxn_ids, values, float(distinct["percent"]))

    broadcast = inputs["broadcast"]
    broadcast_ids = [str(rxn) for rxn in broadcast["reactions"]]
    set_variance_bounds(model, broadcast_ids, float(broadcast["value"]), float(broadcast["percent"]))

    after_other = {
        rxn.id: (float(rxn.lower_bound), float(rxn.upper_bound))
        for rxn in model.reactions
        if rxn.id not in touched
    }

    return {
        "n_untouched_reactions_checked": len(before_other),
        # The point of the scenario: this should be empty on both sides.
        "unexpectedly_changed_reactions": sorted(
            rid for rid in before_other if before_other[rid] != after_other.get(rid)
        ),
        "distinct": [_bounds(model, rxn_id) for rxn_id in rxn_ids],
        "broadcast": [_bounds(model, rxn_id) for rxn_id in sorted(broadcast_ids)],
    }


def _bounds(model, rxn_id):
    rxn = model.reactions.get_by_id(rxn_id)
    return {
        "reaction": rxn_id,
        "lower_bound": float(rxn.lower_bound),
        "upper_bound": float(rxn.upper_bound),
    }
