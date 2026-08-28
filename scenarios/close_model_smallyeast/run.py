"""Python side of the model-closing scenario.

RAVEN's closeModel and close_model agree on which reactions are "unit
exchange" (coefficients summing to 1 in absolute value) but close them
through mechanisms that share no structure at all --- see
close_model_smallyeast.m for what closeModel actually does (appends a
metabolite, never touches bounds) and why that still locks the reaction to
zero flux. This compares the one thing both mechanisms are answerable to
regardless of how they work: which reactions get identified, and whether
each one is actually incapable of carrying flux afterwards, checked by
optimising each reaction's own flux to its minimum and maximum rather than
by reading either side's own (incompatible) internal representation.

FVA is forced onto a single process, as gapfill_connect_smallyeast's does,
for the same reason: reproducibility, and one process is plenty for a
53-reaction model.

The solver is named by the scenario rather than inherited from the machine
--- see scenario.yml.
"""

import cobra

from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import close_model

cobra.Configuration().processes = 1


def _is_unit_exchange(rxn):
    """RAVEN's own rule, restated: sum(|coeff|) == 1."""
    total = sum(abs(c) for c in rxn.metabolites.values())
    return abs(total - 1.0) < 1e-9


def _flux_range(model, rxn_id):
    rxn = model.reactions.get_by_id(rxn_id)
    original_objective = model.objective
    original_direction = model.objective_direction
    try:
        model.objective = rxn
        model.objective_direction = "max"
        max_flux = float(model.slim_optimize())
        model.objective_direction = "min"
        min_flux = float(model.slim_optimize())
    finally:
        model.objective = original_objective
        model.objective_direction = original_direction
    return min_flux, max_flux


def run(ctx):
    inputs = ctx["inputs"]
    # Set before any model is read: a cobra model takes its solver from the
    # configuration at construction time.
    cobra.Configuration().solver = str(inputs["python_solver"])

    model = read_yaml_model(inputs["model"])
    model.reactions.get_by_id("glcIN").upper_bound = float(inputs["glc_uptake"])
    model.reactions.get_by_id("o2IN").upper_bound = float(inputs["o2_uptake"])
    model.solver = str(inputs["python_solver"])

    unit_exchange = sorted(rxn.id for rxn in model.reactions if _is_unit_exchange(rxn))

    growth_before = float(model.slim_optimize())

    control_id = str(inputs["control_reaction"])
    control_min_before, control_max_before = _flux_range(model, control_id)

    closed = close_model(model)
    closed.solver = str(inputs["python_solver"])

    growth_after = float(closed.slim_optimize())

    closed_reactions = []
    for rxn_id in unit_exchange:
        lo, hi = _flux_range(closed, rxn_id)
        closed_reactions.append({"reaction": rxn_id, "min_flux": lo, "max_flux": hi})

    control_min_after, control_max_after = _flux_range(closed, control_id)

    return {
        "unit_exchange_reactions": unit_exchange,
        "growth_before": growth_before,
        "growth_after": growth_after,
        "closed_reactions": closed_reactions,
        "control_reaction": control_id,
        "control_min_before": control_min_before,
        "control_max_before": control_max_before,
        "control_min_after": control_min_after,
        "control_max_after": control_max_after,
    }
