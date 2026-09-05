"""Python side of the replaceMets/replace_metabolite toy-model scenario."""
import cobra

from raven_toolbox.manipulation import replace_metabolite


def _name_based_model() -> cobra.Model:
    m = cobra.Model("t")
    a = cobra.Metabolite("a", name="oxygen", compartment="c")
    b = cobra.Metabolite("b", name="o2", compartment="c")
    x = cobra.Metabolite("x", name="x", compartment="c")
    d = cobra.Metabolite("d", name="d", compartment="c")
    m.add_metabolites([a, b, x, d])
    r1 = cobra.Reaction("r1", lower_bound=-1000, upper_bound=1000)
    r1.add_metabolites({a: -1, x: 1})
    r2 = cobra.Reaction("r2", lower_bound=-1000, upper_bound=1000)
    r2.add_metabolites({b: -1, x: 1})
    unrelated1 = cobra.Reaction("unrelated1", lower_bound=-1000, upper_bound=1000)
    unrelated1.add_metabolites({d: -1})
    unrelated2 = cobra.Reaction("unrelated2", lower_bound=-1000, upper_bound=1000)
    unrelated2.add_metabolites({d: -1})
    m.add_reactions([r1, r2, unrelated1, unrelated2])
    return m


def _identifiers_model() -> cobra.Model:
    m = cobra.Model("t2")
    a = cobra.Metabolite("a", name="oxygen", compartment="c")
    b = cobra.Metabolite("b", name="o2", compartment="c")
    x = cobra.Metabolite("x", name="x", compartment="c")
    m.add_metabolites([a, b, x])
    r1 = cobra.Reaction("r1", lower_bound=-1000, upper_bound=1000)
    r1.add_metabolites({a: -1, x: 1})
    m.add_reactions([r1])
    return m


def _checkpoint(model: cobra.Model) -> dict:
    return {
        "metabolites": sorted(
            (
                {"id": met.id, "name": met.name, "compartment": met.compartment}
                for met in model.metabolites
            ),
            key=lambda row: row["id"],
        ),
        "reactions": {
            rxn.id: sorted(
                (
                    {"metabolite": met.id, "coefficient": coef}
                    for met, coef in rxn.metabolites.items()
                ),
                key=lambda row: row["metabolite"],
            )
            for rxn in model.reactions
        },
    }


def run(ctx):
    inputs = ctx["inputs"]

    name_model = _name_based_model()
    replace_metabolite(
        name_model, inputs["name_based"]["metabolite"], inputs["name_based"]["replacement"],
    )

    id_model = _identifiers_model()
    replace_metabolite(
        id_model, inputs["identifiers_based"]["metabolite"], inputs["identifiers_based"]["replacement"],
        identifiers=True,
    )

    return {
        "name_based": _checkpoint(name_model),
        "identifiers_based": _checkpoint(id_model),
    }
