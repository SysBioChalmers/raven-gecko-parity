"""The parity ledger: one declared status per public function, on both sides."""

from __future__ import annotations

import io
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

#: Every public function on either side must carry exactly one of these.
STATUSES: dict[str, str] = {
    "parity": "Both sides implement this and are intended to behave the same.",
    "python-pending": "MATLAB has it; a Python port is queued.",
    "matlab-pending": "Python has it; a MATLAB back-port is queued.",
    "matlab-only": "Deliberately MATLAB-only --- not coming to Python.",
    "python-only": "Deliberately Python-only --- not going to MATLAB.",
    "via-dependency": "The other side gets this from a dependency (cobrapy, COBRA Toolbox) instead.",
    "internal": "Not part of the cross-implementation API (glue, installers, helpers).",
    "unreviewed": "Not yet triaged. Drive this count to zero.",
}

#: Statuses that must justify themselves in prose.
REASON_REQUIRED = frozenset({"matlab-only", "python-only", "via-dependency", "internal"})

#: Statuses that describe a settled one-sided decision rather than queued work.
ONE_SIDED = frozenset({"matlab-only", "python-only", "via-dependency"})

#: Statuses that represent queued work rather than a settled decision.
PENDING = frozenset({"python-pending", "matlab-pending"})

FIELD_ORDER = ("matlab", "python", "status", "reason", "issue", "scenarios", "notes")


class LedgerError(RuntimeError):
    """Raised when a ledger file cannot be parsed into entries."""


@dataclass
class Entry:
    """One row: a function on one or both sides, plus why it is where it is."""

    status: str
    matlab: str | None = None
    python: str | None = None
    reason: str | None = None
    issue: str | None = None
    notes: str | None = None
    scenarios: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        """A stable human-facing name for the row."""
        return self.matlab or self.python or "<empty>"

    @property
    def sort_key(self) -> tuple[str, str]:
        return ((self.matlab or "~").lower(), (self.python or "~").lower())

    def to_dict(self) -> dict:
        out: dict[str, object] = {}
        for name in FIELD_ORDER:
            value = getattr(self, name)
            if value in (None, "", []):
                continue
            out[name] = value
        return out


@dataclass
class Ledger:
    pair: str
    matlab_repo: str
    python_repo: str
    entries: list[Entry]
    version: int = 1
    path: Path | None = None

    def by_matlab(self) -> dict[str, Entry]:
        return {e.matlab: e for e in self.entries if e.matlab}

    def by_python(self) -> dict[str, Entry]:
        return {e.python: e for e in self.entries if e.python}

    def with_status(self, *statuses: str) -> list[Entry]:
        wanted = set(statuses)
        return [e for e in self.entries if e.status in wanted]

    def counts(self) -> dict[str, int]:
        out = {status: 0 for status in STATUSES}
        for entry in self.entries:
            out[entry.status] = out.get(entry.status, 0) + 1
        return out


def load_ledger(path: Path) -> Ledger:
    """Read a ledger YAML file."""
    if not path.is_file():
        raise LedgerError(f"ledger not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise LedgerError(f"{path}: expected a mapping at the top level")

    raw_entries = data.get("entries") or []
    if not isinstance(raw_entries, list):
        raise LedgerError(f"{path}: 'entries' must be a list")

    entries: list[Entry] = []
    for index, raw in enumerate(raw_entries, start=1):
        if not isinstance(raw, dict):
            raise LedgerError(f"{path}: entry {index} is not a mapping")
        unknown = set(raw) - set(FIELD_ORDER)
        if unknown:
            raise LedgerError(f"{path}: entry {index} has unknown field(s): {', '.join(sorted(unknown))}")
        if "status" not in raw:
            raise LedgerError(f"{path}: entry {index} has no 'status'")
        scenarios = raw.get("scenarios") or []
        if isinstance(scenarios, str):
            scenarios = [scenarios]
        entries.append(
            Entry(
                status=str(raw["status"]),
                matlab=raw.get("matlab"),
                python=raw.get("python"),
                reason=raw.get("reason"),
                issue=raw.get("issue"),
                notes=raw.get("notes"),
                scenarios=list(scenarios),
            )
        )

    return Ledger(
        pair=data.get("pair", path.stem),
        matlab_repo=data.get("matlab", ""),
        python_repo=data.get("python", ""),
        entries=entries,
        version=int(data.get("version", 1)),
        path=path,
    )


HEADER = """\
# Parity ledger --- {pair}
#
# One row per public function on either side. `parity check` fails if a public
# function is missing here, or if a row names something that no longer exists.
#
# status:
{status_help}
#
# Regenerate the human-readable view with: parity report --pair {pair}
"""


def dump_ledger(ledger: Ledger) -> str:
    """Serialise a ledger deterministically, so diffs stay readable."""
    status_help = "\n".join(f"#   {name:<15} {help_}" for name, help_ in STATUSES.items())
    buffer = io.StringIO()
    buffer.write(HEADER.format(pair=ledger.pair, status_help=status_help))
    buffer.write("\n")

    head = {
        "version": ledger.version,
        "pair": ledger.pair,
        "matlab": ledger.matlab_repo,
        "python": ledger.python_repo,
    }
    buffer.write(yaml.safe_dump(head, sort_keys=False, allow_unicode=True))
    buffer.write("\nentries:\n")

    for entry in sorted(ledger.entries, key=lambda e: e.sort_key):
        rendered = yaml.safe_dump(
            entry.to_dict(), sort_keys=False, allow_unicode=True, default_flow_style=False, width=100
        )
        lines = rendered.rstrip("\n").split("\n")
        buffer.write(f"  - {lines[0]}\n")
        for line in lines[1:]:
            buffer.write(f"    {line}\n")

    return buffer.getvalue()


def save_ledger(ledger: Ledger, path: Path | None = None) -> Path:
    target = path or ledger.path
    if target is None:
        raise LedgerError("no path to save the ledger to")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dump_ledger(ledger), encoding="utf-8")
    return target


def merge_entries(existing: list[Entry], discovered: list[Entry]) -> list[Entry]:
    """Add *discovered* rows for anything *existing* does not already cover.

    Hand-written decisions always win: a discovered row is dropped if either of its
    sides is already claimed by an existing row.
    """
    claimed_matlab = {e.matlab for e in existing if e.matlab}
    claimed_python = {e.python for e in existing if e.python}

    merged = list(existing)
    for entry in discovered:
        if entry.matlab and entry.matlab in claimed_matlab:
            continue
        if entry.python and entry.python in claimed_python:
            continue
        merged.append(replace(entry))
        if entry.matlab:
            claimed_matlab.add(entry.matlab)
        if entry.python:
            claimed_python.add(entry.python)
    return merged
