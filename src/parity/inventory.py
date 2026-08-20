"""Enumerating the public API of each side of a pair.

MATLAB: one public function per ``.m`` file, so the file tree *is* the API list once
vendored code, tests and tutorials are excluded.

Python: the public API is what the sub-package ``__init__.py`` files re-export in their
``__all__``. Parsed with :mod:`ast` rather than imported, so the scan needs neither the
package's dependencies nor an installed copy.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from parity.config import MatlabSide, PythonSide


@dataclass(frozen=True)
class MatlabFunction:
    """A public MATLAB function --- ``name`` is the API, ``path`` merely where it lives."""

    name: str
    path: str

    @property
    def key(self) -> str:
        return self.name


@dataclass(frozen=True)
class PythonExport:
    """A name re-exported from a sub-package ``__init__.py``.

    ``aliases`` holds the other places the same object is re-exported from --- geckopy, for
    instance, surfaces most of its API both at ``geckopy.X`` and at ``geckopy.subpkg.X``.
    Those are one function, so they get one ledger row: the shortest qualname is canonical.
    """

    qualname: str
    name: str
    module: str
    defined_in: str | None
    aliases: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return self.qualname


@dataclass(frozen=True)
class Inventory:
    matlab: tuple[MatlabFunction, ...]
    python: tuple[PythonExport, ...]

    @property
    def matlab_keys(self) -> set[str]:
        return {fn.key for fn in self.matlab}

    @property
    def python_keys(self) -> set[str]:
        return {export.key for export in self.python}

    def matlab_by_path(self) -> dict[str, MatlabFunction]:
        return {fn.path: fn for fn in self.matlab}

    def python_by_source(self) -> dict[str, list[PythonExport]]:
        """Map a defining module's repo-relative path to the exports it provides."""
        out: dict[str, list[PythonExport]] = {}
        for export in self.python:
            if export.defined_in:
                out.setdefault(export.defined_in, []).append(export)
        return out


def _is_excluded(relative: Path, exclude: tuple[str, ...]) -> bool:
    posix = relative.as_posix()
    parts = set(relative.parts)
    for pattern in exclude:
        if "/" in pattern:
            if posix == pattern or posix.startswith(pattern.rstrip("/") + "/"):
                return True
        elif pattern in parts:
            return True
    # MATLAB's own privacy conventions: private/, +packages, @class folders.
    return any(part == "private" or part.startswith(("+", "@")) for part in relative.parts[:-1])


def scan_matlab(side: MatlabSide) -> tuple[MatlabFunction, ...]:
    """List the public ``.m`` functions of a MATLAB repo."""
    if not side.path.is_dir():
        raise FileNotFoundError(f"MATLAB repo not found: {side.path}")

    found: list[MatlabFunction] = []
    for file in sorted(side.path.rglob("*.m")):
        relative = file.relative_to(side.path)
        if ".git" in relative.parts or _is_excluded(relative, side.exclude):
            continue
        found.append(MatlabFunction(name=file.stem, path=relative.as_posix()))
    return tuple(found)


def _literal_all(tree: ast.Module) -> list[str] | None:
    """Extract a module-level ``__all__`` of string literals, following runtime semantics.

    A module may assign ``__all__`` more than once and may extend it with ``+=``; the last
    plain assignment wins and later augmentations add to it, exactly as at import time.
    """
    names: list[str] | None = None
    for node in tree.body:
        if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add):
            target = node.target
            if isinstance(target, ast.Name) and target.id == "__all__" and names is not None:
                names = names + _string_elements(node.value)
            continue

        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, ast.AnnAssign) and node.value is not None
            else []
        )
        if any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
            names = _string_elements(node.value)
    return names


def _string_elements(value: ast.expr | None) -> list[str]:
    if not isinstance(value, (ast.List, ast.Tuple)):
        return []
    return [e.value for e in value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]


def _locally_defined(tree: ast.Module) -> set[str]:
    """Names bound by a def/class/assignment in this module rather than imported."""
    bound: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Assign):
            bound.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            bound.add(node.target.id)
    return bound


def _import_sources(tree: ast.Module, package: str) -> dict[str, str]:
    """Map each imported name to the dotted module it was imported from."""
    sources: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        if node.level:
            # Relative import: resolve against the package containing this __init__.py.
            base = package.split(".")
            trimmed = base[: len(base) - (node.level - 1)] if node.level > 1 else base
            module = ".".join([*trimmed, module]) if module else ".".join(trimmed)
        for alias in node.names:
            sources[alias.asname or alias.name] = module
    return sources


