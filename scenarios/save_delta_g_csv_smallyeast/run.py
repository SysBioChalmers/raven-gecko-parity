"""Python side of the deltaG CSV writer scenario.

save_delta_g_csv and saveDeltaGCSV both write one row per entity, in model
order, verbatim from whatever the model already holds --- neither
interprets or filters a value on the way out. This scenario stamps three
metabolites and three reactions (an ordinary value, yeast-GEM's own
10000000.0 "no measurement" sentinel, and one left unstamped), writes them
out, and reads the CSV back with pandas purely as test scaffolding, the
same way the MATLAB side reads it back with readtable --- nothing under
test here is either side's own reader.
"""

import math
import tempfile
from pathlib import Path

import pandas as pd

from raven_toolbox.annotation import save_delta_g_csv
from raven_toolbox.io import read_yaml_model


def run(ctx):
    inputs = ctx["inputs"]
    model = read_yaml_model(inputs["model"])

    _stamp(model.metabolites, inputs["met_values"])
    _stamp(model.reactions, inputs["rxn_values"])

    met_csv = Path(tempfile.mktemp(suffix=".csv"))
    rxn_csv = Path(tempfile.mktemp(suffix=".csv"))
    try:
        save_delta_g_csv(model.metabolites, met_csv)
        save_delta_g_csv(model.reactions, rxn_csv)

        met_df = pd.read_csv(met_csv)
        rxn_df = pd.read_csv(rxn_csv)
    finally:
        met_csv.unlink(missing_ok=True)
        rxn_csv.unlink(missing_ok=True)

    return {
        "met_row_count": len(met_df),
        "rxn_row_count": len(rxn_df),
        "metabolites": [_read_row(met_df, mid) for mid in inputs["met_ids"]],
        "reactions": [_read_row(rxn_df, rid) for rid in inputs["rxn_ids"]],
    }


def _stamp(entities, values):
    for entity in entities:
        if entity.id in values:
            entity.notes["deltaG"] = str(values[entity.id])


def _read_row(df, entity_id):
    matches = df.loc[df["Var1"] == entity_id, "Var2"]
    if matches.empty:
        raise AssertionError(f"{entity_id} missing from the written CSV")
    value = float(matches.iloc[0])
    return {"entity": entity_id, "value": "NaN" if math.isnan(value) else value}
