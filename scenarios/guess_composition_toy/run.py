"""Python side of the guessComposition/guess_composition toy-model scenario."""
import cobra

from raven_toolbox.utils import guess_composition


def _chain_model() -> cobra.Model:
    m = cobra.Model("guess_composition_toy", name="guess_composition_toy")
    a = cobra.Metabolite("A", name="A", formula="CH4", compartment="c")
    b = cobra.Metabolite("B", name="B", compartment="c")
    c = cobra.Metabolite("C", name="C", compartment="c")
    orphan = cobra.Metabolite("Orphan", name="Orphan", compartment="c")
    m.add_metabolites([a, b, c, orphan])

    r1 = cobra.Reaction("R1", lower_bound=0, upper_bound=1000)
    r1.add_metabolites({a: -1, b: 1})
    r2 = cobra.Reaction("R2", lower_bound=0, upper_bound=1000)
    r2.add_metabolites({b: -1, c: 1})
    m.add_reactions([r1, r2])
    return m


def run(ctx):
    model = _chain_model()
    result = guess_composition(model, print_results=False)

    return {
        "guessed_for": sorted(result.guessed),
        "could_not_guess": sorted(result.could_not_guess),
        "b_formula": model.metabolites.get_by_id("B").formula,
        "c_formula": model.metabolites.get_by_id("C").formula,
    }
