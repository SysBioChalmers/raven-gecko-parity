"""Python side of the reaction-rewriting scenario.

``change_reaction_equations`` takes a mapping of reaction id to equation
string; RAVEN's ``changeRxns`` takes parallel arrays of the same. Both mutate
the named reactions in place and touch nothing else about them, which is most
of what this scenario checks.

The whole model is inspected, not just the two changed reactions: the claim
is that *everything else* is untouched, and that is only evidence if the rest
of the model is looked at too.
"""

from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import gpr_to_dnf
from raven_toolbox.manipulation.change import change_reaction_equations


def run(ctx):
    inputs = ctx["inputs"]
    model = read_yaml_model(inputs["model"])

    before_mets = {met.id for met in model.metabolites}
    before_other = {
        rxn.id: _fingerprint(rxn)
        for rxn in model.reactions
        if rxn.id not in inputs["equations"]
    }

    equations = {str(k): str(v) for k, v in dict(inputs["equations"]).items()}
    change_reaction_equations(
        model,
        equations,
        mets_by="id",
        compartment=str(inputs["compartment"]),
        allow_new_mets=bool(inputs["allow_new_mets"]),
    )

    after_mets = {met.id for met in model.metabolites}
    after_other = {rxn.id: _fingerprint(rxn) for rxn in model.reactions if rxn.id in before_other}

    return {
        "n_reactions": len(model.reactions),
        "n_metabolites_before": len(before_mets),
        "n_metabolites_after": len(after_mets),
        "created_metabolites": sorted(after_mets - before_mets),
        "changed_reactions": [
            _fingerprint(model.reactions.get_by_id(rxn_id))
            for rxn_id in sorted(equations)
        ],
        "n_untouched_reactions_checked": len(before_other),
        # The point of the scenario: this should be empty on both sides. A
        # reaction id here rather than a bare pass/fail flag says which
        # reaction moved when the docstrings promised none would.
        "unexpectedly_changed_reactions": sorted(
            rid for rid in before_other if before_other[rid] != after_other[rid]
        ),
    }


def _fingerprint(rxn):
    clauses = [sorted(clause) for clause in gpr_to_dnf(rxn.gpr)]
    clauses.sort()
    stoich = sorted(
        (met.id, float(coeff)) for met, coeff in rxn.metabolites.items()
    )
    return {
        "reaction": rxn.id,
        "name": str(rxn.name or ""),
        "lower_bound": float(rxn.lower_bound),
        "upper_bound": float(rxn.upper_bound),
        "objective_coefficient": float(rxn.objective_coefficient),
        "subsystem": _subsystem(rxn),
        "clauses": clauses,
        "stoichiometry": stoich,
    }


def _subsystem(rxn):
    """cobra's own type hint promises a str, but its YAML round trip can
    leave a reaction with no subsystem holding the raw list ``[None]``
    instead: smallYeast.yml writes an absent subsystem as ``subsystem:
    [null]``, and cobra.io.dict assigns whatever the YAML parsed straight
    onto the attribute with no normalisation. Neither changeRxns nor
    change_reaction_equations touches subsystem, so this is purely how the
    fixture stores "no subsystem" -- reduced here to the empty string, the
    same value the MATLAB side reads off an empty subSystems cell."""
    value = rxn.subsystem
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "")
