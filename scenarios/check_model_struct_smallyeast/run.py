"""Python side of the model-structure-checking scenario.

``check_model`` returns a flat list of ``ModelIssue(category, object_id,
message)``. Only ``category`` and ``object_id`` are compared, as
``(category, entity)`` pairs --- the message text is each implementation's own
prose and was never going to match; see scenario.yml for the categories this
covers and, just as importantly, the ones it deliberately does not.

These four category names are check_model's own, and are compared against
the same four semantic names on the MATLAB side --- NOT against
checkModelStruct's own `category` output, which (see
check_model_struct_smallyeast.m's classify() helper) is a coarser,
order-sensitive classification that mislabels two of these four checks
under names ('empty_id', 'invalid_id') that describe a different concern
entirely, and collapses the other two under one shared name ('unused').

Filtered to the four checks this scenario actually exercises: RAVEN's
checkModelStruct has several more categories (missing_field, wrong_type,
invalid_bounds, invalid_formula, cross_reference, other) that check
RAVEN-struct properties a cobra.Model cannot represent invalidly in the first
place, and check_model does not have them at all. Comparing the two
unfiltered would fail the moment RAVEN flagged any of those, which would be a
scope mismatch, not a disagreement about the four shared checks.
"""

from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import change_gene_reaction_rules, change_reaction_equations
from raven_toolbox.utils import check_model

SHARED_CATEGORIES = {"orphan_metabolite", "orphan_gene", "empty_reaction", "objective"}


def run(ctx):
    inputs = ctx["inputs"]
    model = read_yaml_model(inputs["model"])

    rewritten = inputs["rewritten_reaction"]
    change_reaction_equations(
        model, {str(rewritten["reaction"]): str(rewritten["equation"])},
        mets_by="id", allow_new_mets=False,
    )

    emptied = model.reactions.get_by_id(str(inputs["emptied_reaction"]))
    emptied.subtract_metabolites(dict(emptied.metabolites))

    model.reactions.get_by_id(str(inputs["objective_reaction"])).objective_coefficient = 0.0

    gpr = inputs["gpr_replaced"]
    change_gene_reaction_rules(model, {str(gpr["reaction"]): str(gpr["grRule"])}, replace=True)

    issues = check_model(model)

    pairs = sorted(
        (issue.category, str(issue.object_id) if issue.object_id is not None else "")
        for issue in issues
        if issue.category in SHARED_CATEGORIES
    )
    return {
        "n_issues": len(pairs),
        "issues": [{"category": category, "entity": entity} for category, entity in pairs],
    }
