"""Answering "what did I just change, and what does that mean for the other side?".

This is the local stand-in for a cross-repo bot: run it against a commit range (or your
uncommitted work) in any of the four repos and it maps the touched files back through the
ledger to the sibling functions that now need attention.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from parity.config import Pair
from parity.inventory import Inventory, build_inventory
from parity.ledger import Entry, Ledger, load_ledger


class GitError(RuntimeError):
    """Raised when git cannot answer a question about a repo."""


def _git(repo: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:  # pragma: no cover - depends on the host
        raise GitError("git is not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise GitError(f"git {' '.join(args)} failed in {repo}:\n{exc.stderr.strip()}") from exc
    return completed.stdout


def describe(repo: Path) -> str:
    """A short human-readable "which checkout is this?" for provenance.

    Worth printing on every check: a ledger is only meaningful against a specific pair of
    revisions, and scanning a feature branch gives different answers than scanning develop.
    """
    try:
        branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
        commit = _git(repo, "rev-parse", "--short", "HEAD").strip()
    except GitError:
        return "not a git checkout"
    dirty = bool(_git(repo, "status", "--porcelain").strip())
    return f"{branch}@{commit}{' +dirty' if dirty else ''}"


def changed_files(repo: Path, since: str | None = None) -> list[str]:
    """Repo-relative paths changed in *since* (a rev or range), or in the working tree."""
    if since:
        rev_range = since if ".." in since else f"{since}..HEAD"
        output = _git(repo, "diff", "--name-only", rev_range)
        return sorted(line for line in output.splitlines() if line)

    tracked = _git(repo, "diff", "--name-only", "HEAD")
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard")
    return sorted({line for line in (tracked + untracked).splitlines() if line})


@dataclass
class Touched:
    """One ledger row reached by a changed file."""

    entry: Entry
    via: str


@dataclass
class MirrorResult:
    pair: str
    side: str
    files: list[str]
    at_parity: list[Touched] = field(default_factory=list)
    divergent: list[Touched] = field(default_factory=list)
    pending: list[Touched] = field(default_factory=list)
    unreviewed: list[Touched] = field(default_factory=list)
    unmapped: list[str] = field(default_factory=list)

    @property
    def needs_attention(self) -> bool:
        return bool(self.at_parity or self.unreviewed)


def _sibling_label(entry: Entry, side: str) -> str:
    return (entry.python if side == "matlab" else entry.matlab) or "--"


def analyse(
    pair: Pair,
    side: str,
    since: str | None = None,
    inventory: Inventory | None = None,
    ledger: Ledger | None = None,
) -> MirrorResult:
    """Map changes on one side of a pair to the ledger rows they touch."""
    inventory = inventory or build_inventory(pair)
    ledger = ledger or load_ledger(pair.ledger)
    repo = pair.side(side).path

    files = changed_files(repo, since)
    result = MirrorResult(pair=pair.name, side=side, files=files)

    by_matlab, by_python = ledger.by_matlab(), ledger.by_python()
    matlab_paths = inventory.matlab_by_path()
    python_sources = inventory.python_by_source()

    for path in files:
        reached: list[tuple[Entry, str]] = []
        if side == "matlab":
            function = matlab_paths.get(path)
            if function and function.name in by_matlab:
                reached.append((by_matlab[function.name], function.name))
        else:
            for export in python_sources.get(path, []):
                if export.qualname in by_python:
                    reached.append((by_python[export.qualname], export.qualname))

        if not reached:
            if path.endswith((".m", ".py")):
                result.unmapped.append(path)
            continue

        for entry, via in reached:
            touched = Touched(entry=entry, via=via)
            if entry.status == "parity":
                result.at_parity.append(touched)
            elif entry.status in ("python-pending", "matlab-pending"):
                result.pending.append(touched)
            elif entry.status == "unreviewed":
                result.unreviewed.append(touched)
            else:
                result.divergent.append(touched)

    return result


def render(result: MirrorResult, pair: Pair, brief: bool = False) -> str:
    """Format a mirror analysis for a terminal or a git hook."""
    other = "python" if result.side == "matlab" else "matlab"
    other_repo = pair.side(other).repo

    if not result.files:
        return "parity: no changed files."

    if not (result.at_parity or result.pending or result.unreviewed or result.divergent):
        return f"parity: {len(result.files)} changed file(s), none mapped to a ledger entry."

    lines: list[str] = []
    header = f"parity [{result.pair}]: {len(result.files)} changed file(s) on the {result.side} side"
    lines.append(header)

    if result.at_parity:
        lines.append("")
        lines.append(f"  MIRROR -> {other_repo}  (these are declared at parity)")
        for touched in result.at_parity:
            lines.append(f"    {touched.via}")
            lines.append(f"      -> {_sibling_label(touched.entry, result.side)}")
            if touched.entry.scenarios and not brief:
                lines.append(f"      scenarios: {', '.join(touched.entry.scenarios)}")

    if result.unreviewed:
        lines.append("")
        lines.append("  TRIAGE  (touched, but the ledger has not decided their status yet)")
        for touched in result.unreviewed:
            lines.append(f"    {touched.via}")

    if result.pending and not brief:
        lines.append("")
        lines.append("  QUEUED  (already known to be one-sided)")
        for touched in result.pending:
            issue = f"  [{touched.entry.issue}]" if touched.entry.issue else ""
            lines.append(f"    {touched.via}  ({touched.entry.status}){issue}")

    if result.divergent and not brief:
        lines.append("")
        lines.append("  DIVERGENT  (deliberate --- no mirroring expected)")
        for touched in result.divergent:
            lines.append(f"    {touched.via}  ({touched.entry.status})")

    if result.unmapped and not brief:
        lines.append("")
        lines.append(f"  {len(result.unmapped)} changed source file(s) map to no public function.")

    return "\n".join(lines)
