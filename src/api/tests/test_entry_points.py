"""Every command the container runs must import cleanly in a fresh interpreter.

Tests import app.main first, which hides import cycles that only appear when another module is
loaded first (e.g. `python -m app.content.seed` in docker-compose.yml).
"""

import subprocess
import sys
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("module", ["app.main", "app.content.seed", "app.models", "app.content.schema", "app.engines.story"])
def test_module_imports_on_its_own(module):
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"], cwd=API_DIR, capture_output=True, text=True, timeout=60
    )

    assert result.returncode == 0, result.stderr
