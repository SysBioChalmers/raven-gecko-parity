"""Python side of the transport-reactions scenario.

``add_transport_reactions`` and RAVEN's ``addTransport`` take the same three
positional arguments (source compartment, target compartment(s), metabolite
names) and the same ``onlyToExisting`` / ``only_to_existing`` default.

New reactions are derived by difference from the model before and after
rather than from the return value, matching the convention used everywhere
else in this suite: RAVEN returns only the updated model plus the new ids,
where this side returns reaction objects, so the difference is the one
quantity both can state.

Reaction ids are deliberately not compared --- see scenario.yml.
"""

from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import add_transport_reactions


def run(ctx):
    inputs = ctx["inputs"]
    return {
        "reversible": _checkpoint(inputs, reversible=True),
        "irreversible": _checkpoint(inputs, reversible=False),
    }


def _checkpoint(inputs, *, reversible):
    model = read_yaml_model(inputs["model"])
    before_rxns = {rxn.id for rxn in model.reactions}
    before_mets = {met.id for met in model.metabolites}

    added = add_transport_reactions(
        model,
        str(inputs["from_compartment"]),
        [str(inputs["to_compartment"])],
        [str(name) for name in inputs["metabolite_names"]],
        reversible=reversible,
        only_to_existing=True,
    )

    after_mets = {met.id for met in model.metabolites}

    return {
        "n_reactions_before": len(before_rxns),
        "n_reactions_after": len(model.reactions),
        "n_added": len(added),
        "n_metabolites_before": len(before_mets),
        "n_metabolites_after": len(after_mets),
        # By name, not by the reaction id neither side derives from anything
        # about the transport itself.
        "transports": sorted(
            (
                {
                    "name": str(rxn.name or ""),
                    "lower_bound": float(rxn.lower_bound),
                    "upper_bound": float(rxn.upper_bound),
                    "from_species": _species(rxn, str(inputs["from_compartment"])),
                    "to_species": _species(rxn, str(inputs["to_compartment"])),
                }
                for rxn in added
            ),
            key=lambda t: t["name"],
        ),
    }


def _species(rxn, compartment):
    """The (name, coefficient) of the one metabolite this transport has in
    *compartment* --- a transport reaction has exactly one on each side."""
    for met, coeff in rxn.metabolites.items():
        if met.compartment == compartment:
            return {"name": str(met.name or ""), "coefficient": float(coeff)}
    raise AssertionError(f"{rxn.id} has no metabolite in compartment {compartment!r}")
