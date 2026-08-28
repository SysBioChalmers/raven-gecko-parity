"""Python side of the Excel export scenario.

export_to_excel is a faithful, deliberate port --- same sheets, same
headers, same column order, even the same "RXNS' ID column is the real
id but METS' ID column is name[comp], with the real id moved to
REPLACEMENT ID" convention RAVEN itself uses. Where the two diverge is
LOWER BOUND / UPPER BOUND: exportToExcelFormat hides a bound that equals
the model's own declared default (model.annotation.defaultLB/defaultUB,
smallYeast declares -1000/1000) --- an irreversible reaction's lower bound
is hidden separately, only when it is exactly 0 --- leaving the cell
blank rather than printing a redundant value; export_to_excel has no such
logic and always writes the literal bound. On smallYeast, whose bounds
are drawn entirely from {-1000, 0, 1000}, this is not a corner case: it
is the fate of nearly every reaction's bound cells.

Neither side provides a reader for its own export ("Excel import is
intentionally excluded", by both docstrings), so this reads the freshly
written file back with openpyxl purely as test scaffolding, the same way
the MATLAB side reads it back with readcell --- nothing under test here
comes from either side's own reader.
"""

import tempfile
from pathlib import Path

import openpyxl

from raven_toolbox.io import export_to_excel, read_yaml_model


def run(ctx):
    inputs = ctx["inputs"]
    model = read_yaml_model(inputs["model"])

    out_path = Path(tempfile.mktemp(suffix=".xlsx"))
    try:
        export_to_excel(model, out_path)
        wb = openpyxl.load_workbook(out_path)
        ws = wb["RXNS"]
        rows = list(ws.iter_rows(values_only=True))
    finally:
        out_path.unlink(missing_ok=True)

    headers = rows[0]
    id_col = headers.index("ID")
    lb_col = headers.index("LOWER BOUND")
    ub_col = headers.index("UPPER BOUND")

    by_id = {row[id_col]: row for row in rows[1:]}

    records = []
    for rxn_id in inputs["reaction_ids"]:
        row = by_id[str(rxn_id)]
        records.append(
            {
                "reaction": str(rxn_id),
                "lower_bound": row[lb_col],
                "upper_bound": row[ub_col],
            }
        )

    return {"rxns_bounds": records}
