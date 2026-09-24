import importlib.util
import sys
from pathlib import Path


def load_builder():
    scripts = Path(__file__).parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    path = scripts / "build_disk.py"
    spec = importlib.util.spec_from_file_location("build_disk", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stage_image_path_uses_zero_padded_sequence_and_description():
    builder = load_builder()

    assert builder.stage_image_path(7, "test-token-embedding") == (
        builder.BUILD / "cs64-007-test-token-embedding.d64"
    )
