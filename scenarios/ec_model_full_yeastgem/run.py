"""Python side of the genome-scale ecModel pipeline scenario (Tier 4).

Runs the full non-DLKcat pipeline --- make_ec_model, fill_eccodes_from_gem,
fuzzy_kcat_matching, apply_kcat_list, apply_kcat_constraints, set_prot_pool_size --- on
GECKO's own yeast-GEM tutorial model. See scenario.yml for why DLKcat is out of scope,
why eccodes and the BRENDA files each need a small amount of scenario-side data
preparation before the pipeline can run at all, and the one confirmed divergence
(EC-code validation strictness) this scenario asserts.
"""

import csv
import importlib.util
import sys
import tempfile
from pathlib import Path

import cobra
import numpy as np
import yaml

from geckopy import (
    ModelAdapter,
    apply_kcat_constraints,
    apply_kcat_list,
    fill_eccodes_from_gem,
    fuzzy_kcat_matching,
    load_brenda_data,
    load_conventional_gem,
    load_phyl_dist,
    make_ec_model,
    set_prot_pool_size,
)


def _adapter(inputs: dict) -> ModelAdapter:
    """geckopy's yeast-GEM adapter, repointed at the GECKO copy of the fixture.

    Same reasoning as every ecTestGEM-scale scenario in this pair: the parameters are
    geckopy's own (model_adapter.toml), the data files become the ones MATLAB reads.
    """
    adapter = ModelAdapter.from_folder(inputs["adapter_python"])
    fixture = Path(inputs["fixture_dir"])
    adapter.params.path = fixture
    adapter.params.conv_gem = fixture / "models" / "yeast-GEM.yml"
    # examples/yeast-GEM/model_adapter.toml carries f=0.4461, a different value than
    # YeastGEMAdapter.m's own f=0.5 -- not a bug on either side (each is presumably a
    # deliberately calibrated value for that project), but setProtPoolSize's bound is
    # directly proportional to f, so leaving them different would show up as a
    # pool_ub mismatch that has nothing to do with either implementation's own
    # behaviour. Matched here so this scenario compares the pipeline, not the config.
    adapter.params.f = 0.5
    return adapter


def _patch_eccodes_from_yaml(conv: cobra.Model, yaml_path: Path) -> None:
    """Recover yeast-GEM.yml's own `eccodes` reaction field.

    cobra.io.load_yaml_model (what load_conventional_gem calls for a .yml file) does
    not populate reaction.annotation['ec-code'] from it --- confirmed by direct
    execution, not assumed. A second, plain YAML parse (PyYAML's built-in `!!omap`
    handling) recovers the (reaction id -> `;`-joined EC list) mapping directly, and
    writes it into the annotation key fill_eccodes_from_gem actually reads. This
    restores parity input; it is not a workaround for anything being compared.
    """
    with open(yaml_path, encoding="utf-8") as f:
        raw = dict(yaml.safe_load(f))
    eccodes_by_id: dict[str, str] = {}
    for row in raw["reactions"]:
        row = dict(row)
        ec = row.get("eccodes")
        if ec:
            eccodes_by_id[row["id"]] = ";".join(ec) if isinstance(ec, list) else str(ec)
    for rxn in conv.reactions:
        if rxn.id in eccodes_by_id:
            rxn.annotation["ec-code"] = eccodes_by_id[rxn.id]


def _strip_ec(ec: str) -> str:
    return ec[2:] if ec.startswith("EC") else ec


def _strip_organism(org: str) -> str:
    return org.split("//", 1)[0]


