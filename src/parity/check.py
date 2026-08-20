"""Validating a ledger against what the two repos actually contain.

Three failure modes matter, and each one is a way parity silently rots:

* **uncovered** --- a public function exists but no ledger row claims it (new code slipped in
  without anyone deciding whether the other side needs it);
* **stale** --- a ledger row names a function that no longer exists (renamed or deleted);
* **invalid** --- a row's fields contradict its status (e.g. ``parity`` with only one side).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from parity.config import Pair
from parity.inventory import Inventory, build_inventory
from parity.ledger import PENDING, REASON_REQUIRED, STATUSES, Entry, Ledger, load_ledger

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    level: str
    kind: str
    subject: str
    message: str

    def format(self) -> str:
        return f"{self.level:<7} {self.kind:<11} {self.subject}\n        {self.message}"


@dataclass
class CheckResult:
    pair: str
    ledger: Ledger
    inventory: Inventory
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.level == WARNING]

    @property
    def unreviewed(self) -> int:
        return sum(1 for e in self.ledger.entries if e.status == "unreviewed")

    def ok(self, strict: bool = False) -> bool:
        if self.errors:
            return False
        return not (strict and (self.warnings or self.unreviewed))


def _check_entry(entry: Entry, inventory: Inventory) -> list[Finding]:
    findings: list[Finding] = []
    subject = entry.label

    if entry.status not in STATUSES:
        known = ", ".join(STATUSES)
        findings.append(
            Finding(ERROR, "invalid", subject, f"unknown status {entry.status!r} (expected one of: {known})")
        )
        return findings

    if not entry.matlab and not entry.python:
        findings.append(Finding(ERROR, "invalid", subject, "entry names neither a MATLAB nor a Python function"))
        return findings

    # Stale references: the ledger points at something that is no longer there.
    if entry.matlab and entry.matlab not in inventory.matlab_keys:
        findings.append(
            Finding(ERROR, "stale", subject, f"MATLAB function {entry.matlab!r} no longer exists (renamed or removed?)")
        )
    if entry.python and entry.python not in inventory.python_keys:
        findings.append(
            Finding(ERROR, "stale", subject, f"Python export {entry.python!r} no longer exists (renamed or removed?)")
        )

    # Status-specific shape.
    if entry.status == "parity" and not (entry.matlab and entry.python):
        findings.append(
            Finding(ERROR, "invalid", subject, "status 'parity' requires both a 'matlab' and a 'python' function")
        )
    if entry.status == "python-pending" and entry.python:
        findings.append(
            Finding(
                ERROR,
                "invalid",
                subject,
                "status 'python-pending' means the Python side does not exist yet --- "
                "set status to 'parity' now that it does",
            )
        )
    if entry.status == "matlab-pending" and entry.matlab:
        findings.append(
            Finding(
                ERROR,
                "invalid",
                subject,
                "status 'matlab-pending' means the MATLAB side does not exist yet --- "
                "set status to 'parity' now that it does",
            )
        )
    if entry.status == "python-pending" and not entry.matlab:
        findings.append(Finding(ERROR, "invalid", subject, "status 'python-pending' requires a 'matlab' function"))
    if entry.status == "matlab-pending" and not entry.python:
        findings.append(Finding(ERROR, "invalid", subject, "status 'matlab-pending' requires a 'python' export"))
    if entry.status == "matlab-only" and entry.python:
        findings.append(Finding(ERROR, "invalid", subject, "status 'matlab-only' cannot name a Python export"))
    if entry.status == "python-only" and entry.matlab:
        findings.append(Finding(ERROR, "invalid", subject, "status 'python-only' cannot name a MATLAB function"))
    if entry.status == "subsumed" and entry.matlab and entry.python:
        findings.append(
            Finding(
                ERROR,
                "invalid",
                subject,
                "status 'subsumed' names the side that has the standalone function; the other "
                "side folds it into something else, so only one side belongs here",
            )
        )
    if entry.status == "via-dependency" and entry.matlab and entry.python:
        findings.append(
            Finding(
                ERROR,
                "invalid",
                subject,
                "status 'via-dependency' names the side that has the function; the other side's "
                "equivalent lives in a dependency, so only one side belongs here",
            )
        )

    if entry.status in REASON_REQUIRED and not entry.reason:
        findings.append(
            Finding(
                ERROR,
                "invalid",
                subject,
                f"status {entry.status!r} is a deliberate decision and must carry a 'reason'",
            )
        )
    if entry.status in PENDING and not entry.issue:
        findings.append(
            Finding(WARNING, "untracked", subject, f"queued work ({entry.status}) has no tracking 'issue'")
        )
    if entry.status == "unreviewed":
        findings.append(Finding(WARNING, "unreviewed", subject, "needs triage: decide the real status"))

    return findings


def run_check(pair: Pair, inventory: Inventory | None = None, ledger: Ledger | None = None) -> CheckResult:
    """Validate a pair's ledger against a fresh scan of both repos."""
    inventory = inventory or build_inventory(pair)
    ledger = ledger or load_ledger(pair.ledger)
    result = CheckResult(pair=pair.name, ledger=ledger, inventory=inventory)

    # Duplicates first: they would corrupt every count below.
    for side, getter in (("matlab", lambda e: e.matlab), ("python", lambda e: e.python)):
        seen: dict[str, int] = {}
        for entry in ledger.entries:
            key = getter(entry)
            if key:
                seen[key] = seen.get(key, 0) + 1
        for key, count in sorted(seen.items()):
            if count > 1:
                result.findings.append(
                    Finding(ERROR, "duplicate", key, f"claimed by {count} ledger entries on the {side} side")
                )

    for entry in ledger.entries:
        result.findings.extend(_check_entry(entry, inventory))

    # Coverage: every public function must be claimed by exactly one row.
    covered_matlab = {e.matlab for e in ledger.entries if e.matlab}
    covered_python = {e.python for e in ledger.entries if e.python}

    for function in inventory.matlab:
        if function.key not in covered_matlab:
            result.findings.append(
                Finding(
                    ERROR,
                    "uncovered",
                    function.key,
                    f"public MATLAB function ({function.path}) has no ledger entry --- "
                    "add one declaring whether Python needs it",
                )
            )
    for export in inventory.python:
        if export.key not in covered_python:
            result.findings.append(
                Finding(
                    ERROR,
                    "uncovered",
                    export.key,
                    f"public Python export ({export.defined_in}) has no ledger entry --- "
                    "add one declaring whether MATLAB needs it",
                )
            )

    return result
