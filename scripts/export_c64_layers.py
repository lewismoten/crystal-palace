#!/usr/bin/env python3
"""Export Crystal-9's original packed tensors as individually pageable C64 PRGs.

No weights are distilled, requantized, or regenerated. Each C9W1 packet holds
verbatim FP16 scale bytes followed by the source INT4 packed bytes. The two-byte
PRG load address places the packet at $C000, a RAM window below I/O space.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

LOAD_ADDRESS = bytes((0x00, 0xC0))
MAGIC = b"C9W1"


def pack_layer(layer_id: int, scales: bytes, packed: bytes) -> bytes:
    if not 0 <= layer_id <= 255:
        raise ValueError("layer id must fit in one byte")
    if len(scales) > 0xFFFF or len(packed) > 0xFFFF:
        raise ValueError("layer payload exceeds C64 packet limit")
    return MAGIC + bytes((layer_id,)) + len(scales).to_bytes(2, "little") + len(packed).to_bytes(2, "little") + scales + packed


def main() -> None:
    import argparse
    import torch

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=Path.home() / "crystal-9/releases/huggingface-int4-v1/artifacts/crystal-9-int4-group2-packed-fp16-scales-v1.pt")
    parser.add_argument("--output", type=Path, default=Path("build/layers"))
    args = parser.parse_args()

    source = args.artifact.read_bytes()
    manifest = torch.load(args.artifact, map_location="cpu", weights_only=True)
    if manifest.get("format") != "crystal-9-packed-int4-fp16-scales-v1" or manifest.get("scale_storage") != "float16":
        raise ValueError("expected the checked Crystal-9 FP16-scale packed INT4 artifact")
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    for layer_id, (name, record) in enumerate(manifest["tensors"].items()):
        # Use PyTorch's byte view rather than Tensor.numpy(): the exporter only
        # needs raw storage bytes, so requiring NumPy adds an unnecessary setup
        # dependency on Linux and macOS.
        scales = bytes(record["scales"].detach().cpu().contiguous().view(torch.uint8).reshape(-1).tolist())
        packed = bytes(record["packed"].detach().cpu().contiguous().view(torch.uint8).reshape(-1).tolist())
        packet = pack_layer(layer_id, scales, packed)
        filename = f"C9W{layer_id:02d}.PRG"
        (args.output / filename).write_bytes(LOAD_ADDRESS + packet)
        records.append({
            "id": layer_id,
            "tensor": name,
            "file": filename,
            "shape": list(record["shape"]),
            "scheme": record["scheme"],
            "group_size": record["group_size"],
            "scale_bytes": len(scales),
            "packed_bytes": len(packed),
            "packet_sha256": hashlib.sha256(packet).hexdigest(),
        })
    package = {
        "format": "cp64-crystal9-layer-package-v1",
        "source_artifact": args.artifact.name,
        "source_artifact_sha256": hashlib.sha256(source).hexdigest(),
        "source_integrity_sha256": manifest["integrity_sha256"],
        "load_address": "$c000",
        "records": records,
    }
    (args.output / "manifest.json").write_text(json.dumps(package, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"layers": len(records), "payload_bytes": sum(item["scale_bytes"] + item["packed_bytes"] for item in records), "source_sha256": package["source_artifact_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
