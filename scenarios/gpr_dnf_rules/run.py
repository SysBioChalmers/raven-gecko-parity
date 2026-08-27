"""Python side of the GPR normalisation scenario.

``grRuleToDNF`` takes a rule string and parses it itself; ``gpr_to_dnf`` takes an
already-parsed :class:`~cobra.core.gene.GPR`. Parsing here with
``GPR.from_string`` is not a shortcut around that difference --- it is what the
ledger says the Python side does: ``parseGrRule`` is a ``via-dependency`` row,
because cobra owns the parser on this side. So the two chains compared are

    parseGrRule -> grRuleToDNF        (MATLAB)
    GPR.from_string -> gpr_to_dnf     (Python)

which is the whole path a caller actually travels.
"""

from cobra.core.gene import GPR

from raven_toolbox.manipulation import gpr_to_dnf
from raven_toolbox.utils import is_dnf


def run(ctx):
    rules = list(ctx["inputs"]["rules"])

    # Input order, not sorted: the rules are a fixture whose order is part of
    # the declaration, and keeping it makes a difference easy to locate in
    # scenario.yml.
    analysed = [_analyse(str(rule)) for rule in rules]

    return {
        "n_rules": len(analysed),
        # A rule that fails to parse is the interesting case, so count it
        # rather than leaving it to be spotted in the per-rule list.
        "n_unparsable": sum(1 for row in analysed if not row["parsed"]),
        "n_dnf": sum(1 for row in analysed if row["is_dnf"]),
        "rules": analysed,
    }


def _analyse(rule):
    try:
        gpr = GPR.from_string(rule)
        parsed = True
    except Exception:  # noqa: BLE001 --- any parse failure is the same finding
        gpr, parsed = None, False

    if not parsed:
        # Every key always present: an unparsable rule on one side only must
        # read as a value difference, not as a structural one.
        return {"rule": rule, "parsed": False, "is_dnf": False, "n_clauses": 0, "clauses": []}

    clauses = [[str(gene) for gene in clause] for clause in gpr_to_dnf(gpr)]
    return {
        "rule": rule,
        "parsed": True,
        "is_dnf": bool(is_dnf(gpr)),
        "n_clauses": len(clauses),
        "clauses": clauses,
    }
