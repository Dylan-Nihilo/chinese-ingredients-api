#!/usr/bin/env python3
"""Build deterministic, offline exports from the same validated API snapshot."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingredient_api.catalog import Catalog, DEFAULT_DATA_DIR, _json_bytes


def export(catalog, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    files = {**catalog.raw, "ingredients.csv": catalog.csv_bytes()}
    for name, data in files.items():
        (output / name).write_bytes(data)
    manifest = {"datasetVersion": catalog.version, "snapshotSha256": catalog.snapshot_hash, "files": {name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)} for name, data in sorted(files.items())}}
    (output / "manifest.json").write_bytes(_json_bytes(manifest))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("dist"))
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args()
    manifest = export(Catalog(args.data_dir), args.output)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
