"""Python side of the getMinNrFluxes/get_min_nr_fluxes toy-model scenario."""
import cobra

from raven_toolbox.analysis import get_min_nr_fluxes


def _two_source_model() -> cobra.Model:
    m = cobra.Model("t")
    x = cobra.Metabolite("X", compartment="c")
    m.add_metabolites([x])
    source1 = cobra.Reaction("source1", lower_bound=0, upper_bound=1000)
    source1.add_metabolites({x: 1})
    source2 = cobra.Reaction("source2", lower_bound=0, upper_bound=1000)
    source2.add_metabolites({x: 1})
    demand = cobra.Reaction("demand", lower_bound=5, upper_bound=5)
    demand.add_metabolites({x: -1})
    m.add_reactions([source1, source2, demand])
    return m


def run(ctx):
    inputs = ctx["inputs"]
    to_minimize = inputs["to_minimize"]
    scores = inputs["scores"]

    tie_broken = _checkpoint(_two_source_model(), to_minimize, scores)

    infeasible_model = _two_source_model()
    infeasible_model.reactions.get_by_id("source1").upper_bound = 0
    infeasible_model.reactions.get_by_id("source2").upper_bound = 0
    infeasible = _checkpoint(infeasible_model, to_minimize, scores)

    return {"tie_broken_by_scores": tie_broken, "infeasible": infeasible}


def _checkpoint(model, to_minimize, scores):
    res = get_min_nr_fluxes(model, to_minimize, scores=scores)
    return {
        "status": res.status,
        "active": sorted(res.active),
        "fluxes": {} if res.fluxes.empty else res.fluxes.round(9).to_dict(),
    }
