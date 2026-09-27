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

    assert builder.stage_image_path(8, "test-position-embedding") == (
        builder.BUILD / "cs64-008-test-position-embedding.d64"
    )


def test_current_disk_stage_reports_resumable_model_turn_dashboard():
    builder = load_builder()

    assert builder.CURRENT_STAGE == 54
    assert builder.CURRENT_DESCRIPTION == "resumable-model-turns-metered-expert-pages"
