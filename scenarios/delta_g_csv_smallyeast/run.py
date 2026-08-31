"""Python side of the deltaG CSV loader scenario.

load_delta_g_csv and loadDeltaGCSV agree on the ordinary case --- match by
id, leave anything the CSV doesn't mention untouched --- and, by their
current defaults, on yeast-GEM's own "no measurement" sentinel value too:
10000000.0 (load_delta_g_csv's own docstring names checkrxnDirection.m as
the reader that gates on this verbatim) is stored exactly as written by
both, rather than treated as absent. load_delta_g_csv still carries a
``missing_value`` opt-in for callers who want the old filtering behaviour;
loadDeltaGCSV has no such option at all (RAVEN#719 removed it outright).
Neither side filters unless explicitly asked to, so the two agree without
this scenario overriding either default.

Storage location differs too and is not itself the finding: RAVEN keeps
metDeltaG/rxnDeltaG as numeric array fields on the model struct;
raven_toolbox stores the same fact as a string on each entity's own
``.notes['deltaG']`` (cobra has no per-entity numeric side-table to put it
in). Both are read back and normalised to a float-or-absent pair for
comparison here, so that representational difference does not itself
register as one.
"""

import math

from raven_toolbox.annotation import load_delta_g_csv
from raven_toolbox.io import read_yaml_model


def run(ctx):
    inputs = ctx["inputs"]
    model = read_yaml_model(inputs["model"])

    load_delta_g_csv(model.metabolites, inputs["met_csv"])
    load_delta_g_csv(model.reactions, inputs["rxn_csv"])

    met_ids = [str(m) for m in inputs["met_ids"]]
    rxn_ids = [str(r) for r in inputs["rxn_ids"]]

    return {
        "metabolites": [_read(model.metabolites.get_by_id(mid)) for mid in met_ids],
        "reactions": [_read(model.reactions.get_by_id(rid)) for rid in rxn_ids],
    }


def _read(entity):
    raw = entity.notes.get("deltaG")
    value = float(raw) if raw is not None else math.nan
    return {"entity": entity.id, "value": value}
