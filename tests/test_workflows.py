"""Every `run:` block in a workflow has to be valid shell.

Nothing checks a workflow's shell until the job runs, and these jobs run on a
schedule --- so a quoting mistake sits there silently and then costs a whole
night. Not hypothetical: a stray backslash-quote at the end of one line shipped
to both this repo and raven-toolbox, and the first nightly run died on
``unexpected EOF while looking for matching '"'``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


def usable_bash() -> str | None:
    """Return a bash that can actually parse a script, or None.

    On Windows `bash` often resolves to the WSL stub, which exits non-zero with
    "Windows Subsystem for Linux has no installed distributions" no matter what
    it is handed. Checking only that the name resolves turns that into three
    confusing failures about the workflows, which are fine.
    """
    candidate = shutil.which("bash")
    if not candidate:
        return None
    probe = subprocess.run([candidate, "-n"], input=b":\n", capture_output=True)
    return candidate if probe.returncode == 0 else None


BASH = usable_bash()


WORKFLOWS = sorted((Path(__file__).resolve().parents[1] / ".github" / "workflows").glob("*.yml"))


def read(path: Path) -> str:
    """Read with CRLF normalised away.

    Git stores these files with LF, which is what a runner gets. A Windows
    working copy has CRLF, and bash reports a stray carriage return as a syntax
    error --- so without this the check would fail on every developer machine and
    pass in CI, which is the wrong way round.
    """
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def run_blocks(path: Path):
    """Yield (step label, script) for every `run:` in the workflow."""
    document = yaml.safe_load(read(path))
    for job_name, job in (document.get("jobs") or {}).items():
        for index, step in enumerate(job.get("steps") or []):
            script = step.get("run")
            if script:
                yield f"{path.name}:{job_name}:{step.get('name') or index}", script


def strip_expressions(script: str) -> str:
    """Replace ``${{ ... }}`` with a literal, so this checks shell not templating.

    Actions substitutes these before bash sees them. Leaving them in would make
    bash parse ``{{`` as shell; dropping them entirely would let an unquoted
    empty expansion look like valid syntax when it is not.
    """
    lines = []
    for line in script.split("\n"):
        while "${{" in line and "}}" in line:
            head, rest = line.split("${{", 1)
            line = head + "PLACEHOLDER" + rest.split("}}", 1)[1]
        lines.append(line)
    return "\n".join(lines)


def test_the_workflow_directory_was_actually_found():
    """Otherwise every test below passes by having nothing to check."""
    assert WORKFLOWS, "no workflow files found"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_is_valid_yaml(path: Path):
    assert yaml.safe_load(read(path))


@pytest.mark.skipif(BASH is None, reason="no usable bash")
@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_run_block_parses_as_shell(path: Path):
    assert BASH is not None  # skipif guarantees this; mypy does not know that
    for label, script in run_blocks(path):
        # Bytes, not text: in text mode Python translates "\n" to "\r\n" on the
        # way into stdin under Windows, and bash then rejects the carriage
        # returns it just received. That would fail every block on Windows for a
        # reason that has nothing to do with the workflow.
        result = subprocess.run(
            [BASH, "-n"],
            input=strip_expressions(script).encode("utf-8"),
            capture_output=True,
        )
        assert result.returncode == 0, f"{label}\n{result.stderr.decode('utf-8', 'replace')}"
