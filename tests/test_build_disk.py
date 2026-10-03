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


def test_current_disk_stage_reports_archive_charset_and_readable_packets():
    builder = load_builder()

    assert builder.CURRENT_STAGE == 78
    assert builder.CURRENT_DESCRIPTION == "archive-charset-and-readable-packets"


def test_disk_tensor_filenames_are_descriptive_but_preserve_packet_identity():
    builder = load_builder()

    assert len(builder.DISK_TENSOR_FILENAMES) == 48
    assert builder.DISK_TENSOR_FILENAMES["C9W00.PRG"] == "EMBEDTOK.PRG"
    assert builder.DISK_TENSOR_FILENAMES["C9W02.PRG"] == "ATTNQKVW.PRG"
    assert builder.DISK_TENSOR_FILENAMES["C9W08.PRG"] == "ROUTERW.PRG"
    assert builder.DISK_TENSOR_FILENAMES["C9W10.PRG"] == "EX0L1W.PRG"
    assert builder.DISK_TENSOR_FILENAMES["C9W47.PRG"] == "OUTHEADB.PRG"
    assert len(set(builder.DISK_TENSOR_FILENAMES.values())) == 48
