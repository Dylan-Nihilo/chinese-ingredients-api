"""Load and validate one immutable catalog snapshot shared by API and exports."""
from __future__ import annotations

import csv
import copy
import hashlib
import io
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from types import MappingProxyType
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = ROOT / "data"
ID_PATTERN = re.compile(r"ing_[0-9]{6}\Z")
KEY_PATTERN = re.compile(r"[a-z][a-z0-9_-]*\Z")
VERSION_PATTERN = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")


class DataError(ValueError):
    """An invalid seed must prevent startup, rather than silently serving it."""


def normalize(value: str) -> str:
    """NFKC/case normalization; dialect and script variants must be explicit aliases."""
    return unicodedata.normalize("NFKC", value).strip().casefold()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DataError(message)


def _keys(value: object, required: set[str], label: str) -> dict:
    _require(isinstance(value, dict), f"{label}: expected object")
    _require(set(value) == required, f"{label}: expected fields {sorted(required)}, got {sorted(value)}")
    return value


def _text(value: object, label: str) -> None:
    _require(isinstance(value, str) and bool(value.strip()) and value == value.strip(), f"{label}: expected nonempty trimmed string")
    _require(not any(unicodedata.category(c).startswith("C") for c in value), f"{label}: control characters are not allowed")


def _date(value: object, label: str) -> None:
    _text(value, label)
    try:
        _require(date.fromisoformat(value).isoformat() == value, f"{label}: expected YYYY-MM-DD")
    except ValueError as exc:
        raise DataError(f"{label}: invalid ISO date") from exc


def _url(value: object, label: str) -> None:
    _text(value, label)
    try:
        parsed = urlparse(value)
        _ = parsed.port  # Triggers validation of malformed/non-numeric ports.
        valid = parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password and not any(c.isspace() for c in value)
    except ValueError as exc:
        raise DataError(f"{label}: malformed HTTPS reference URL") from exc
    _require(valid, f"{label}: expected HTTPS reference URL")


def _list(value: object, label: str, nonempty: bool = False) -> None:
    _require(isinstance(value, list) and (not nonempty or bool(value)), f"{label}: expected {'nonempty ' if nonempty else ''}array")


def validate(ingredients_doc: dict, categories_doc: dict, sources_doc: dict) -> None:
    _keys(ingredients_doc, {"schemaVersion", "datasetVersion", "releasedAt", "license", "scope", "ingredients"}, "dataset")
    _require(ingredients_doc["schemaVersion"] == "1.0.0", "unsupported schemaVersion")
    _require(isinstance(ingredients_doc["datasetVersion"], str) and bool(VERSION_PATTERN.fullmatch(ingredients_doc["datasetVersion"])), "invalid datasetVersion")
    _date(ingredients_doc["releasedAt"], "releasedAt")
    _text(ingredients_doc["license"], "dataset license")
    _keys(ingredients_doc["scope"], {"includes", "excludes"}, "scope")
    for key in ("includes", "excludes"):
        _list(ingredients_doc["scope"][key], f"scope.{key}", True)
        for value in ingredients_doc["scope"][key]:
            _text(value, f"scope.{key}")
    _keys(categories_doc, {"categories"}, "categories document")
    _keys(sources_doc, {"sources"}, "sources document")
    _list(categories_doc["categories"], "categories", True)
    _list(sources_doc["sources"], "sources", True)
    categories, sources = set(), set()
    for item in categories_doc["categories"]:
        _keys(item, {"id", "name", "description"}, "category")
        for field in item:
            _text(item[field], f"category.{field}")
        _require(bool(KEY_PATTERN.fullmatch(item["id"])), "invalid category ID")
        _require(item["id"] not in categories, f"duplicate category: {item['id']}")
        categories.add(item["id"])
    for item in sources_doc["sources"]:
        _keys(item, {"id", "title", "url", "license", "licenseUrl", "licenseNote", "accessedAt"}, "source")
        for field in ("id", "title", "license", "licenseNote"):
            _text(item[field], f"source.{field}")
        _require(bool(KEY_PATTERN.fullmatch(item["id"])), "invalid source ID")
        _url(item["url"], "source.url")
        if item["licenseUrl"] is not None:
            _url(item["licenseUrl"], "source.licenseUrl")
        _date(item["accessedAt"], "source.accessedAt")
        _require(item["id"] not in sources, f"duplicate source: {item['id']}")
        sources.add(item["id"])
    _list(ingredients_doc["ingredients"], "ingredients", True)
    ids, names = set(), set()
    for item in ingredients_doc["ingredients"]:
        _keys(item, {"id", "name", "aliases", "categoryId", "kind", "description", "icon", "sourceRefs"}, "ingredient")
        _require(isinstance(item["id"], str) and bool(ID_PATTERN.fullmatch(item["id"])), "invalid ingredient ID")
        _require(item["id"] not in ids, f"duplicate ingredient ID: {item['id']}")
        ids.add(item["id"])
        _text(item["name"], f"{item['id']}.name")
        name = normalize(item["name"])
        _require(name not in names, f"duplicate canonical name: {item['name']}")
        names.add(name)
        _require(isinstance(item["categoryId"], str) and item["categoryId"] in categories, f"unknown category on {item['id']}")
        _require(item["kind"] == "ingredient", "v1 seed only supports ingredients, not seasonings")
        _require(item["description"] is None, "v1 descriptions are intentionally null, not copied prose")
        _require(item["icon"] is None, "v1 icons are intentionally null; artwork licensing must be reviewed first")
        _list(item["aliases"], f"{item['id']}.aliases")
        aliases = {name}
        for alias in item["aliases"]:
            _keys(alias, {"name", "locale"}, "alias")
            _text(alias["name"], "alias.name")
            _require(isinstance(alias["locale"], str) and alias["locale"] in {"zh-CN", "zh-TW", "zh-HK", "zh"}, "unsupported alias locale")
            normalized = normalize(alias["name"])
            _require(normalized not in aliases, f"duplicate alias on {item['id']}: {alias['name']}")
            aliases.add(normalized)
        _list(item["sourceRefs"], f"{item['id']}.sourceRefs", True)
        covered_fields = set()
        for ref in item["sourceRefs"]:
            _keys(ref, {"sourceId", "url", "accessedAt", "fields", "note"}, "sourceRef")
            _require(isinstance(ref["sourceId"], str) and ref["sourceId"] in sources, f"unknown source on {item['id']}")
            _url(ref["url"], "sourceRef.url")
            _date(ref["accessedAt"], "sourceRef.accessedAt")
            _text(ref["note"], "sourceRef.note")
            _list(ref["fields"], "sourceRef.fields", True)
            _require(all(isinstance(f, str) and f in {"name", "aliases", "categoryId"} for f in ref["fields"]), "unsupported sourced field")
            _require(len(ref["fields"]) == len(set(ref["fields"])), "duplicate sourced field")
            covered_fields.update(ref["fields"])
        _require("name" in covered_fields, f"{item['id']}: name requires provenance")
        _require(not item["aliases"] or "aliases" in covered_fields, f"{item['id']}: aliases require provenance")
    _require([i["id"] for i in ingredients_doc["ingredients"]] == sorted(ids), "ingredients must be ordered by stable ID")


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _load_json(raw: bytes) -> dict:
    def pairs(entries):
        result = {}
        for key, value in entries:
            if key in result:
                raise DataError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs)
    except (ValueError, UnicodeError) as exc:
        raise DataError(f"invalid JSON: {exc}") from exc


