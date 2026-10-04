"""Platform bootstrap coverage for the local 64tass tool wrapper."""
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_bootstrap_supports_macos_homebrew_tass64_without_apt():
    source = (ROOT / "scripts" / "bootstrap_64tass.sh").read_text()

    assert 'command -v brew' in source
    assert 'brew install tass64' in source
    assert 'command -v 64tass' in source
    assert 'ln -sf' in source
