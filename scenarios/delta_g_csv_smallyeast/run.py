"""Python side of the deltaG CSV loader scenario.

load_delta_g_csv and deltaGCSV('load', ...) agree on the ordinary case ---
match by id, leave anything the CSV doesn't mention untouched --- but not
on what a "no value" sentinel means. yeast-GEM's own side-car CSVs use
10000000.0 to mean "no measurement" (load_delta_g_csv's own docstring
names checkrxnDirection.m as the reader that gates on this verbatim); RAVEN's
deltaGCSV has no concept of this sentinel at all and stores it as a literal
number like any other. load_delta_g_csv treats it as missing and leaves the
entity unstamped instead.

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
