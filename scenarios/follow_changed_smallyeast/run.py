"""Python side of the followChanged/follow_changed scenario."""
import pandas as pd

from raven_toolbox.analysis import follow_changed
from raven_toolbox.io import read_yaml_model


def run(ctx):
    inputs = ctx["inputs"]
    model = read_yaml_model(inputs["model"])

    fluxes_a = pd.Series(0.0, index=[r.id for r in model.reactions])
    fluxes_a.update(pd.Series(inputs["fluxes_a"], dtype=float))
    fluxes_b = pd.Series(0.0, index=[r.id for r in model.reactions])
    fluxes_b.update(pd.Series(inputs["fluxes_b"], dtype=float))

    result = follow_changed(
        model, fluxes_a, fluxes_b,
        cutoff_flux=inputs["cutoff_flux"],
        cutoff_diff=inputs["cutoff_diff"],
        cutoff_change=inputs["cutoff_change"],
        metabolite_list=inputs["metabolite_list"],
    )

    changed = sorted(
        (
            {
                "reaction": c.reaction,
                "name": c.name,
                "flux": c.flux,
                "reference_flux": c.reference_flux,
                "difference": c.difference,
            }
            for c in result.changed
        ),
        key=lambda row: row["reaction"],
    )

    return {
        "filtered": {
            "changed": changed,
            "missing_metabolites": sorted(result.missing_metabolites),
        }
    }
