#!/usr/bin/env python3
"""Validate the seed and (optionally) a previous ingredients.json release."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingredient_api.catalog import Catalog, DataError, DEFAULT_DATA_DIR, normalize


def validate_baseline(catalog, baseline):
    old = json.loads(Path(baseline).read_text(encoding="utf-8"))
    for previous in old["ingredients"]:
        current = catalog.by_id.get(previous["id"])
        if current is None:
            raise DataError(f"Stable ID removed: {previous['id']}. Keep IDs; design a deprecation migration first.")
        labels = {normalize(current["name"]), *(normalize(a["name"]) for a in current["aliases"])}
        if normalize(previous["name"]) not in labels:
            raise DataError(f"Possible ID reuse/rename: {previous['id']}. Preserve the old name as a sourced alias or review the migration.")
        for item in catalog.ingredients:
            if item["id"] != previous["id"] and normalize(item["name"]) == normalize(previous["name"]):
                raise DataError(f"Canonical name moved to a different ID: {previous['name']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--baseline", type=Path, help="Previous release ingredients.json; detects deleted/reassigned identities")
    args = parser.parse_args()
    try:
        catalog = Catalog(args.data_dir)
        if args.baseline:
            validate_baseline(catalog, args.baseline)
    except (DataError, OSError, ValueError, KeyError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"VALID: {len(catalog.ingredients)} ingredients; {len(catalog.categories)} categories; dataset {catalog.version}")
    print(f"Snapshot SHA-256: {catalog.snapshot_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
