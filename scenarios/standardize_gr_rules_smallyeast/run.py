"""Python side of the non-DNF GPR detection scenario.

find_non_dnf_grrules is the lint-only half of standardizeGrRules: cobra
auto-normalises a GPR's brackets and operator case at assignment time, so
there is nothing on the Python side that corresponds to
standardizeGrRules' string-rewriting output (grRules, rxnGeneMat) --- only
to indexes2check, the reactions findPotentialErrors (called internally by
standardizeGrRules) flags as non-DNF. Both use the same underlying
"is this GPR an OR of AND-complexes" check already cross-validated by
gpr_dnf_rules; this scenario exercises the wrapper on a real model instead
of synthetic strings.

smallYeast's own GPRs are all single genes or plain ORs --- none are
non-DNF --- so HXK's rule is deliberately rewritten to one that is,
using change_gene_reaction_rules (already cross-validated by
change_gene_rules_smallyeast), to give the detector something to find.
"""

from raven_toolbox.io import read_yaml_model
from raven_toolbox.manipulation import change_gene_reaction_rules
from raven_toolbox.utils import find_non_dnf_grrules


def run(ctx):
    inputs = ctx["inputs"]
    model = read_yaml_model(inputs["model"])

    rewritten = inputs["non_dnf_rule"]
    change_gene_reaction_rules(
        model, {str(rewritten["reaction"]): str(rewritten["grRule"])}, replace=True
    )

    issues = find_non_dnf_grrules(model)

    return {
        "flagged_reactions": sorted(issue.reaction_id for issue in issues),
    }
