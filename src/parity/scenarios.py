"""Cross-implementation behaviour tests.

A scenario is a directory holding a declaration (``scenario.yml``), a Python entry point
(``run.py``, exposing ``run(ctx) -> dict``) and a MATLAB entry point (``run.m``, returning a
struct). Both are handed the same inputs and both write their results to JSON in the same
shape; ``parity compare`` then diffs the two within a declared tolerance.

Name parity says the two toolboxes have the same functions. This says they still produce
the same numbers.
"""

from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

RESULT_VERSION = 1


class ScenarioError(RuntimeError):
    """Raised when a scenario is malformed or cannot be executed."""


@dataclass(frozen=True)
class Tolerance:
    rel: float = 1e-6
    abs: float = 1e-9

    def close(self, left: float, right: float) -> bool:
        return math.isclose(left, right, rel_tol=self.rel, abs_tol=self.abs)


@dataclass(frozen=True)
class Scenario:
    id: str
    pair: str
    description: str
    directory: Path
    inputs: dict
    entries: tuple[str, ...] = ()
    tolerance: Tolerance = field(default_factory=Tolerance)

    @property
    def python_entry(self) -> Path:
        return self.directory / "run.py"

    @property
    def matlab_entry(self) -> Path:
        """``<id>.m``, not ``run.m`` --- ``run`` is a MATLAB builtin, and a file per scenario
        named after the scenario keeps two scenarios from shadowing each other on the path."""
        return self.directory / f"{self.id}.m"


def load_scenario(directory: Path) -> Scenario:
    """Read one scenario directory."""
    spec_file = directory / "scenario.yml"
    if not spec_file.is_file():
        raise ScenarioError(f"no scenario.yml in {directory}")

    data = yaml.safe_load(spec_file.read_text(encoding="utf-8")) or {}
    tolerance = data.get("tolerance") or {}
    return Scenario(
        id=data.get("id", directory.name),
        pair=data.get("pair", ""),
        description=data.get("description", ""),
        directory=directory,
        inputs=data.get("inputs") or {},
        entries=tuple(data.get("entries") or ()),
        tolerance=Tolerance(
            rel=float(tolerance.get("rel", 1e-6)),
            abs=float(tolerance.get("abs", 1e-9)),
        ),
    )


def list_scenarios(root: Path, pair: str | None = None) -> list[Scenario]:
    """Every scenario under *root*, optionally filtered to one pair."""
    if not root.is_dir():
        return []
    found = [load_scenario(child) for child in sorted(root.iterdir()) if (child / "scenario.yml").is_file()]
    return [s for s in found if not pair or s.pair == pair]


def build_context(scenario: Scenario, repo_root: Path, pair=None) -> dict:
    """The inputs handed identically to both implementations.

    String inputs may use ``{scenario_dir}``, ``{repo_root}``, ``{matlab_repo}`` and
    ``{python_repo}`` placeholders, and bare relative paths resolve against the scenario
    directory. Both sides therefore read the same bytes off disk --- which matters more than
    it sounds: a scenario that quietly fed the two implementations different files would
    report differences that are nothing to do with the code.
    """
    substitutions = {
        "scenario_dir": scenario.directory.resolve().as_posix(),
        "repo_root": repo_root.resolve().as_posix(),
    }
    if pair is not None:
        substitutions["matlab_repo"] = pair.matlab.path.as_posix()
        substitutions["python_repo"] = pair.python.path.as_posix()

    resolved = {}
    for key, value in scenario.inputs.items():
        resolved[key] = _resolve_input(value, scenario.directory, substitutions)

    return {
        "scenario": scenario.id,
        "scenario_dir": substitutions["scenario_dir"],
        "repo_root": substitutions["repo_root"],
        "inputs": resolved,
    }


def _resolve_input(value, scenario_dir: Path, substitutions: dict[str, str]):
    if not isinstance(value, str):
        return value

    if "{" in value:
        try:
            value = value.format(**substitutions)
        except KeyError as exc:
            raise ScenarioError(f"unknown placeholder {exc} in scenario input {value!r}") from None

    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = scenario_dir / value
    if candidate.exists():
        return candidate.resolve().as_posix()

    # Not a path --- a number-as-string, an identifier, a flag.
    return value