def _module_file(module: str, src_root: Path, repo_root: Path) -> str | None:
    """Resolve a dotted module to a repo-relative file path, if it exists on disk."""
    stem = src_root / Path(*module.split("."))
    for candidate in (stem.with_suffix(".py"), stem / "__init__.py"):
        if candidate.is_file():
            return candidate.relative_to(repo_root).as_posix()
    return None


@dataclass(frozen=True)
class _PackageInfo:
    """What one ``__init__.py`` re-exports, and from where."""

    path: str
    sources: dict[str, str]
    local: set[str]
    exported: tuple[str, ...] | None


def _scan_packages(package_root: Path, src_root: Path, repo_root: Path) -> dict[str, _PackageInfo]:
    """Read every ``__init__.py`` under the package, whether or not it declares ``__all__``."""
    packages: dict[str, _PackageInfo] = {}
    for init in sorted(package_root.rglob("__init__.py")):
        module = ".".join(init.relative_to(src_root).parent.parts)
        tree = ast.parse(init.read_text(encoding="utf-8"), filename=str(init))
        names = _literal_all(tree)
        packages[module] = _PackageInfo(
            path=init.relative_to(repo_root).as_posix(),
            sources=_import_sources(tree, module),
            local=_locally_defined(tree),
            exported=tuple(names) if names is not None else None,
        )
    return packages


def _resolve_definition(
    module: str,
    name: str,
    packages: dict[str, _PackageInfo],
    src_root: Path,
    repo_root: Path,
) -> str | None:
    """Follow re-export chains to the module that actually defines *name*.

    ``geckopy.apply_complex_data`` is re-exported from ``geckopy.limit_proteins``, which in
    turn re-exports it from ``geckopy.limit_proteins.apply_complex_data``. Only the last of
    those is the definition, and only that answer makes two aliases collapse into one row
    (and makes an edit to the defining file map back to the export).
    """
    seen: set[str] = set()
    current = module

    while current not in seen:
        seen.add(current)
        info = packages.get(current)
        if info is None:
            # A plain module rather than a package: this is where the trail ends.
            return _module_file(current, src_root, repo_root)
        if name in info.sources:
            current = info.sources[name]
            continue
        if name in info.local:
            return info.path
        return info.path

    return _module_file(current, src_root, repo_root)


def scan_python(side: PythonSide) -> tuple[PythonExport, ...]:
    """List the public API of a Python package, as declared by ``__all__``."""
    package_root = side.package_root
    if not package_root.is_dir():
        raise FileNotFoundError(f"Python package not found: {package_root}")

    src_root = side.path / side.src
    packages = _scan_packages(package_root, src_root, side.path)

    found: list[PythonExport] = []
    seen: set[str] = set()

    for module, info in packages.items():
        if not info.exported:
            continue
        for name in info.exported:
            qualname = f"{module}.{name}"
            if qualname in seen:
                continue
            seen.add(qualname)
            found.append(
                PythonExport(
                    qualname=qualname,
                    name=name,
                    module=module,
                    defined_in=_resolve_definition(module, name, packages, src_root, side.path),
                )
            )

    return _collapse_aliases(found)


def _collapse_aliases(exports: list[PythonExport]) -> tuple[PythonExport, ...]:
    """Fold re-exports of the same object into a single canonical entry.

    Two exports are the same function when they share a name *and* a defining module. The
    shortest qualname wins (ties broken alphabetically), which picks the top-level
    ``geckopy.make_ec_model`` over ``geckopy.ec_model.make_ec_model``.
    """
    grouped: dict[tuple[str, str | None], list[PythonExport]] = {}
    unresolved: list[PythonExport] = []

    for export in exports:
        if export.defined_in is None:
            unresolved.append(export)
        else:
            grouped.setdefault((export.name, export.defined_in), []).append(export)

    collapsed: list[PythonExport] = list(unresolved)
    for group in grouped.values():
        canonical, *rest = sorted(group, key=lambda e: (len(e.qualname), e.qualname))
        collapsed.append(
            PythonExport(
                qualname=canonical.qualname,
                name=canonical.name,
                module=canonical.module,
                defined_in=canonical.defined_in,
                aliases=tuple(sorted(e.qualname for e in rest)),
            )
        )

    return tuple(sorted(collapsed, key=lambda e: e.qualname))


def build_inventory(pair) -> Inventory:
    """Scan both sides of a pair."""
    return Inventory(matlab=scan_matlab(pair.matlab), python=scan_python(pair.python))
