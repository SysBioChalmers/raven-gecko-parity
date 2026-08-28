"""Python side of the model-diffing scenario.

``diff_models`` returns ``DiffReport(equal, differences)`` --- a boolean and a
list of human-readable strings, formatted however this implementation likes.
The strings themselves are not compared: RAVEN's diffModels phrases the same
facts differently (a different sprintf template, a different float format),
and comparing text would fail on formatting rather than on substance. What is
compared is the *count* --- both sides push exactly one line per difference
found, so a fixture engineered to contain exactly N differences gives both
implementations the same number to agree on, which is only possible if they
found the same things.

Model B is model A with one edit per checked category, built from functions
this suite has already cross-validated (add_reactions_from_equations /
change_reaction_equations / change_gene_reaction_rules) plus plain field
assignment for what none of those touch. reactions_only_in_a/b and
genes_only_in_a/b are derived directly from the two models rather than from
either function's own output --- diffModels exposes these as first-class
fields where DiffReport does not, so this is context about the fixture, not a
claim about the function's return shape. See scenario.yml.
"""

from raven_toolbox.comparison import diff_models
from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import (
    add_reactions_from_equations,
    change_gene_reaction_rules,
    change_reaction_equations,
)


def run(ctx):
    inputs = ctx["inputs"]

    a = read_yaml_model(inputs["model"])
    a.reactions.get_by_id(str(inputs["eccode"]["reaction"])).annotation["ec-code"] = str(
        inputs["eccode"]["a"]
    )
    b = _modified(inputs)
    report = diff_models(a, b)

    a_rxns, b_rxns = {r.id for r in a.reactions}, {r.id for r in b.reactions}
    a_genes, b_genes = {g.id for g in a.genes}, {g.id for g in b.genes}

    # Two independent, otherwise-untouched reads of the same file: a cheap
    # determinism check that the reader and the diff function together
    # introduce no artefact of their own. Deliberately not the annotated `a`
    # above, which would show the ec-code edit as a spurious difference.
    self_report = diff_models(read_yaml_model(inputs["model"]), read_yaml_model(inputs["model"]))

    return {
        "modified": {
            "equal": bool(report.equal),
            "n_differences": len(report.differences),
            "reactions_only_in_a": sorted(a_rxns - b_rxns),
            "reactions_only_in_b": sorted(b_rxns - a_rxns),
            "genes_only_in_a": sorted(a_genes - b_genes),
            "genes_only_in_b": sorted(b_genes - a_genes),
        },
        "self": {
            "equal": bool(self_report.equal),
            "n_differences": len(self_report.differences),
        },
    }


def _modified(inputs):
    model = read_yaml_model(inputs["model"])

    model.remove_reactions([str(inputs["removed_reaction"])], remove_orphans=False)

    added = inputs["added_reaction"]
    add_reactions_from_equations(
        model,
        [{"id": str(added["id"]), "equation": str(added["equation"]), "name": str(added["name"])}],
        mets_by="id", allow_new_mets=False, allow_new_genes=False,
    )

    stoich = inputs["stoichiometry"]
    change_reaction_equations(
        model, {str(stoich["reaction"]): str(stoich["equation"])}, mets_by="id", allow_new_mets=False
    )

    bounds = inputs["bounds"]
    model.reactions.get_by_id(str(bounds["reaction"])).upper_bound = float(bounds["upper_bound"])

    objective = inputs["objective"]
    model.reactions.get_by_id(str(objective["reaction"])).objective_coefficient = float(
        objective["coefficient"]
    )

    changed = inputs["gpr_changed"]
    change_gene_reaction_rules(model, {str(changed["reaction"]): str(changed["grRule"])}, replace=True)

    reordered = inputs["gpr_reordered"]
    change_gene_reaction_rules(model, {str(reordered["reaction"]): str(reordered["grRule"])}, replace=True)

    eccode = inputs["eccode"]
    model.reactions.get_by_id(str(eccode["reaction"])).annotation["ec-code"] = str(eccode["b"])

    formula = inputs["metabolite_formula"]
    model.metabolites.get_by_id(str(formula["metabolite"])).formula = str(formula["b"])

    charge = inputs["metabolite_charge"]
    model.metabolites.get_by_id(str(charge["metabolite"])).charge = float(charge["b"])

    return model