def _canonical(value):
    """Reduce a result to JSON-safe primitives, without losing numeric precision."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if hasattr(value, "tolist"):  # numpy arrays, pandas Series/Index
        return _canonical(value.tolist())
    if hasattr(value, "to_dict"):  # pandas DataFrame
        return _canonical(value.to_dict(orient="list"))
    return str(value)


def run_python(scenario: Scenario, repo_root: Path, pair=None) -> dict:
    """Execute a scenario's Python side in this interpreter."""
    entry = scenario.python_entry
    if not entry.is_file():
        raise ScenarioError(f"scenario {scenario.id} has no run.py")

    spec = importlib.util.spec_from_file_location(f"parity_scenario_{scenario.id}", entry)
    if spec is None or spec.loader is None:
        raise ScenarioError(f"cannot load {entry}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "run"):
        raise ScenarioError(f"{entry} defines no run(ctx) function")

    results = module.run(build_context(scenario, repo_root, pair))
    if not isinstance(results, dict):
        raise ScenarioError(f"{entry}: run(ctx) must return a dict of named results")

    return {
        "result_version": RESULT_VERSION,
        "scenario": scenario.id,
        "implementation": "python",
        "runtime": f"python {sys.version.split()[0]}",
        "results": _canonical(results),
    }


def run_matlab(scenario: Scenario, repo_root: Path, pair=None, matlab: str = "matlab") -> dict:
    """Execute a scenario's MATLAB side via ``matlab -batch``."""
    entry = scenario.matlab_entry
    if not entry.is_file():
        raise ScenarioError(f"scenario {scenario.id} has no run.m")

    harness = repo_root / "matlab"
    context_file = scenario.directory / ".context.json"
    output_file = scenario.directory / ".matlab_result.json"
    context_file.write_text(json.dumps(build_context(scenario, repo_root, pair), indent=2), encoding="utf-8")

    setup = f"{pair.matlab.setup_command}; " if pair is not None else ""
    command = "addpath('{harness}'); {setup}parity_run('{directory}', '{context}', '{output}');".format(
        harness=harness.as_posix(),
        setup=setup,
        directory=scenario.directory.as_posix(),
        context=context_file.as_posix(),
        output=output_file.as_posix(),
    )
    try:
        completed = subprocess.run([matlab, "-batch", command], capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise ScenarioError(
            f"{matlab!r} is not on PATH --- run the scenario from inside MATLAB instead:\n"
            f"    addpath('{harness.as_posix()}')\n"
            f"    parity_run('{scenario.directory.as_posix()}')"
        ) from exc

    if completed.returncode != 0 or not output_file.is_file():
        raise ScenarioError(
            f"MATLAB run of {scenario.id} failed (exit {completed.returncode}):\n"
            f"{completed.stdout.strip()}\n{completed.stderr.strip()}"
        )

    return json.loads(output_file.read_text(encoding="utf-8"))


@dataclass
class Difference:
    path: str
    left: object
    right: object
    note: str

    def format(self) -> str:
        return f"  {self.path}\n      {self.note}\n      left={self.left!r}  right={self.right!r}"


def compare_values(left, right, tolerance: Tolerance, path: str = "results") -> list[Difference]:
    """Structurally compare two result trees within *tolerance*."""
    if isinstance(left, bool) or isinstance(right, bool):
        # Checked before the numeric branch, and by type as well as value: in Python
        # ``True == 1``, so a flag on one side and a count on the other would otherwise
        # compare equal. That is a shape disagreement between the two harnesses, and the
        # whole point is to surface it.
        if isinstance(left, bool) != isinstance(right, bool):
            return [Difference(path, left, right, "one side is a boolean, the other is not")]
        return [] if left == right else [Difference(path, left, right, "boolean mismatch")]

    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if not tolerance.close(float(left), float(right)):
            delta = abs(float(left) - float(right))
            return [Difference(path, left, right, f"numeric mismatch (|delta| = {delta:.6g})")]
        return []

    if isinstance(left, dict) and isinstance(right, dict):
        differences: list[Difference] = []
        for key in sorted(set(left) - set(right)):
            differences.append(Difference(f"{path}.{key}", left[key], None, "present on the left only"))
        for key in sorted(set(right) - set(left)):
            differences.append(Difference(f"{path}.{key}", None, right[key], "present on the right only"))
        for key in sorted(set(left) & set(right)):
            differences.extend(compare_values(left[key], right[key], tolerance, f"{path}.{key}"))
        return differences

    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return [Difference(path, len(left), len(right), "length mismatch")]
        differences = []
        for index, (a, b) in enumerate(zip(left, right)):
            differences.extend(compare_values(a, b, tolerance, f"{path}[{index}]"))
        return differences

    if left != right:
        return [Difference(path, left, right, f"mismatch ({type(left).__name__} vs {type(right).__name__})")]
    return []


def compare_results(left: dict, right: dict, tolerance: Tolerance) -> list[Difference]:
    """Compare two result documents produced by :func:`run_python` / :func:`run_matlab`."""
    if left.get("scenario") != right.get("scenario"):
        return [
            Difference(
                "scenario",
                left.get("scenario"),
                right.get("scenario"),
                "these results are from different scenarios",
            )
        ]
    return compare_values(left.get("results"), right.get("results"), tolerance)


def write_result(document: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