class Catalog:
    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR):
        self.raw = {}
        docs = {}
        for filename in ("ingredients.json", "categories.json", "sources.json"):
            try:
                raw = (data_dir / filename).read_bytes()
            except OSError as exc:
                raise DataError(f"cannot read {filename}: {exc}") from exc
            self.raw[filename] = raw
            docs[filename] = _load_json(raw)
        validate(docs["ingredients.json"], docs["categories.json"], docs["sources.json"])
        self.raw = MappingProxyType(self.raw)
        self._document = docs["ingredients.json"]
        self._ingredients = self._document["ingredients"]
        self._categories = docs["categories.json"]["categories"]
        self._sources = docs["sources.json"]["sources"]
        self._by_id = {item["id"]: item for item in self._ingredients}
        self._search_index = [(item, normalize(item["name"]), [normalize(a["name"]) for a in item["aliases"]]) for item in self._ingredients]
        self.version = self._document["datasetVersion"]
        self.checksums = MappingProxyType({name: hashlib.sha256(raw).hexdigest() for name, raw in self.raw.items()})
        # Includes categories and source licensing, not just ingredient rows.
        digest = hashlib.sha256()
        for filename in sorted(self.raw):
            digest.update(filename.encode() + b"\0" + self.raw[filename])
        self.snapshot_hash = digest.hexdigest()

    # Return detached records so in-process consumers cannot mutate the snapshot.
    @property
    def document(self):
        return copy.deepcopy(self._document)

    @property
    def ingredients(self):
        return copy.deepcopy(self._ingredients)

    @property
    def categories(self):
        return copy.deepcopy(self._categories)

    @property
    def sources(self):
        return copy.deepcopy(self._sources)

    @property
    def by_id(self):
        return copy.deepcopy(self._by_id)

    def search(self, q: str = "", category: str | None = None) -> list[dict]:
        query = normalize(q)
        ranked = []
        for item, name, aliases in self._search_index:
            if category and item["categoryId"] != category:
                continue
            if not query:
                rank = 0
            elif query == name:
                rank = 0
            elif query in aliases:
                rank = 1
            elif name.startswith(query):
                rank = 2
            elif any(a.startswith(query) for a in aliases):
                rank = 3
            elif query in name:
                rank = 4
            elif any(query in a for a in aliases):
                rank = 5
            else:
                continue
            ranked.append((rank, item["id"], item))
        return [copy.deepcopy(item) for _, _, item in sorted(ranked, key=lambda row: (row[0], row[1]))]

    def metadata(self) -> dict:
        return {
            "schemaVersion": self.document["schemaVersion"],
            "datasetVersion": self.version,
            "releasedAt": self.document["releasedAt"],
            "license": self.document["license"],
            "scope": self.document["scope"],
            "ingredientCount": len(self.ingredients),
            "categoryCount": len(self.categories),
            "sourceCount": len(self.sources),
            "snapshotSha256": self.snapshot_hash,
            "files": {name: {"sha256": digest, "download": f"/v1/exports/{name}"} for name, digest in self.checksums.items()},
        }

    def csv_bytes(self) -> bytes:
        # Nested arrays remain JSON strings for a lossless CSV round trip.
        # No BOM: machine-readable UTF-8; import as UTF-8 when using a spreadsheet.
        output = io.StringIO(newline="")
        fields = ["id", "name", "aliases", "categoryId", "kind", "description", "icon", "sourceRefs"]
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for item in self.ingredients:
            writer.writerow({key: json.dumps(item[key], ensure_ascii=False, separators=(",", ":")) if key in {"aliases", "sourceRefs", "description", "icon"} else item[key] for key in fields})
        return output.getvalue().encode("utf-8")
