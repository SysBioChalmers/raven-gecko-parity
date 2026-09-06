"""Python side of the removeBadRxns/remove_bad_reactions toy-model scenario."""
import cobra

from raven_toolbox.manipulation import remove_bad_reactions


def _bad_model() -> cobra.Model:
    m = cobra.Model("bad")
    a = cobra.Metabolite("A", compartment="c", formula="C1")
    b = cobra.Metabolite("B", compartment="c", formula="C1")
    m.add_metabolites([a, b])
    r1 = cobra.Reaction("R1", lower_bound=0, upper_bound=1000)
    r1.add_metabolites({a: -1, b: 1})
    r2 = cobra.Reaction("R2", lower_bound=0, upper_bound=1000)
    r2.add_metabolites({b: -1, a: 2})
    m.add_reactions([r1, r2])
    return m


def run(ctx):
    inputs = ctx["inputs"]
    ignore_both = inputs["ignore_both"]

    # balance_elements is passed explicitly rather than left at its default
    # (C, P, S, N, O): MATLAB's getElementalBalance requires every requested
    # element to actually appear somewhere in the model, and this toy model
    # (formula "C1" throughout) only ever has carbon -- see the .m harness.
    return {
        "default_removes_r2": _checkpoint(_bad_model(), balance_elements=["C"]),
        "ignoring_both_mets_removes_nothing": _checkpoint(
            _bad_model(), ignore_mets=ignore_both, balance_elements=["C"],
        ),
    }


def _checkpoint(model, **kwargs):
    removed = remove_bad_reactions(model, **kwargs)
    return {
        "removed": sorted(removed),
        "remaining": sorted(r.id for r in model.reactions),
    }
