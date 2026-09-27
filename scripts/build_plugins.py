"""Generate the SessionStart hook files for every plugin under ``ai/``.

Each plugin keeps its always-on instructions in ``ai/<plugin>/context.md``. A
SessionStart hook injects that text into the session, but only as the
``additionalContext`` field of a JSON object on stdout, and the hook command
has to run on Windows, macOS and Linux without Python or Node being installed.
So this script writes the JSON once, to ``hooks/context.json``, and the hook
command prints that file with ``cat``.

    python scripts/build_plugins.py          # regenerate
    python scripts/build_plugins.py --check  # exit 1 if any file is out of date
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "ai"

# startup, /clear and compaction all start from a context without the text;
# a resumed session still has it.
MATCHER = "startup|clear|compact"


def hooks_json() -> str:
    config = {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": MATCHER,
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'cat "${CLAUDE_PLUGIN_ROOT}/hooks/context.json"',
                        }
                    ],
                }
            ]
        }
    }
    return json.dumps(config, indent=2) + "\n"


def context_json(context_md: Path) -> str:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context_md.read_text(encoding="utf-8"),
        }
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def expected_files() -> dict[Path, str]:
    files: dict[Path, str] = {}
    for context_md in sorted(PLUGINS.glob("*/context.md")):
        hooks = context_md.parent / "hooks"
        files[hooks / "hooks.json"] = hooks_json()
        files[hooks / "context.json"] = context_json(context_md)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report stale files instead of writing")
    args = parser.parse_args(argv)

    stale = []
    for path, content in expected_files().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            continue
        stale.append(path.relative_to(ROOT).as_posix())
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")

    if args.check and stale:
        print("out of date (run python scripts/build_plugins.py):", *stale, sep="\n  ")
        return 1
    for name in stale:
        print(f"wrote {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
