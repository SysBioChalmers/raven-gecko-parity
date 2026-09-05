"""Python side of the processProteinFastaFile/process_protein_fasta_file scenario."""
import tempfile
from pathlib import Path

import pandas as pd

from raven_toolbox.curation import process_protein_fasta_file


def run(ctx):
    inputs = ctx["inputs"]
    gene_table = pd.DataFrame({
        "GenBank_protein": inputs["protein_ids"],
        inputs["header_col"]: inputs["header_values"],
    })

    with tempfile.TemporaryDirectory() as out_dir:
        out_path = process_protein_fasta_file(
            inputs["faa"], gene_table, inputs["header_col"], output_dir=out_dir,
        )
        records = _read_fasta(Path(out_path))

    return {"processed": records}


def _read_fasta(path):
    records = []
    header = None
    seq = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if header is not None:
                records.append({"header": header, "sequence": "".join(seq)})
            header = line[1:]
            seq = []
        else:
            seq.append(line)
    if header is not None:
        records.append({"header": header, "sequence": "".join(seq)})
    return records
