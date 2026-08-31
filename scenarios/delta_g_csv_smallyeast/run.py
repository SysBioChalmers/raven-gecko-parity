"""Python side of the deltaG CSV load/save scenario.

load_delta_g_csv/save_delta_g_csv and their MATLAB counterparts
loadDeltaGCSV/saveDeltaGCSV agree on the ordinary case --- match by id,
leave anything the CSV doesn't mention untouched --- and, since
raven-gecko-parity#67/#16, on yeast-GEM's own "no measurement" placeholder
value too: neither side interprets a CSV value at all any more, so the
placeholder (10000000.0) is recorded exactly like any other value.

Storage location differs and is not itself the finding: RAVEN keeps
metDeltaG/rxnDeltaG as numeric array fields on the model struct;
raven_toolbox stores the same fact as a string on each entity's own
``.notes['deltaG']`` (cobra has no per-entity numeric side-table to put it
in). Both are read back and normalised to a float-or-absent pair for
comparison here.
"""

import math
import tempfile
from pathlib import Path

import pandas as pd

from raven_toolbox.annotation import load_delta_g_csv, save_delta_g_csv
from raven_toolbox.io import read_yaml_model


def run(ctx):
    inputs = ctx["inputs"]
    model = read_yaml_model(inputs["model"])

    load_delta_g_csv(model.metabolites, inputs["met_csv"])
    load_delta_g_csv(model.reactions, inputs["rxn_csv"])

    met_ids = [str(m) for m in inputs["met_ids"]]
    rxn_ids = [str(r) for r in inputs["rxn_ids"]]

    with tempfile.TemporaryDirectory(prefix="parity_delta_g_") as workdir:
        out_met_csv = Path(workdir) / "met_out.csv"
        out_rxn_csv = Path(workdir) / "rxn_out.csv"
        save_delta_g_csv(model.metabolites, out_met_csv)
        save_delta_g_csv(model.reactions, out_rxn_csv)
        saved_metabolites = _read_csv_rows(out_met_csv)
        saved_reactions = _read_csv_rows(out_rxn_csv)

    return {
        "metabolites": [_read(model.metabolites.get_by_id(mid)) for mid in met_ids],
        "reactions": [_read(model.reactions.get_by_id(rid)) for rid in rxn_ids],
        "saved_metabolites": saved_metabolites,
        "saved_reactions": saved_reactions,
    }


def _read(entity):
    raw = entity.notes.get("deltaG")
    value = float(raw) if raw is not None else math.nan
    return {"entity": entity.id, "value": value}


def _read_csv_rows(path):
    """The full contents of a saved CSV, sorted by id --- what was actually
    written, not what a later load of it would read back."""
    df = pd.read_csv(path)
    id_col, value_col = df.columns[0], df.columns[1]
    records = [
        {"entity": str(row[id_col]), "value": float(row[value_col])}
        for _, row in df.iterrows()
    ]
    records.sort(key=lambda r: r["entity"])
    return records
