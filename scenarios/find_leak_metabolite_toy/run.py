"""Python side of the findLeakMetabolite/find_leak_metabolite toy-model scenario."""
import cobra

from raven_toolbox.gapfilling import find_leak_metabolite


def _leak_model() -> cobra.Model:
    m = cobra.Model("leak")
    a = cobra.Metabolite("A", name="alanine", compartment="c")
    b = cobra.Metabolite("B", compartment="c")
    c = cobra.Metabolite("C", compartment="c")
    d = cobra.Metabolite("D", compartment="c")
    m.add_metabolites([a, b, c, d])

    r1 = cobra.Reaction("R1", lower_bound=0, upper_bound=1000)
    r1.add_metabolites({a: -1, b: 1})
    r2 = cobra.Reaction("R2", lower_bound=0, upper_bound=1000)
    r2.add_metabolites({b: -1, a: 2})
    r3 = cobra.Reaction("R3", lower_bound=0, upper_bound=1000)
    r3.add_metabolites({c: -1, d: -1})
    m.add_reactions([r1, r2, r3])
    return m


def run(ctx):
    inputs = ctx["inputs"]
    ignore_all = inputs["ignore_all"]
    ignore_by_name = inputs["ignore_by_name"]

    return {
        "produce_default": _checkpoint(_leak_model(), "produce"),
        "consume_pair": _checkpoint(_leak_model(), "consume"),
        "produce_all_ignored": _checkpoint(_leak_model(), "produce", ignore_mets=ignore_all),
        "produce_ignore_by_name": _checkpoint(
            _leak_model(), "produce", ignore_mets=ignore_by_name, is_names=True,
        ),
    }


def _checkpoint(model, direction, **kwargs):
    res = find_leak_metabolite(model, direction, **kwargs)
    if res.status != "optimal":
        return {"status": "infeasible", "metabolites": [], "fluxes": {}}
    return {
        "status": "optimal",
        "metabolites": sorted(res.metabolites),
        "fluxes": res.fluxes.round(9).to_dict(),
    }
