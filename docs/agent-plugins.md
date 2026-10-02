# Coding agent plugins

This repository is a Claude Code plugin marketplace named `raven-gecko`. It holds the
instructions a coding agent follows in RAVEN, GECKO, raven-toolbox, geckopy and this
repository, so that conventions shared by all five are written once.

## Plugins

| Plugin | Enabled in | Contents |
|---|---|---|
| `common` | all five repositories | Repository map, parity ledger duties, authorship, merging, links, comment and YAML rules. Skills: `pr-text`, `doc-prose`, `parity-ledger`. |
| `raven` | RAVEN | Layout, pure-MATLAB rule, help text format, argument parsing. Skill: `run-tests`. |
| `gecko` | GECKO | Layout, RAVEN dependency, help text format, unit tests. Skill: `run-tests`. |
| `raven-toolbox` | raven-toolbox | Layout, registries, `__all__`, lint, type checks and tests. |
| `geckopy` | geckopy | Layout, flat public API, lint and tests. Skill: `dual-install`. |

Each plugin directory under `ai/` contains:

- `.claude-plugin/plugin.json`: the plugin manifest.
- `context.md`: rules that apply to every session in the target repository.
- `hooks/`: a SessionStart hook that adds `context.md` to the session at startup, after
  `/clear` and after compaction. `scripts/build_plugins.py` generates these files.
- `skills/<name>/SKILL.md`: longer instructions, loaded when the task matches the skill's
  `description` or when invoked as `/<plugin>:<skill>`.

## Editing

1. Edit `context.md` or a `SKILL.md` file.
2. Regenerate the hook files and run the tests:

   ```bash
   python scripts/build_plugins.py
   pytest tests/test_plugins.py
   ```

   `tests/test_plugins.py` fails when a hook file is out of date, when `marketplace.json`
   and the `ai/` directories disagree, when a skill has no `name` or `description`, or when
   a file contains an em dash.
3. Increase `version` in the plugin's `plugin.json`. Installed copies update when the
   version changes.

Keep `context.md` short, because its whole text is part of every session. Put procedures
and reference material in skills.

To try a plugin before it is merged, start a session with the local directory:

```bash
claude --plugin-dir ai/raven --plugin-dir ai/common
```

## Enabling the plugins in a repository

Each target repository commits `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "raven-gecko": {
      "source": {
        "source": "github",
        "repo": "SysBioChalmers/raven-gecko-parity"
      }
    }
  },
  "enabledPlugins": {
    "common@raven-gecko": true,
    "raven@raven-gecko": true
  }
}
```

with the second `enabledPlugins` entry naming that repository's plugin (`raven`, `gecko`,
`raven-toolbox` or `geckopy`). This repository enables `common` only. The marketplace is
read from the default branch, `develop`, so a plugin change reaches the other repositories
when it is merged here.

On the first session in a repository with this file, Claude Code asks the user to trust the
marketplace and install the plugins. A user who declines works without them.
