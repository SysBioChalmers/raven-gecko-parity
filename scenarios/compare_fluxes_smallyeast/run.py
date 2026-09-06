"""Python side of the compareFluxes/compare_fluxes scenario."""
import pandas as pd

from raven_toolbox.analysis import compare_fluxes
from raven_toolbox.io import read_yaml_model


def _dense(model, sparse_inputs):
    fluxes = pd.Series(0.0, index=[r.id for r in model.reactions])
    fluxes.update(pd.Series(sparse_inputs, dtype=float))
    return fluxes


def _checkpoint(result):
    return {
        # In the order compare_fluxes produced them: the descending sort by
        # abs_delta is part of what this scenario checks.
        "changed": [
            {
                "reaction": row.reaction,
                "flux1": float(row.flux1),
                "flux2": float(row.flux2),
                "abs_delta": float(row.abs_delta),
                "rel_change": float(row.rel_change),
                "type": row.type,
            }
            for row in result.changed.itertuples(index=False)
        ],
        # Model order on both sides, so no ordering claim -- sorted before
        # comparing. n_considered is a raven-toolbox addition compareFluxes has
        # no counterpart for, so it is not compared.
        "turned_on": sorted(result.turned_on),
        "turned_off": sorted(result.turned_off),
        "flipped": sorted(result.flipped),
    }


def run(ctx):
    inputs = ctx["inputs"]
    model = read_yaml_model(inputs["model"])

    fluxes_1 = _dense(model, inputs["fluxes_1"])
    fluxes_2 = _dense(model, inputs["fluxes_2"])
    cutoff = inputs["cutoff"]

    unfiltered = compare_fluxes(model, fluxes_1, fluxes_2, cutoff=cutoff)
    filtered = compare_fluxes(
        model, fluxes_1, fluxes_2, cutoff=cutoff,
        metabolite_list=inputs["metabolite_list"],
    )

    return {
        "unfiltered": _checkpoint(unfiltered),
        "filtered": _checkpoint(filtered),
    }
