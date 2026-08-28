"""Python side of the structural-manipulation chain.

Three checkpoints, each starting from a fresh read of the same model so that a
difference in one does not cascade into the next:

``irrev``
    ``convert_to_irreversible`` --- reversible reactions split into a forward
    and a ``_REV`` reaction.

``expand``
    ``expand_model`` --- reactions with isozymes replaced by one ``_EXP_N``
    reaction per DNF clause.

``sorted``
    ``sort_identifiers`` --- the same model with reactions, metabolites and
    genes in alphabetical order.

Shape rules, per docs/scenarios.md: sort everything, always emit every key,
lists of records rather than objects keyed by model identifiers. The one
deliberate exception is ``sorted``, where *model order is the result* and
sorting it here would make the checkpoint assert nothing.
"""

from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import (
    convert_to_irreversible,
    expand_model,
    gpr_to_dnf,
)
from raven_toolbox.utils import sort_identifiers


def run(ctx):
    path = ctx["inputs"]["model"]
    return {
        "irrev": _irrev_checkpoint(read_yaml_model(path)),
        "expand": _expand_checkpoint(read_yaml_model(path)),
        "sorted": _sorted_checkpoint(read_yaml_model(path)),
    }


def _irrev_checkpoint(model):
    added = convert_to_irreversible(model)
    return {
        "n_reactions": len(model.reactions),
        "n_reverse": len(added),
        "reverse_reactions": sorted(added),
        "reactions": _reaction_records(model),
        "gene_rules": _gene_rules(model),
        "stoichiometry": _stoichiometry(model),
    }


def _expand_checkpoint(model):
    added = expand_model(model)
    return {
        "n_reactions": len(model.reactions),
        "n_added": len(added),
        "added_reactions": sorted(added),
        "reactions": _reaction_records(model),
        "gene_rules": _gene_rules(model),
        "stoichiometry": _stoichiometry(model),
    }


def _sorted_checkpoint(model):
    sort_identifiers(model)
    # Model order, not sorted order --- see the module docstring. The lists
    # below are what sort_identifiers produced; re-sorting them would compare
    # this harness against itself.
    return {
        "reactions": [rxn.id for rxn in model.reactions],
        "metabolites": [met.id for met in model.metabolites],
        "genes": [gene.id for gene in model.genes],
        # Compartments are a plain dict on this side rather than an ordered
        # model field, so they are emitted in key order; RAVEN's sortIdentifiers
        # sorts model.comps, which comes to the same thing when it works.
        "compartments": sorted(model.compartments),
    }


def _reaction_records(model):
    return [
        {
            "id": rxn.id,
            "name": rxn.name,
            "lower_bound": float(rxn.lower_bound),
            "upper_bound": float(rxn.upper_bound),
            "objective_coefficient": float(rxn.objective_coefficient),
        }
        for rxn in sorted(model.reactions, key=lambda r: r.id)
    ]


def _gene_rules(model):
    """GPRs as sorted DNF clauses.

    Compared as gene *sets* rather than as rule strings: RAVEN runs
    standardizeGrRules at the end of expandModel, which brackets complexes,
    while the Python side joins the clause with " and ". That is formatting,
    not behaviour, and diffing the strings would report it every night.
    """
    rules = []
    for rxn in sorted(model.reactions, key=lambda r: r.id):
        clauses = [sorted(clause) for clause in gpr_to_dnf(rxn.gpr)]
        clauses.sort()
        rules.append({"reaction": rxn.id, "clauses": clauses})
    return rules


def _stoichiometry(model):
    entries = [
        {"reaction": rxn.id, "metabolite": met.id, "coefficient": float(coeff)}
        for rxn in model.reactions
        for met, coeff in rxn.metabolites.items()
    ]
    entries.sort(key=lambda e: (e["reaction"], e["metabolite"]))
    return entries
