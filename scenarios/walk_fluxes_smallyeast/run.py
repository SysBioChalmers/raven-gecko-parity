"""Python side of the walkFluxes/walk_fluxes navigation scenario."""
import pandas as pd

from raven_toolbox.analysis import FluxWalker
from raven_toolbox.io import read_yaml_model


def run(ctx):
    inputs = ctx["inputs"]
    model = read_yaml_model(inputs["model"])
    fluxes = pd.Series(inputs["fluxes"])

    walker = FluxWalker(
        model, fluxes, inputs["start_rxn"],
        cutoff=inputs["cutoff"], max_per_met=inputs["max_per_met"],
    )

    groups = [
        {
            "metabolite": g.metabolite,
            "name": g.name,
            "role": g.role,
            "magnitude": g.magnitude,
            "neighbors": [
                {
                    "number": n.number,
                    "reaction": n.reaction,
                    "flux": n.flux,
                    "role": n.role,
                    "name": n.name,
                }
                for n in g.neighbors
            ],
        }
        for g in walker.groups
    ]

    return {"atpx_neighbors": {"groups": groups, "neighbor_order": walker.neighbor_ids}}
