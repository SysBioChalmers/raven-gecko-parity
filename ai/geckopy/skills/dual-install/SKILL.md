---
name: dual-install
description: Install local checkouts of geckopy and raven-toolbox together so tests run against both working copies. Use when a change touches both packages, or when local test results disagree with CI.
---

# Installing geckopy and raven-toolbox together

geckopy declares raven-toolbox as a dependency. `pip install -e .` in a geckopy checkout
resolves that dependency, and in an environment shared by several checkouts it can replace
an existing editable raven-toolbox install with a regular one. Tests then import a
raven-toolbox that is not the working copy under edit, and local results stop matching CI.

1. Install geckopy first, then raven-toolbox. The later install takes precedence:

   ```bash
   pip install -e "<geckopy-checkout>[dev]"
   pip install -e "<raven-toolbox-checkout>[dev]"
   ```

2. Before trusting a test result, confirm which files Python imports:

   ```bash
   python -c "import geckopy, raven_toolbox; print(geckopy.__file__); print(raven_toolbox.__file__)"
   ```

   Both paths must point into the intended checkouts, not into `site-packages` or another
   worktree.
3. After any later `pip install -e .` in geckopy, install raven-toolbox again and repeat the
   check.

A separate virtual environment per task avoids the problem.
