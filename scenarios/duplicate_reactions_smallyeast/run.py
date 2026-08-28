"""Python side of the duplicate-detection scenario.

``find_duplicate_reactions`` returns groups of reaction objects;
``findDuplicateRxns`` returns every pairwise combination as reaction indices.
Both are reduced here to sorted lists of reaction ids ordered by their first
member, which is the one form that says the same thing on both sides.

The expanded fixture is built rather than shipped: ``expand_model`` splits each
isozyme rule into one reaction per AND-clause, which manufactures duplicates the
way an expand-then-contract pipeline does. That is safe to lean on because
``expandModel`` is itself compared by model_manipulation_smallyeast.
"""

from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import expand_model, find_duplicate_reactions


def run(ctx):
    path = ctx["inputs"]["model"]

    def plain():
        return read_yaml_model(path)

    def expanded():
        model = read_yaml_model(path)
        expand_model(model)
        return model

    return {
        "plain_any_direction": _checkpoint(plain(), ignore_direction=True),
        "plain_same_direction": _checkpoint(plain(), ignore_direction=False),
        "expanded_any_direction": _checkpoint(expanded(), ignore_direction=True),
        "expanded_same_direction": _checkpoint(expanded(), ignore_direction=False),
    }


def _checkpoint(model, *, ignore_direction):
    groups = find_duplicate_reactions(model, ignore_direction=ignore_direction)

    members = sorted(
        (sorted(rxn.id for rxn in group) for group in groups),
        key=lambda ids: ids[0],
    )

    return {
        "n_reactions": len(model.reactions),
        "n_groups": len(members),
        # Total reactions implicated, not the number of groups: a group of
        # three and three groups of two are different findings that would
        # otherwise both read as "3".
        "n_duplicate_reactions": sum(len(ids) for ids in members),
        "groups": [{"members": ids} for ids in members],
    }
