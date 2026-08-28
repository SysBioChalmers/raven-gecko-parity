"""Python side of the connectivity gap-filling scenario.

``connect_blocked_reactions`` returns a :class:`GapFillResult` where RAVEN's
``fillGaps`` returns four parallel outputs; the three that describe the outcome
line up directly (``added_reactions`` / ``addedRxns``, ``newly_connected`` /
``newConnected``, ``cannot_connect`` / ``cannotConnect``).

FVA is forced onto a single process. cobra defaults to running it across
several, which makes the run harder to reproduce and does not survive the way
this harness loads a scenario module; one process is also plenty for a
53-reaction model.

The solver is named by the scenario rather than inherited from the machine, so
that both sides are demonstrably solving with the same one --- see scenario.yml.
"""

import cobra

from raven_toolbox.gapfilling import connect_blocked_reactions
from raven_toolbox.io import read_yaml_model

cobra.Configuration().processes = 1


def run(ctx):
    inputs = ctx["inputs"]
    # Set before any model is read: a cobra model takes its solver from the
    # configuration at construction time.
    cobra.Configuration().solver = str(inputs["python_solver"])

    def prepared(removed):
        model = read_yaml_model(inputs["model"])
        for rxn_id in inputs["opened_reactions"]:
            model.reactions.get_by_id(str(rxn_id)).upper_bound = float(
                inputs["opened_upper_bound"]
            )
        model.solver = str(inputs["python_solver"])
        if removed:
            model.remove_reactions([str(rxn) for rxn in removed])
        else:
            # The template. Renamed because fillGaps refuses a reference model
            # sharing the draft's id; done here too so both sides start from
            # identical inputs.
            model.id = str(inputs["template_id"])
        return model

    return {
        "single": _checkpoint(inputs, prepared(inputs["single_removed"]), prepared([])),
        "double": _checkpoint(inputs, prepared(inputs["double_removed"]), prepared([])),
    }


def _checkpoint(inputs, draft, template):
    before = {rxn.id for rxn in draft.reactions}

    result = connect_blocked_reactions(
        draft,
        template,
        allow_net_production=bool(inputs["allow_net_production"]),
    )

    return {
        "n_reactions_before": len(before),
        "n_added": len(result.added_reactions),
        "added_reactions": sorted(result.added_reactions),
        "n_newly_connected": len(result.newly_connected),
        "newly_connected": sorted(result.newly_connected),
        "n_cannot_connect": len(result.cannot_connect),
        "cannot_connect": sorted(result.cannot_connect),
        # The filled model, so a repair that picked the right reactions but
        # assembled them into something else would not pass on the lists alone.
        "filled_reactions": sorted(rxn.id for rxn in result.model.reactions),
    }
