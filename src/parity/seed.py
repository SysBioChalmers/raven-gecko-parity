"""Bootstrapping and topping up a ledger from a scan of both repos.

Nobody is going to hand-write 600 rows. This proposes them: an exact normalised name match
(``predictLocalization`` <-> ``predict_localization``) settles the easy majority, an
abbreviation-aware pass catches MATLAB's ``Rxns``/``Mets`` against Python's spelled-out
``reactions``/``metabolites``, and whatever is left is emitted as ``unreviewed`` with the
nearest candidates named in its ``notes`` so triage is a yes/no rather than a search.

Everything it proposes is ``unreviewed``: the tool pairs names, a human confirms behaviour.
Existing rows are never overwritten.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from parity.config import Pair
from parity.inventory import Inventory, PythonExport, build_inventory
from parity.ledger import Entry, Ledger, load_ledger, merge_entries

#: MATLAB's house abbreviations against the words the Python ports spell out.
ABBREVIATIONS: dict[str, str] = {
    "rxns": "reactions",
    "rxn": "reaction",
    "mets": "metabolites",
    "met": "metabolite",
    "comps": "compartments",
    "comp": "compartment",
    "prots": "proteins",
    "prot": "protein",
    "params": "parameters",
    "param": "parameter",
    "eqns": "equations",
    "eqn": "equation",
    "coeffs": "coefficients",
    "coeff": "coefficient",
}

#: How close a name has to be before it is worth suggesting during triage.
SUGGESTION_CUTOFF = 0.72
MAX_SUGGESTIONS = 3


def normalise(name: str) -> str:
    """Fold camelCase and snake_case onto a common key."""
    return name.replace("_", "").lower()


def _words(name: str) -> list[str]:
    """Split either naming convention into lowercase words."""
    if "_" in name:
        return [w for w in name.lower().split("_") if w]
    return [w.lower() for w in re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+", name) if w]


def expand(name: str) -> str:
    """Normalise, then spell out MATLAB's abbreviations."""
    return "".join(ABBREVIATIONS.get(word, word) for word in _words(name))


@dataclass
class SeedSummary:
    exact: int
    expanded: int
    matlab_unmatched: int
    python_unmatched: int

    @property
    def matched(self) -> int:
        return self.exact + self.expanded

    @property
    def total(self) -> int:
        return self.matched + self.matlab_unmatched + self.python_unmatched


def _index(exports: list[PythonExport], key) -> dict[str, list[PythonExport]]:
    out: dict[str, list[PythonExport]] = {}
    for export in exports:
        out.setdefault(key(export.name), []).append(export)
    return out


def discover(inventory: Inventory) -> tuple[list[Entry], SeedSummary]:
    """Propose ledger rows for everything in *inventory*."""
    python = list(inventory.python)
    exact_index = _index(python, normalise)
    expanded_index = _index(python, expand)
    python_names = [e.name for e in python]

    entries: list[Entry] = []
    used: set[str] = set()
    exact = expanded = 0

    for function in inventory.matlab:
        match, how = None, ""
        for index, key, label in (
            (exact_index, normalise, "exact name match"),
            (expanded_index, expand, "name match after expanding MATLAB abbreviations"),
        ):
            candidates = [c for c in index.get(key(function.name), []) if c.qualname not in used]
            if len(candidates) == 1:
                match, how = candidates[0], label
                break

        if match is not None:
            used.add(match.qualname)
            exact += how.startswith("exact")
            expanded += not how.startswith("exact")
            entries.append(
                Entry(
                    status="unreviewed",
                    matlab=function.name,
                    python=match.qualname,
                    notes=f"auto-paired ({how}); confirm the behaviour actually matches",
                )
            )
            continue

        entries.append(
            Entry(status="unreviewed", matlab=function.name, notes=_suggest(function.name, python_names, used, python))
        )

    matlab_unmatched = sum(1 for e in entries if e.python is None)

    leftover = [e for e in python if e.qualname not in used]
    for export in leftover:
        entries.append(
            Entry(
                status="unreviewed",
                python=export.qualname,
                notes=_suggest_matlab(export.name, [f.name for f in inventory.matlab]),
            )
        )

    return entries, SeedSummary(
        exact=exact,
        expanded=expanded,
        matlab_unmatched=matlab_unmatched,
        python_unmatched=len(leftover),
    )


def _suggest(matlab_name: str, python_names: list[str], used: set[str], python: list[PythonExport]) -> str:
    """Name the closest unclaimed Python exports, for a human to accept or reject."""
    available = {e.name: e for e in python if e.qualname not in used}
    close = difflib.get_close_matches(expand(matlab_name), [expand(n) for n in available], MAX_SUGGESTIONS, SUGGESTION_CUTOFF)
    if not close:
        return "no obvious Python counterpart; decide whether one is needed"
    by_expanded = {expand(name): name for name in available}
    named = [by_expanded[c] for c in close if c in by_expanded]
    return "no confident pairing; closest Python exports: " + ", ".join(named)


def _suggest_matlab(python_name: str, matlab_names: list[str]) -> str:
    close = difflib.get_close_matches(expand(python_name), [expand(n) for n in matlab_names], MAX_SUGGESTIONS, SUGGESTION_CUTOFF)
    if not close:
        return "no obvious MATLAB counterpart; decide whether one is needed"
    by_expanded = {expand(name): name for name in matlab_names}
    named = [by_expanded[c] for c in close if c in by_expanded]
    return "no confident pairing; closest MATLAB functions: " + ", ".join(named)


def sync_ledger(pair: Pair, inventory: Inventory | None = None) -> tuple[Ledger, int, SeedSummary]:
    """Top a ledger up with rows for anything it does not yet cover.

    Returns the updated ledger, how many rows were added, and how the pairing went.
    """
    inventory = inventory or build_inventory(pair)

    if pair.ledger.is_file():
        ledger = load_ledger(pair.ledger)
    else:
        ledger = Ledger(
            pair=pair.name,
            matlab_repo=pair.matlab.repo,
            python_repo=pair.python.repo,
            entries=[],
            path=pair.ledger,
        )

    discovered, summary = discover(inventory)
    before = len(ledger.entries)
    ledger.entries = merge_entries(ledger.entries, discovered)
    return ledger, len(ledger.entries) - before, summary
