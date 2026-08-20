"""Install the parity git hooks into the four repos.

    python hooks/install.py            # all four repos from parity.toml
    python hooks/install.py --pair raven
    python hooks/install.py --uninstall

The hooks are advisory: they print what the other implementation owes and get out of the
way. An existing hook is never clobbered --- if one is already there and is not ours, the
installer says so and skips it.
"""

from __future__ import annotations

import argparse
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parity.config import load_config  # noqa: E402

HOOKS = ("post-commit", "pre-push")
MARKER = "# parity:"


def hook_body(source: Path, config_path: Path) -> str:
    """Point the hook at this checkout, so it works from any repo."""
    text = source.read_text(encoding="utf-8")
    return text.replace(
        "set -e\n",
        f'set -e\n\n{MARKER} installed by hooks/install.py\nPARITY_CONFIG="{config_path.as_posix()}"\nexport PARITY_CONFIG\n',
        1,
    )


def install_one(repo: Path, label: str, config_path: Path, uninstall: bool) -> None:
    hooks_dir = repo / ".git" / "hooks"
    if not hooks_dir.is_dir():
        print(f"  {label:<28} skipped (no .git/hooks --- is {repo} a git checkout?)")
        return

    for name in HOOKS:
        target = hooks_dir / name
        source = Path(__file__).parent / name

        if uninstall:
            if target.is_file() and MARKER in target.read_text(encoding="utf-8"):
                target.unlink()
                print(f"  {label:<28} removed {name}")
            continue

        if target.is_file():
            existing = target.read_text(encoding="utf-8")
            if MARKER not in existing:
                print(f"  {label:<28} skipped {name} (a different hook is already installed)")
                continue

        target.write_text(hook_body(source, config_path), encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"  {label:<28} installed {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pair", help="only this pair (default: all)")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()

    config = load_config()
    config_path = config.root / "parity.toml"
    names = [args.pair] if args.pair else sorted(config.pairs)

    for name in names:
        pair = config.pair(name)
        print(f"{name}:")
        install_one(pair.matlab.path, pair.matlab.repo, config_path, args.uninstall)
        install_one(pair.python.path, pair.python.repo, config_path, args.uninstall)

    if not args.uninstall:
        print("\nThe hooks need the `parity` command on PATH: pip install -e .")
        print("Set PARITY_STRICT=1 to make pre-push refuse a branch that touches parity functions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
