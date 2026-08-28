"""Python side of the topological gap-analysis scenario.

``analyse_topology`` and RAVEN's ``gapFillTopological`` are explicit mirrors of
each other --- same fixed-point scope computation, same four result fields, both
citing Meneco (Prigent et al. 2017). What differs is only how the results are
stored: a set of ids and a dict here, a logical vector over ``model.mets`` and a
cell array aligned with ``blockedMets`` there. Both are flattened to sorted
lists of ids and records.

The draft is built by removing reactions from the model rather than by shipping
a second file, so the universal database and the draft cannot drift apart.
"""

from raven_toolbox.gapfilling import analyse_topology
from raven_toolbox.io import read_yaml_model


def run(ctx):
    inputs = ctx["inputs"]
    path = inputs["model"]

    draft = read_yaml_model(path)
    universal = read_yaml_model(path)

    removed = [str(rxn) for rxn in inputs["removed_reactions"]]
    # remove_orphans left at its default: metabolites and genes that fall out
    # of use stay in the model, matching removeReactions' removeUnusedMets
    # default on the other side. Removing them would change the target set.
    draft.remove_reactions(removed)

    result = analyse_topology(
        draft,
        universal,
        seeds=[str(m) for m in inputs["seeds"]],
        targets=[str(m) for m in inputs["targets"]],
        # The summary goes to stdout and has no counterpart in the result
        # document; the MATLAB side is silenced the same way.
        verbose=False,
    )

    blocked = sorted(result.blocked_metabolites)
    return {
        "n_removed": len(removed),
        "n_reachable": len(result.reachable_metabolites),
        "reachable_metabolites": sorted(result.reachable_metabolites),
        "n_blocked": len(blocked),
        "blocked_metabolites": blocked,
        # A list of records rather than an object keyed by metabolite id, and
        # every blocked metabolite present even when nothing in the universal
        # database produces it --- an absent key would read as a structural
        # difference rather than as an empty candidate list.
        "candidate_reactions": [
            {
                "metabolite": met,
                "reactions": sorted(result.candidate_reactions.get(met, [])),
            }
            for met in blocked
        ],
        "pruning_fraction": float(result.pruning_fraction),
    }
