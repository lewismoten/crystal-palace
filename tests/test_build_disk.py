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


def test_release_image_path_is_a_stable_user_facing_d64_name():
    builder = load_builder()

    assert builder.RELEASE_IMAGE == builder.ROOT / "release" / "crystal-palace-9.d64"


def test_current_disk_stage_reports_title_input_and_runtime_plane_recovery():
    builder = load_builder()

    assert builder.CURRENT_STAGE == 86
    assert builder.CURRENT_DESCRIPTION == "browser-verified-title-radar-blackout"


def test_disk_tensor_filenames_are_descriptive_but_preserve_packet_identity():
    builder = load_builder()

    assert len(builder.DISK_TENSOR_FILENAMES) == 48
    assert builder.DISK_TENSOR_FILENAMES["C9W00.PRG"] == "EMBEDTOK.PRG"
    assert builder.DISK_TENSOR_FILENAMES["C9W02.PRG"] == "ATTNQKVW.PRG"
    assert builder.DISK_TENSOR_FILENAMES["C9W08.PRG"] == "ROUTERW.PRG"
    assert builder.DISK_TENSOR_FILENAMES["C9W10.PRG"] == "EX0L1W.PRG"
    assert builder.DISK_TENSOR_FILENAMES["C9W47.PRG"] == "OUTHEADB.PRG"
    assert len(set(builder.DISK_TENSOR_FILENAMES.values())) == 48


def test_missing_model_packet_directory_builds_a_presentation_preview(tmp_path):
    builder = load_builder()

    assert builder.model_packet_files(tmp_path / "layers") == {}


def test_partial_model_packet_directory_is_rejected(tmp_path):
    builder = load_builder()
    layers = tmp_path / "layers"
    layers.mkdir()
    (layers / "C9W00.PRG").write_bytes(b"incomplete")

    try:
        builder.model_packet_files(layers)
    except SystemExit as error:
        assert "exactly the 48" in str(error)
    else:
        raise AssertionError("a partial original-model packet set must not build")
