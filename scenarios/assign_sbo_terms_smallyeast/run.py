"""Python side of the SBO-term-assignment scenario.

add_sbo_terms's own transport detector is explicitly self-described as
"a cheap analogue" of RAVEN's getTransportRxns, not a faithful port ---
see scenario.yml for exactly how the two algorithms differ and why they
still agree on this fixture. biomass_rxn_name / ngam_rxn_name are
redirected to real smallYeast reaction names (their yeast-GEM-specific
defaults match nothing here) so those two override branches --- and
their priority over the single-reactant default --- are actually
exercised rather than silently skipped.
"""

from raven_toolbox.annotation import add_sbo_terms
from raven_toolbox.io import read_yaml_model


def run(ctx):
    inputs = ctx["inputs"]
    model = read_yaml_model(inputs["model"])

    add_sbo_terms(
        model,
        biomass_rxn_name=str(inputs["biomass_rxn_name"]),
        ngam_rxn_name=str(inputs["ngam_rxn_name"]),
    )

    metabolite_sbo = sorted(
        (met.id, met.annotation.get("sbo", "")) for met in model.metabolites
    )
    reaction_sbo = sorted(
        (rxn.id, rxn.annotation.get("sbo", "")) for rxn in model.reactions
    )

    return {
        "metabolite_sbo": [
            {"metabolite": mid, "sbo": sbo} for mid, sbo in metabolite_sbo
        ],
        "reaction_sbo": [
            {"reaction": rid, "sbo": sbo} for rid, sbo in reaction_sbo
        ],
    }
