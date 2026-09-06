"""Python side of the fitParameters/fit_parameters toy-model scenario."""
import cobra

from raven_toolbox.biomass import ParameterPosition, fit_parameters


def _chain_model() -> cobra.Model:
    m = cobra.Model("fit_toy", name="fit_toy")
    a = cobra.Metabolite("a", compartment="c")
    b = cobra.Metabolite("b", compartment="c")
    x = cobra.Metabolite("x", compartment="c")
    m.add_metabolites([a, b, x])

    ex_a = cobra.Reaction("EX_A", lower_bound=0, upper_bound=1000)
    ex_a.add_metabolites({a: 1})
    ex_b = cobra.Reaction("EX_B", lower_bound=0, upper_bound=1000)
    ex_b.add_metabolites({b: 1})
    ra = cobra.Reaction("RA", lower_bound=0, upper_bound=1000)
    ra.add_metabolites({a: -1, x: 1})
    rb = cobra.Reaction("RB", lower_bound=0, upper_bound=1000)
    rb.add_metabolites({b: -1, x: 1})
    growth = cobra.Reaction("GROWTH", lower_bound=0, upper_bound=1000)
    growth.add_metabolites({x: -1.0})  # placeholder; fit_parameters overwrites this
    m.add_reactions([ex_a, ex_b, ra, rb, growth])
    return m


def run(ctx):
    model = _chain_model()
    x_values = [[2.0, 4.0], [4.0, 2.0], [6.0, 6.0]]
    values_to_fit = [[3.0], [3.0], [6.0]]  # true k=2: (a+b)/2
    positions = [ParameterPosition((("GROWTH", "x"),), (True,))]

    result = fit_parameters(
        model, ["EX_A", "EX_B"], x_values, ["GROWTH"], values_to_fit, positions,
        initial_guess=[1.0],
    )

    fitted_growth = result.model.reactions.get_by_id("GROWTH")
    fitted_x = result.model.metabolites.get_by_id("x")

    return {
        # A bare scalar, matching MATLAB's own single-element serialization:
        # this scenario fits exactly one parameter.
        "parameters": float(result.parameters[0]),
        "fitness_score": result.fitness_score,
        "fitted_coefficient": fitted_growth.metabolites[fitted_x],
    }
