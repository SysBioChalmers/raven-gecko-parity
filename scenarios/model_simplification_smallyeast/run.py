"""Python side of the model-simplification scenario.

``simplify_model`` is the single entry point mirroring RAVEN's ``simplifyModel``
boolean-flag interface, and it is what is called here rather than the per-mode
functions it delegates to --- the flags are part of what is being compared.

It works in place and reports nothing, where RAVEN returns the deleted
reactions and metabolites. Both sides therefore take the difference between the
model before and after, which is symmetric and still catches a mode that
removed the wrong thing.
"""

from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import simplify_model


def run(ctx):
    inputs = ctx["inputs"]
    path = inputs["model"]
    cascade_removed = [str(rxn) for rxn in inputs["cascade_removed_reactions"]]

    zero_interval = read_yaml_model(path)
    dead_end = read_yaml_model(path)
    dead_end_alone = read_yaml_model(path)

    cascade = read_yaml_model(path)
    cascade.remove_reactions(cascade_removed)

    return {
        "zero_interval": _checkpoint(zero_interval, delete_zero_interval=True),
        "composed": _checkpoint(
            dead_end, delete_zero_interval=True, delete_dead_end=True
        ),
        "composed_cascade": _checkpoint(
            cascade, delete_zero_interval=True, delete_dead_end=True
        ),
        "dead_end_alone": _checkpoint(dead_end_alone, delete_dead_end=True),
    }


def _checkpoint(model, **modes):
    before_rxns = {rxn.id for rxn in model.reactions}
    before_mets = {met.id for met in model.metabolites}

    simplify_model(model, **modes)

    after_rxns = {rxn.id for rxn in model.reactions}
    after_mets = {met.id for met in model.metabolites}

    return {
        "n_reactions_before": len(before_rxns),
        "n_reactions_after": len(after_rxns),
        "n_metabolites_before": len(before_mets),
        "n_metabolites_after": len(after_mets),
        "removed_reactions": sorted(before_rxns - after_rxns),
        "removed_metabolites": sorted(before_mets - after_mets),
        "reactions": sorted(after_rxns),
        "metabolites": sorted(after_mets),
        # Keeping the chemistry under test as well as the census: a pass that
        # removed the right reactions but disturbed the ones it kept would
        # agree on every count above.
        "bounds": [
            {
                "reaction": rxn.id,
                "lower_bound": float(rxn.lower_bound),
                "upper_bound": float(rxn.upper_bound),
            }
            for rxn in sorted(model.reactions, key=lambda r: r.id)
        ],
        "stoichiometry": _stoichiometry(model),
    }


def _stoichiometry(model):
    entries = [
        {"reaction": rxn.id, "metabolite": met.id, "coefficient": float(coeff)}
        for rxn in model.reactions
        for met, coeff in rxn.metabolites.items()
    ]
    entries.sort(key=lambda e: (e["reaction"], e["metabolite"]))
    return entries
