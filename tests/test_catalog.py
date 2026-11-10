import copy
import csv
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ingredient_api.catalog import Catalog, DataError, DEFAULT_DATA_DIR, normalize, validate
from scripts.export_data import export
from scripts.validate_data import validate_baseline


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()
        self.docs = [json.loads(self.catalog.raw[name]) for name in ('ingredients.json', 'categories.json', 'sources.json')]

    def invalid(self, mutate):
        docs = copy.deepcopy(self.docs)
        mutate(docs)
        with self.assertRaises(DataError):
            validate(*docs)

    def test_public_records_cannot_mutate_snapshot(self):
        before = self.catalog.csv_bytes()
        for records in [self.catalog.ingredients, self.catalog.document["ingredients"], list(self.catalog.by_id.values()), self.catalog.search()]:
            records[0]["name"] = "changed"
            records[0]["aliases"].clear()
        self.catalog.categories[0]["name"] = "changed"
        self.catalog.sources[0]["license"] = "changed"
        self.assertEqual(self.catalog.csv_bytes(), before)
        with self.assertRaises(TypeError):
            self.catalog.raw["ingredients.json"] = b"changed"

    def test_seed_validates(self):
        validate(*self.docs)
        self.assertGreaterEqual(len(self.catalog.ingredients), 1)

    def test_ingredient_only_no_assets_or_prose(self):
        for item in self.catalog.ingredients:
            self.assertEqual(item['kind'], 'ingredient')
            self.assertIsNone(item['icon'])
            self.assertIsNone(item['description'])

    def test_release_has_reviewed_cc0_sources(self):
        self.assertEqual(self.catalog.document['license'], 'CC0-1.0')
        self.assertTrue(all(s['license'] == 'CC0-1.0' for s in self.catalog.sources))
        self.assertTrue(all(ref['sourceId'] == 'wikidata' for i in self.catalog.ingredients for ref in i['sourceRefs']))

    def test_canonical_and_alias_match_same_record(self):
        for item in self.catalog.ingredients:
            self.assertIn(item, self.catalog.search(item['name']))
            for alias in item['aliases']:
                self.assertIn(item, self.catalog.search(alias['name']))

    def test_specific_chinese_alias(self):
        self.assertEqual(self.catalog.search('西红柿')[0]['name'], '番茄')
        self.assertEqual(self.catalog.search('马铃薯')[0]['name'], '土豆')

    def test_normalization(self):
        self.assertEqual(normalize('  ＡＢＣ  '), 'abc')
        self.assertEqual(self.catalog.search('　西红柿 '), self.catalog.search('西红柿'))

    def test_search_partial(self):
        matches = self.catalog.search('瓜')
        self.assertGreater(len(matches), 1)
        self.assertTrue(all('瓜' in i['name'] or any('瓜' in a['name'] for a in i['aliases']) for i in matches))

    def test_empty_search_stable_id_order(self):
        ids = [item['id'] for item in self.catalog.search()]
        self.assertEqual(ids, sorted(ids))

    def test_category_filter(self):
        for category in self.catalog.categories:
            items = self.catalog.search(category=category['id'])
            self.assertTrue(all(i['categoryId'] == category['id'] for i in items))

    def test_no_match(self):
        self.assertEqual(self.catalog.search('这是一个不存在的食材名称'), [])

    def test_missing_field_rejected(self):
        self.invalid(lambda d: d[0]['ingredients'][0].pop('id'))

    def test_extra_field_rejected(self):
        self.invalid(lambda d: d[0]['ingredients'][0].update({'unknown': True}))

    def test_duplicate_id_rejected(self):
        self.invalid(lambda d: d[0]['ingredients'][1].update(id=d[0]['ingredients'][0]['id']))

    def test_duplicate_name_rejected(self):
        self.invalid(lambda d: d[0]['ingredients'][1].update(name=d[0]['ingredients'][0]['name']))

    def test_invalid_id_rejected(self):
        self.invalid(lambda d: d[0]['ingredients'][0].update(id='potato'))

    def test_invalid_category_rejected(self):
        self.invalid(lambda d: d[0]['ingredients'][0].update(categoryId='missing'))

    def test_unknown_source_rejected(self):
        self.invalid(lambda d: d[0]['ingredients'][0]['sourceRefs'][0].update(sourceId='missing'))

    def test_empty_source_list_rejected(self):
        self.invalid(lambda d: d[0]['ingredients'][0].update(sourceRefs=[]))

    def test_insecure_source_url_rejected(self):
        self.invalid(lambda d: d[0]['ingredients'][0]['sourceRefs'][0].update(url='http://example.com'))

    def test_source_credentials_rejected(self):
        self.invalid(lambda d: d[0]['ingredients'][0]['sourceRefs'][0].update(url='https://secret@example.com'))

    def test_malformed_url_rejected_cleanly(self):
        for url in ["https://[", "https://example.com:wrong", "https://example .com"]:
            with self.subTest(url=url):
                self.invalid(lambda d: d[0]["ingredients"][0]["sourceRefs"][0].update(url=url))

    def test_nonstring_locale_rejected_cleanly(self):
        self.invalid(lambda d: d[0]["ingredients"][0]["aliases"][0].update(locale=[]))

    def test_unsourced_alias_rejected(self):
        self.invalid(lambda d: d[0]['ingredients'][0]['sourceRefs'][0].update(fields=['name']))

    def test_unsourced_name_rejected(self):
        self.invalid(lambda d: d[0]['ingredients'][0]['sourceRefs'][0].update(fields=['aliases']))

    def test_duplicate_alias_rejected(self):
        self.invalid(lambda d: d[0]['ingredients'][0]['aliases'].append({'name':d[0]['ingredients'][0]['name'], 'locale':'zh-CN'}))

    def test_unsupported_alias_locale_rejected(self):
        self.invalid(lambda d: d[0]['ingredients'][0]['aliases'][0].update(locale='en'))

    def test_seasoning_rejected(self):
        self.invalid(lambda d: d[0]['ingredients'][0].update(kind='seasoning'))

    def test_bad_date_rejected(self):
        self.invalid(lambda d: d[0].update(releasedAt='2026-02-30'))

    def test_bad_version_rejected(self):
        self.invalid(lambda d: d[0].update(datasetVersion='latest'))

    def test_reordered_ids_rejected(self):
        self.invalid(lambda d: d[0]['ingredients'].reverse())

    def test_duplicate_source_rejected(self):
        self.invalid(lambda d: d[2]['sources'].append(d[2]['sources'][0]))

    def test_duplicate_category_rejected(self):
        self.invalid(lambda d: d[1]['categories'].append(d[1]['categories'][0]))

    def test_snapshot_and_file_checksums(self):
        for name, digest in self.catalog.checksums.items():
            self.assertEqual(digest, hashlib.sha256((DEFAULT_DATA_DIR / name).read_bytes()).hexdigest())
        self.assertEqual(self.catalog.snapshot_hash, Catalog().snapshot_hash)

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            for filename, raw in self.catalog.raw.items():
                Path(folder, filename).write_bytes(raw)
            Path(folder, 'ingredients.json').write_text('{"x":1,"x":2}')
            with self.assertRaisesRegex(DataError, 'duplicate JSON key'):
                Catalog(Path(folder))

    def test_invalid_json_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'ingredients.json').write_bytes(b'\xff')
            with self.assertRaises(DataError):
                Catalog(Path(folder))

    def test_missing_files_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(DataError):
                Catalog(Path(folder))

    def test_csv_lossless_round_trip(self):
        rows = list(csv.DictReader(io.StringIO(self.catalog.csv_bytes().decode('utf-8'))))
        for row in rows:
            for key in ('aliases', 'sourceRefs', 'description', 'icon'):
                row[key] = json.loads(row[key])
        self.assertEqual(rows, self.catalog.ingredients)

    def test_export_deterministic_exact_json(self):
        with tempfile.TemporaryDirectory() as folder:
            first = export(self.catalog, folder)
            second = export(self.catalog, folder)
            self.assertEqual(first, second)
            for name, raw in self.catalog.raw.items():
                self.assertEqual(Path(folder, name).read_bytes(), raw)
            for name, info in first['files'].items():
                content = Path(folder, name).read_bytes()
                self.assertEqual(len(content), info['bytes'])
                self.assertEqual(hashlib.sha256(content).hexdigest(), info['sha256'])

    def test_baseline_current_passes(self):
        validate_baseline(self.catalog, DEFAULT_DATA_DIR / 'ingredients.json')

    def test_baseline_removed_id_fails(self):
        baseline = copy.deepcopy(self.catalog.document)
        baseline['ingredients'][0]['id'] = 'ing_999999'
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, 'baseline.json')
            path.write_text(json.dumps(baseline))
            with self.assertRaises(DataError):
                validate_baseline(self.catalog, path)

    def test_baseline_identity_change_fails(self):
        baseline = copy.deepcopy(self.catalog.document)
        baseline['ingredients'][0]['name'] = '另一个食材'
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, 'baseline.json')
            path.write_text(json.dumps(baseline))
            with self.assertRaises(DataError):
                validate_baseline(self.catalog, path)


if __name__ == '__main__':
    unittest.main()
