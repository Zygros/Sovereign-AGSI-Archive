"""The Nexus broker stays fail-closed when NEXUS_SECRET is absent.

The broker tests themselves skip in that case. This check runs in a clean
interpreter so a missing secret is still an error, not a passing import.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")


def test_nexus_broker_import_requires_secret():
    env = os.environ.copy()
    env.pop("NEXUS_SECRET", None)
    root = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (root, env.get("PYTHONPATH", "")) if part
    )

    completed = subprocess.run(
        [sys.executable, "-c", "import phoenix_nexus.nexus_broker"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "NEXUS_SECRET" in completed.stderr
