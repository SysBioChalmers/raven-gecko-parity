"""Python side of the multi-model comparison scenario.

``compare_models`` returns a :class:`ModelComparison` of pandas DataFrames;
only ``.reactions`` (the presence matrix) is used here --- see scenario.yml
for why metabolites, genes, subsystems, similarity and tasks are not.

Model ids are fixed and known (``full`` / ``minus_two`` /
``minus_one_plus_one``) rather than left to cobra's default
``model_<i>``-if-missing fallback, so both sides can use them directly as
column/field names instead of reproducing that fallback logic.
"""

from raven_toolbox.comparison import compare_models
from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import add_reactions_from_equations

MODEL_IDS = ("full", "minus_two", "minus_one_plus_one")


def run(ctx):
    inputs = ctx["inputs"]
    path = inputs["model"]

    full = read_yaml_model(path)
    full.id = "full"

    minus_two = read_yaml_model(path)
    minus_two.id = "minus_two"
    minus_two.remove_reactions(
        [str(rxn) for rxn in inputs["minus_two_removed"]], remove_orphans=False
    )

    minus_one_plus_one = read_yaml_model(path)
    minus_one_plus_one.id = "minus_one_plus_one"
    minus_one_plus_one.remove_reactions(
        [str(inputs["minus_one_plus_one_removed"])], remove_orphans=False
    )
    added = inputs["minus_one_plus_one_added"]
    add_reactions_from_equations(
        minus_one_plus_one,
        [{"id": str(added["id"]), "equation": str(added["equation"]), "name": str(added["name"])}],
        mets_by="id", allow_new_mets=False, allow_new_genes=False,
    )

    comparison = compare_models([full, minus_two, minus_one_plus_one])
    presence = comparison.reactions

    return {
        "model_ids": list(comparison.model_ids),
        "n_reactions_per_model": {
            mid: int(presence[mid].sum()) for mid in MODEL_IDS
        },
        "n_reactions_total": len(presence.index),
        "reactions": [
            {
                "reaction": rxn_id,
                "full": int(presence.at[rxn_id, "full"]),
                "minus_two": int(presence.at[rxn_id, "minus_two"]),
                "minus_one_plus_one": int(presence.at[rxn_id, "minus_one_plus_one"]),
            }
            for rxn_id in sorted(presence.index)
        ],
    }
