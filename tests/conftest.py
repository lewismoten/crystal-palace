"""Build transient C64 binary planes from the committed PNG sources for tests."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).parents[1]


def pytest_sessionstart(session):
    subprocess.run([sys.executable, str(ROOT / "scripts" / "compile_c64_assets.py")], check=True)
