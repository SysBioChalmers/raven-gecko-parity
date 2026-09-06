"""Python side of the traceFluxPath/trace_flux_path toy-model scenario."""
import cobra
import pandas as pd

from raven_toolbox.analysis import trace_flux_path


def _junction_model() -> cobra.Model:
    m = cobra.Model("junction")
    a = cobra.Metabolite("A", compartment="c")
    b = cobra.Metabolite("B", compartment="c")
    c = cobra.Metabolite("C", compartment="c")
    e = cobra.Metabolite("E", compartment="c")
    d = cobra.Metabolite("D", compartment="c")
    d2 = cobra.Metabolite("D2", compartment="c")
    atp = cobra.Metabolite("atp_c", name="ATP", compartment="c")
    m.add_metabolites([a, b, c, e, d, d2, atp])

    r1 = cobra.Reaction("R1", lower_bound=0, upper_bound=1000)
    r1.add_metabolites({a: -1, b: 1, atp: 1})
    r2a = cobra.Reaction("R2a", lower_bound=0, upper_bound=1000)
    r2a.add_metabolites({b: -1, c: 1})
    r2b = cobra.Reaction("R2b", lower_bound=0, upper_bound=1000)
    r2b.add_metabolites({b: -1, e: 1})
    r3 = cobra.Reaction("R3", lower_bound=0, upper_bound=1000)
    r3.add_metabolites({c: -1, d: 1})
    r4 = cobra.Reaction("R4", lower_bound=0, upper_bound=1000)
    r4.add_metabolites({e: -1, d: 1})
    r5 = cobra.Reaction("R5", lower_bound=0, upper_bound=1000)
    r5.add_metabolites({atp: -1, d2: 1})
    m.add_reactions([r1, r2a, r2b, r3, r4, r5])
    return m


_FLUXES = pd.Series({"R1": 10.0, "R2a": 7.0, "R2b": 3.0, "R3": 7.0, "R4": 3.0, "R5": 10.0})


def run(ctx):
    model = _junction_model()

    return {
        "direct_junction": _checkpoint(model, "R1", "R2a"),
        "two_hop_majority": _checkpoint(model, "R1", "R3"),
        "minority_branch": _checkpoint(model, "R1", "R4"),
        "currency_blocked_by_default": _checkpoint(model, "R1", "R5"),
        "currency_route_when_allowed": _checkpoint(model, "R1", "R5", trace_material=False),
        "max_hops_prunes": _checkpoint(model, "R1", "R3", max_hops=1),
    }


def _checkpoint(model, from_rxn, to_rxn, **kwargs):
    result = trace_flux_path(model, _FLUXES, from_rxn, to_rxn, **kwargs)
    return {
        "reactions": result.reactions,
        "metabolites": result.metabolites,
        "cumulative_fraction": result.cumulative_fraction,
    }
