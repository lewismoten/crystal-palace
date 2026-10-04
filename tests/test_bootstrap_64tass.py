"""Platform bootstrap coverage for the local 64tass tool wrapper."""
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_bootstrap_supports_macos_homebrew_tass64_without_apt():
    source = (ROOT / "scripts" / "bootstrap_64tass.sh").read_text()

    assert 'command -v brew' in source
    assert 'brew install tass64' in source
    assert 'command -v 64tass' in source
    assert 'ln -sf' in source


def test_full_bootstrap_installs_build_dependencies_and_exact_model_packets():
    source = (ROOT / "scripts" / "bootstrap.sh").read_text()

    assert 'pip install -r "$root/requirements-dev.txt"' in source
    assert 'scripts/bootstrap_64tass.sh' in source
    assert 'https://github.com/lewismoten/crystal-9/releases/download/v1.0.0/' in source
    assert 'crystal-9-int4-group2-packed-fp16-scales-v1.pt' in source
    assert '63eee663a143ee478308144da406873c72c05b6d5226dbb2f5e329dacb1392eb' in source
    assert 'scripts/export_c64_layers.py' in source
