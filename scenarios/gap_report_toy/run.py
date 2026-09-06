"""Python side of the gapReport/gap_report toy-model scenario."""
import cobra

from raven_toolbox.gapfilling import gap_report


def _gap_report_model() -> cobra.Model:
    m = cobra.Model("gaps", name="Gaps")
    glc = cobra.Metabolite("glc", compartment="c")
    pyr = cobra.Metabolite("pyr", compartment="c")
    co2 = cobra.Metabolite("co2", compartment="c")
    x = cobra.Metabolite("x", compartment="c")
    y = cobra.Metabolite("y", compartment="c")
    z = cobra.Metabolite("z", compartment="c")
    p = cobra.Metabolite("P", compartment="c")
    q = cobra.Metabolite("Q", compartment="c")
    m.add_metabolites([glc, pyr, co2, x, y, z, p, q])

    ex_glc = cobra.Reaction("EX_glc", lower_bound=-10, upper_bound=1000)
    ex_glc.add_metabolites({glc: -1})
    r1 = cobra.Reaction("R1", lower_bound=0, upper_bound=1000)
    r1.add_metabolites({glc: -1, pyr: 1})
    r2 = cobra.Reaction("R2", lower_bound=0, upper_bound=1000)
    r2.add_metabolites({pyr: -1, co2: 1})
    dm_co2 = cobra.Reaction("DM_co2", lower_bound=0, upper_bound=1000)
    dm_co2.add_metabolites({co2: -1})
    r3 = cobra.Reaction("R3", lower_bound=0, upper_bound=1000)
    r3.add_metabolites({x: -1, y: 1})
    r4 = cobra.Reaction("R4", lower_bound=0, upper_bound=1000)
    r4.add_metabolites({p: -1, q: 1})
    r5 = cobra.Reaction("R5", lower_bound=0, upper_bound=1000)
    r5.add_metabolites({q: -1, p: 2})
    m.add_reactions([ex_glc, r1, r2, dm_co2, r3, r4, r5])
    return m


def run(ctx):
    result = gap_report(_gap_report_model())

    return {
        "no_flux_reactions": sorted(result.no_flux_reactions),
        "no_flux_reactions_relaxed": sorted(result.no_flux_reactions_relaxed),
        "subgraph_sizes": sorted((len(g) for g in result.subgraphs), reverse=True),
        "not_produced_metabolites": sorted(result.not_produced_metabolites),
        "needed_for_production": {
            mid: sorted(unlocked) for mid, unlocked in result.needed_for_production.items()
        },
        "min_to_connect": [
            {"metabolite": entry.metabolite, "connects": entry.connects}
            for entry in result.min_to_connect
        ],
    }
