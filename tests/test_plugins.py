"""The plugin marketplace under ``ai/`` is consistent and its hook files are current.

The four code repositories load these plugins from this repository's default
branch, so a stale ``hooks/context.json`` or a plugin missing from
``marketplace.json`` reaches every contributor's session without a local error.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
PLUGIN_DIRS = sorted(p for p in (ROOT / "ai").iterdir() if p.is_dir())
SKILLS = sorted((ROOT / "ai").glob("*/skills/*/SKILL.md"))


def load_marketplace() -> dict:
    return json.loads(MARKETPLACE.read_text(encoding="utf-8"))


def test_hook_files_are_current():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_plugins.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout


def test_marketplace_lists_every_plugin_directory():
    listed = {p["source"]: p["name"] for p in load_marketplace()["plugins"]}
    on_disk = {f"./ai/{d.name}": d.name for d in PLUGIN_DIRS}
    assert listed == on_disk


@pytest.mark.parametrize("plugin", PLUGIN_DIRS, ids=lambda p: p.name)
def test_plugin_manifest_matches_directory(plugin: Path):
    manifest = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == plugin.name
    assert (plugin / "context.md").is_file()


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: f"{p.parts[-4]}:{p.parts[-2]}")
def test_skill_frontmatter(skill: Path):
    text = skill.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md must start with YAML frontmatter"
    meta = yaml.safe_load(match.group(1))
    assert meta["name"] == skill.parent.name
    assert meta.get("description")


def test_no_em_dashes():
    files = [MARKETPLACE, *(p for p in (ROOT / "ai").rglob("*") if p.is_file())]
    offenders = [f.relative_to(ROOT).as_posix() for f in files if "—" in f.read_text(encoding="utf-8")]
    assert not offenders
