"""Loading `parity.toml` --- where the repos live and how to scan them."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_NAME = "parity.toml"
LOCAL_CONFIG_NAME = "parity.local.toml"


class ConfigError(RuntimeError):
    """Raised when `parity.toml` is missing, malformed, or points nowhere."""


@dataclass(frozen=True)
class MatlabSide:
    repo: str
    path: Path
    #: The branch this pair is compared at. Stated here rather than left to each
    #: repo's default: RAVEN's default is `main` while the ledger describes
    #: `develop3`, so taking defaults quietly compares a release branch against a
    #: development one.
    ref: str = "main"
    exclude: tuple[str, ...] = ()
    #: MATLAB run before a scenario, to put the toolbox on the path. ``{path}`` is this
    #: repo's location. Override it for toolboxes with a real installer.
    setup: str = "addpath(genpath('{path}'))"

    @property
    def setup_command(self) -> str:
        return self.setup.replace("{path}", self.path.as_posix())

    @property
    def label(self) -> str:
        return "matlab"


@dataclass(frozen=True)
class PythonSide:
    repo: str
    path: Path
    package: str
    ref: str = "main"
    src: str = "src"

    @property
    def label(self) -> str:
        return "python"

    @property
    def package_root(self) -> Path:
        return self.path / self.src / self.package


@dataclass(frozen=True)
class Pair:
    name: str
    ledger: Path
    matlab: MatlabSide
    python: PythonSide

    def side(self, label: str) -> MatlabSide | PythonSide:
        if label == "matlab":
            return self.matlab
        if label == "python":
            return self.python
        raise ConfigError(f"unknown side {label!r} (expected 'matlab' or 'python')")


@dataclass(frozen=True)
class Config:
    root: Path
    pairs: dict[str, Pair]

    def pair(self, name: str) -> Pair:
        try:
            return self.pairs[name]
        except KeyError:
            known = ", ".join(sorted(self.pairs)) or "<none>"
            raise ConfigError(f"unknown pair {name!r} (configured: {known})") from None


def find_config(start: Path | None = None) -> Path:
    """Walk up from *start* looking for `parity.toml`."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        found = candidate / CONFIG_NAME
        if found.is_file():
            return found
    raise ConfigError(f"no {CONFIG_NAME} found in {here} or any parent directory")


def _merge(base: dict, overlay: dict) -> dict:
    """Recursively overlay *overlay* onto *base* (overlay wins on scalars)."""
    out = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: Path | None = None) -> Config:
    """Load `parity.toml`, overlaid with `parity.local.toml` when present.

    Individual paths can also be overridden from the environment, e.g.
    ``PARITY_RAVEN_MATLAB_PATH=/checkouts/RAVEN``.
    """
    config_path = (path or find_config()).resolve()
    root = config_path.parent

    with config_path.open("rb") as handle:
        data = tomllib.load(handle)

    local_path = root / LOCAL_CONFIG_NAME
    if local_path.is_file():
        with local_path.open("rb") as handle:
            data = _merge(data, tomllib.load(handle))

    raw_pairs = data.get("pairs")
    if not raw_pairs:
        raise ConfigError(f"{config_path} declares no [pairs.*] tables")

    pairs: dict[str, Pair] = {}
    for name, spec in raw_pairs.items():
        for required in ("ledger", "matlab", "python"):
            if required not in spec:
                raise ConfigError(f"pair {name!r} is missing '{required}'")

        matlab_spec, python_spec = spec["matlab"], spec["python"]
        pairs[name] = Pair(
            name=name,
            ledger=root / spec["ledger"],
            matlab=MatlabSide(
                repo=matlab_spec["repo"],
                path=_resolve(root, name, "matlab", matlab_spec["path"]),
                ref=matlab_spec.get("ref", MatlabSide.ref),
                exclude=tuple(matlab_spec.get("exclude", ())),
                setup=matlab_spec.get("setup", MatlabSide.setup),
            ),
            python=PythonSide(
                repo=python_spec["repo"],
                path=_resolve(root, name, "python", python_spec["path"]),
                package=python_spec["package"],
                ref=python_spec.get("ref", PythonSide.ref),
                src=python_spec.get("src", "src"),
            ),
        )

    return Config(root=root, pairs=pairs)


def _resolve(root: Path, pair: str, side: str, configured: str) -> Path:
    override = os.environ.get(f"PARITY_{pair.upper()}_{side.upper()}_PATH")
    raw = Path(override or configured)
    return raw.resolve() if raw.is_absolute() else (root / raw).resolve()
