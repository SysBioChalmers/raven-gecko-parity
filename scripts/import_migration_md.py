"""One-time seeding aid: turn raven-toolbox's `migration.md` into ledger rows.

`docs/reference/migration.md` in raven-toolbox is already a function-by-function map with an
explicit verdict per row, marked with an emoji:

    ✅ ported          -> parity
    🗒️ cheatsheet      -> via-dependency  (cobrapy covers it)
    ⛔ not ported      -> matlab-only
    🆕 new             -> unreviewed      (back-port or python-only? a human decides)

Running this once converts roughly a hundred `unreviewed` rows into real decisions, so
triage starts from what has already been thought through rather than from a blank slate.

    python scripts/import_migration_md.py ../raven-toolbox/docs/reference/migration.md

It never overwrites an existing non-`unreviewed` row, and every row it writes still deserves
a human read --- the doc is prose, and this is a regex.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parity.config import load_config  # noqa: E402
from parity.inventory import build_inventory  # noqa: E402
from parity.ledger import Entry, load_ledger, save_ledger  # noqa: E402

CODE_SPAN = re.compile(r"`([^`]+)`")
LINKED_CODE = re.compile(r"\[`([^`]+)`\]\([^)]*\)")

VERDICTS: list[tuple[str, str]] = [
    ("✅", "parity"),
    ("🗒️", "via-dependency"),
    ("🗒", "via-dependency"),
    ("⛔", "matlab-only"),
    ("🆕", "unreviewed"),
]


def classify(cell: str) -> str | None:
    for marker, status in VERDICTS:
        if marker in cell:
            return status
    return None


def matlab_names(cell: str) -> list[str]:
    """Pull bare MATLAB identifiers out of the first column.

    Cells look like ``` `addRxns` (equations) ``` or ``` `removeMets`, `removeGenes` ```,
    so take every code span and keep the leading identifier.
    """
    names = []
    for span in CODE_SPAN.findall(cell):
        identifier = re.match(r"[A-Za-z_][A-Za-z0-9_]*", span.strip())
        if identifier:
            names.append(identifier.group(0))
    return names


def python_names(cell: str, package: str) -> list[str]:
    """Pull dotted raven-toolbox paths out of the second column and qualify them."""
    spans = LINKED_CODE.findall(cell) + CODE_SPAN.findall(cell)
    out: list[str] = []
    for span in spans:
        span = span.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", span):
            continue
        qualified = span if span.startswith(f"{package}.") else f"{package}.{span}"
        if qualified not in out:
            out.append(qualified)
    return out


def parse_rows(text: str) -> list[tuple[str, str, str]]:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---") or "|---|" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0].lower() in ("raven", "matlab", "function"):
            continue
        rows.append((cells[0], cells[1], cells[2] if len(cells) > 2 else ""))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("migration", help="path to raven-toolbox docs/reference/migration.md")
    parser.add_argument("--pair", default="raven")
    parser.add_argument("-n", "--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_config()
    pair = config.pair(args.pair)
    inventory = build_inventory(pair)
    ledger = load_ledger(pair.ledger)

    known_matlab = inventory.matlab_keys
    known_python = inventory.python_keys
    by_matlab = ledger.by_matlab()

    applied = skipped_unknown = skipped_decided = 0
    claimed_python = {e.python for e in ledger.entries if e.python and e.status != "unreviewed"}

    for matlab_cell, python_cell, notes in parse_rows(Path(args.migration).read_text(encoding="utf-8")):
        status = classify(python_cell)
        if status is None:
            continue

        candidates = python_names(python_cell, pair.python.package)
        resolved = [c for c in candidates if c in known_python]
        names = matlab_names(matlab_cell)

        # A row like `runINIT, scoreComplexModel, getINITModel | run_init, score_..., get_...`
        # is a many-to-many mapping in prose. Which name goes with which is a judgement the
        # doc does not make, so neither does this script.
        if status == "parity" and len(names) > 1 and len(resolved) > 1:
            for name in names:
                entry = by_matlab.get(name)
                if name in known_matlab and entry is not None and entry.status == "unreviewed":
                    entry.notes = (
                        "migration.md maps {" + ", ".join(names) + "} onto {" + ", ".join(resolved) + "} "
                        "as a group; pick the right counterpart"
                    )
            continue

        for name in names:
            if name not in known_matlab:
                skipped_unknown += 1
                continue

            entry = by_matlab.get(name)
            if entry is not None and entry.status != "unreviewed":
                skipped_decided += 1
                continue

            if entry is None:
                entry = Entry(status="unreviewed", matlab=name)
                ledger.entries.append(entry)
                by_matlab[name] = entry

            note = _clean(notes)
            if status == "parity":
                usable = [r for r in resolved if r not in claimed_python]
                if not usable:
                    entry.status = "unreviewed"
                    entry.notes = f"migration.md says ported, but no matching export found: {', '.join(candidates) or '--'}"
                    continue
                displaced = entry.python if entry.python and entry.python != usable[0] else None
                entry.status = "parity"
                entry.python = usable[0]
                claimed_python.add(usable[0])
                _absorb_stub(ledger, entry, usable[0])
                if displaced:
                    # Seeding had paired this row by name; migration.md says otherwise. The
                    # export it displaces still needs a row of its own.
                    ledger.entries.append(
                        Entry(
                            status="unreviewed",
                            python=displaced,
                            notes=f"displaced from {name} by migration.md; find its real counterpart",
                        )
                    )
                extra = f" Also listed: {', '.join(usable[1:])}." if len(usable) > 1 else ""
                entry.notes = f"from migration.md.{extra} {note}".strip()
            elif status == "via-dependency":
                entry.status = "via-dependency"
                entry.python = None
                entry.reason = note or "cobrapy covers this; see migration.md"
            elif status == "matlab-only":
                entry.status = "matlab-only"
                entry.python = None
                entry.reason = note or "not ported; see migration.md"
            else:
                entry.notes = f"new in raven-toolbox per migration.md --- decide back-port vs python-only. {note}".strip()

            applied += 1

    restored = _reconcile(ledger, inventory)

    print(f"applied {applied} row(s) from migration.md")
    print(f"skipped {skipped_unknown} naming functions that no longer exist, {skipped_decided} already decided")
    if restored:
        print(f"reconciled {restored} row(s) so every function is claimed exactly once")

    if args.dry_run:
        print("(dry run --- nothing written)")
        return 0

    save_ledger(ledger, pair.ledger)
    print(f"wrote {pair.ledger}")
    return 0


def _reconcile(ledger, inventory) -> int:
    """Restore the invariant `parity check` enforces: one row per function, no gaps.

    Prose is messier than a schema, so rather than trying to make every heuristic above
    perfectly order-independent, this sweeps up afterwards: strip duplicate claims, then
    give a row back to anything that ended up with none.
    """
    touched = 0
    seen_matlab: set[str] = set()
    seen_python: set[str] = set()

    for entry in ledger.entries:
        for attribute, seen in (("matlab", seen_matlab), ("python", seen_python)):
            value = getattr(entry, attribute)
            if value is None:
                continue
            if value in seen:
                setattr(entry, attribute, None)
                entry.status = "unreviewed"
                entry.notes = f"{value} is claimed by another row; find this one's real counterpart"
                touched += 1
            else:
                seen.add(value)

    ledger.entries[:] = [e for e in ledger.entries if e.matlab or e.python]

    for name in sorted(inventory.matlab_keys - seen_matlab):
        ledger.entries.append(Entry(status="unreviewed", matlab=name, notes="left unpaired after the import"))
        touched += 1
    for name in sorted(inventory.python_keys - seen_python):
        ledger.entries.append(Entry(status="unreviewed", python=name, notes="left unpaired after the import"))
        touched += 1

    return touched


def _absorb_stub(ledger, keep: Entry, python_name: str) -> None:
    """Drop the placeholder row that `parity sync` left for a now-paired Python export.

    Seeding emits a one-sided `unreviewed` row for every Python export it could not pair by
    name. When migration.md then pairs one of them with a MATLAB function, that placeholder
    would otherwise linger and claim the same export twice.
    """
    ledger.entries[:] = [
        entry
        for entry in ledger.entries
        if entry is keep or not (entry.python == python_name and entry.matlab is None and entry.status == "unreviewed")
    ]


def _clean(text: str) -> str:
    """Strip Markdown links and emphasis down to plain prose for a `reason` field."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("**", "").replace("`", "")
    return " ".join(text.split())


if __name__ == "__main__":
    raise SystemExit(main())