def _convert_brenda(src_dir: Path, dst_dir: Path) -> None:
    """GECKO's max_KCAT.txt/max_MW.txt/max_SA.txt -> geckopy's kcat.tsv/mw.tsv/sa.tsv.

    Same (EC, substrate, organism, value) triples, EC prefix and organism taxonomy
    suffix stripped, `kcat_median` set equal to `kcat_max` and `n=1` throughout ---
    GECKO's own files carry only one, already-maximal value per triple, so there is no
    underlying distribution to derive a true median from. See
    docs/brenda-reconciliation.md for the mapping, confirmed at ecTestGEM scale; this
    just applies it at genome scale.
    """

    def convert_wide(src_name: str, dst_name: str) -> None:
        with open(src_dir / src_name, encoding="utf-8") as f_in, \
             open(dst_dir / dst_name, "w", encoding="utf-8", newline="") as f_out:
            w = csv.writer(f_out, delimiter="\t", lineterminator="\n")
            w.writerow(["ec_code", "substrate", "organism", "kcat_max", "kcat_median", "n", "references"])
            for line in f_in:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 5:
                    continue
                ec, substrate, organism, value, refs = parts[:5]
                w.writerow([_strip_ec(ec), substrate, _strip_organism(organism), value, value, "1", refs])

    def convert_mw(src_name: str, dst_name: str) -> None:
        with open(src_dir / src_name, encoding="utf-8") as f_in, \
             open(dst_dir / dst_name, "w", encoding="utf-8", newline="") as f_out:
            w = csv.writer(f_out, delimiter="\t", lineterminator="\n")
            w.writerow(["ec_code", "substrate", "organism", "mw", "n", "references"])
            for line in f_in:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 5:
                    continue
                ec, substrate, organism, value, refs = parts[:5]
                w.writerow([_strip_ec(ec), substrate, _strip_organism(organism), value, "1", refs])

    convert_wide("max_KCAT.txt", "kcat.tsv")
    convert_mw("max_MW.txt", "mw.tsv")
    convert_wide("max_SA.txt", "sa.tsv")


def _source_token(source: str) -> str:
    """The base provenance token, stripping geckopy's bracketed wildcard/origin detail.

    Same helper as kcat_chain_ectestgem's own run.py: 'brenda (wc=0, origin=1)' ->
    'brenda'. Documented MATLAB-COMPAT choice (select_kcat_value.py), not a divergence
    this scenario asserts, so the checkpoint compares on the token both sides agree on.
    """
    return source.split(" (", 1)[0].lower()


def run(ctx):
    inputs = ctx["inputs"]
    cobra.Configuration().solver = str(inputs["python_solver"])

    adapter = _adapter(inputs)
    conv = load_conventional_gem(adapter)
    conv_counts = {
        "reactions": len(conv.reactions),
        "metabolites": len(conv.metabolites),
        "genes": len(conv.genes),
    }

    _patch_eccodes_from_yaml(conv, adapter.params.conv_gem)

    model = make_ec_model(conv, adapter, gecko_light=False)
    model.solver = str(inputs["python_solver"])
    model.adapter = adapter
    fill_eccodes_from_gem(model)

    ec_counts = {
        "ec_rxns": len(model.ec.rxns),
        "enzymes": len(model.ec.enzymes),
        "genes": len(model.ec.genes),
        "eccodes_populated": sum(1 for e in model.ec.eccodes if e),
    }

    with tempfile.TemporaryDirectory() as tmp:
        brenda_dir = Path(tmp)
        _convert_brenda(Path(inputs["databases_dir"]), brenda_dir)
        brenda = load_brenda_data(brenda_dir)

    phyl_dist = load_phyl_dist(Path(inputs["adapter_matlab"]).parent / "PhylDist.mat")
    fuzzy_df = fuzzy_kcat_matching(model, brenda, phyl_dist)
    apply_kcat_list(model, fuzzy_df, criteria="max")
    apply_kcat_constraints(model)
    set_prot_pool_size(model)

    kcats = sorted(
        (
            {
                "reaction": str(r),
                "kcat": float(model.ec.kcat[i]),
                "source": _source_token(str(model.ec.source[i])) if model.ec.source[i] else "",
            }
            for i, r in enumerate(model.ec.rxns)
        ),
        key=lambda row: row["reaction"],
    )

    pool_rxn = model.reactions.get_by_id("prot_pool_exchange")

    return {
        "expansion": {
            "conv_counts": conv_counts,
            "ec_counts": ec_counts,
            "ec_rxns": sorted(str(r) for r in model.ec.rxns),
            "enzymes": sorted(str(e) for e in model.ec.enzymes),
        },
        "kcats": {
            "pool_ub": float(pool_rxn.upper_bound),
            "nonzero_count": int(np.sum(model.ec.kcat > 0)),
            "rows": kcats,
        },
    }
