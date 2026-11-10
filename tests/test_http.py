import json
import threading
import unittest
from http.client import HTTPConnection
from urllib.parse import urlencode

from ingredient_api.catalog import Catalog, ROOT
from ingredient_api.http import Application, make_server


class ApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog()
        cls.app = Application(cls.catalog)

    def get(self, path):
        response = self.app.handle('GET', path)
        return response.status, json.loads(response.body)

    def test_default_pagination(self):
        status, body = self.get('/v1/ingredients')
        self.assertEqual(status, 200)
        self.assertEqual(body['data'], self.catalog.ingredients[:20])
        self.assertEqual(body['meta']['total'], len(self.catalog.ingredients))

    def test_paginate_all_without_duplicates_or_omissions(self):
        items = []
        offset = 0
        while offset is not None:
            status, body = self.get(f'/v1/ingredients?limit=3&offset={offset}')
            self.assertEqual(status, 200)
            items.extend(body['data'])
            offset = body['meta']['nextOffset']
        self.assertEqual(items, self.catalog.ingredients)

    def test_offset_beyond_end(self):
        status, body = self.get('/v1/ingredients?offset=1000000')
        self.assertEqual(status, 200)
        self.assertEqual(body['data'], [])
        self.assertIsNone(body['meta']['nextOffset'])

    def test_unicode_alias(self):
        status, body = self.get('/v1/ingredients?' + urlencode({'q':'西红柿'}))
        self.assertEqual(status, 200)
        self.assertEqual(body['data'][0]['name'], '番茄')

    def test_combined_category_and_search(self):
        item = self.catalog.ingredients[0]
        status, body = self.get('/v1/ingredients?' + urlencode({'q':item['name'], 'category':item['categoryId']}))
        self.assertEqual(status, 200)
        self.assertIn(item, body['data'])

    def test_detail_is_exact_canonical_record(self):
        for item in self.catalog.ingredients:
            status, body = self.get('/v1/ingredients/' + item['id'])
            self.assertEqual(status, 200)
            self.assertEqual(body['data'], item)

    def test_missing_detail(self):
        self.assertEqual(self.get('/v1/ingredients/ing_999999')[0], 404)

    def test_bad_parameters(self):
        cases = ['limit=0', 'limit=101', 'limit=-1', 'limit=1.5', 'limit=true', 'limit=', 'limit=1000000000000000', 'offset=-1', 'offset=1000001', 'category=missing', 'category=', 'unknown=1', 'limit=1&limit=2', 'q=x&q=y', 'q=%FF', 'q=%ZZ', 'q=%', 'q', 'q=%00', 'q='+'x'*121]
        for query in cases:
            with self.subTest(query=query):
                status, body = self.get('/v1/ingredients?' + query)
                self.assertEqual(status, 400)
                self.assertIn('code', body['error'])

    def test_empty_query_is_all(self):
        self.assertEqual(self.get('/v1/ingredients?q=')[1]['data'], self.catalog.ingredients[:20])

    def test_metadata_counts_and_digest(self):
        status, body = self.get('/v1/meta')
        self.assertEqual(status, 200)
        self.assertEqual(body['ingredientCount'], len(self.catalog.ingredients))
        self.assertEqual(body['snapshotSha256'], self.catalog.snapshot_hash)

    def test_categories_and_sources(self):
        for path, expected in [('/v1/categories', self.catalog.categories), ('/v1/sources', self.catalog.sources)]:
            status, body = self.get(path)
            self.assertEqual(status, 200)
            self.assertEqual(body['data'], expected)

    def test_json_export_exact_source_bytes(self):
        for filename, raw in self.catalog.raw.items():
            response = self.app.handle('GET', '/v1/exports/' + filename)
            self.assertEqual(response.status, 200)
            self.assertEqual(response.body, raw)

    def test_csv_export_matches_offline(self):
        response = self.app.handle('GET', '/v1/exports/ingredients.csv')
        self.assertEqual(response.body, self.catalog.csv_bytes())
        self.assertIn('text/csv', response.content_type)

    def test_no_file_traversal(self):
        for path in ['/v1/exports/../../LICENSE', '/v1/exports/%2e%2e/LICENSE', '/v1/exports/ingredients.json/../sources.json']:
            self.assertEqual(self.app.handle('GET', path).status, 404)

    def test_methods_read_only(self):
        for method in ['POST', 'PUT', 'PATCH', 'DELETE', 'TRACE', 'CONNECT']:
            response = self.app.handle(method, '/v1/ingredients')
            self.assertEqual(response.status, 405)
            self.assertEqual(response.headers['Allow'], 'GET, HEAD, OPTIONS')

    def test_options(self):
        response = self.app.handle('OPTIONS', '/v1/ingredients')
        self.assertEqual(response.status, 204)
        self.assertEqual(response.body, b'')
        self.assertNotIn('Access-Control-Allow-Origin', response.headers)

    def test_etag_conditionals(self):
        response = self.app.handle('GET', '/v1/ingredients')
        etag = response.headers['ETag']
        for header in [etag, '*', 'W/' + etag, '"other", '+etag]:
            result = self.app.handle('GET', '/v1/ingredients', header)
            self.assertEqual(result.status, 304)
            self.assertEqual(result.body, b'')
        self.assertEqual(self.app.handle('GET', '/v1/ingredients', '"wrong"').status, 200)

    def test_etags_change_with_response(self):
        a = self.app.handle('GET', '/v1/ingredients?limit=1')
        b = self.app.handle('GET', '/v1/ingredients?limit=2')
        self.assertNotEqual(a.headers['ETag'], b.headers['ETag'])

    def test_security_and_cache_headers(self):
        for path in ['/v1/ingredients', '/missing']:
            response = self.app.handle('GET', path)
            self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
            self.assertEqual(response.headers['Cache-Control'], 'no-cache')
            self.assertEqual(response.headers['X-Dataset-Version'], self.catalog.version)

    def test_misc_routes(self):
        for path in ['/', '/healthz', '/docs', '/openapi.json']:
            self.assertEqual(self.app.handle('GET', path).status, 200)

    def test_unknown_route(self):
        self.assertEqual(self.get('/missing')[0], 404)

    def test_unexpected_query_on_other_routes(self):
        for path in ['/healthz', '/v1/meta', '/docs', '/v1/ingredients/ing_000001']:
            self.assertEqual(self.app.handle('GET', path+'?q=x').status, 400)

    def test_large_target(self):
        self.assertEqual(self.app.handle('GET', '/'+'x'*4096).status, 414)

    def test_absolute_url_rejected(self):
        self.assertEqual(self.app.handle('GET', 'https://example.com/v1/ingredients').status, 400)

    def test_openapi_internal_references_resolve(self):
        document = json.loads((ROOT/'openapi.json').read_bytes())
        operation_ids = []
        def walk(value):
            if isinstance(value, dict):
                if '$ref' in value:
                    self.assertTrue(value['$ref'].startswith('#/'))
                    current = document
                    for part in value['$ref'][2:].split('/'):
                        current = current[part]
                if 'operationId' in value:
                    operation_ids.append(value['operationId'])
                for child in value.values(): walk(child)
            elif isinstance(value, list):
                for child in value: walk(child)
        walk(document)
        self.assertEqual(len(operation_ids), len(set(operation_ids)))
        self.assertEqual(document['openapi'], '3.1.0')


class RealHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server('127.0.0.1', 0, Application(Catalog()))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def request(self, method, path, headers=None):
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_get_over_real_socket(self):
        status, headers, body = self.request('GET', '/v1/ingredients?q=%E8%A5%BF%E7%BA%A2%E6%9F%BF')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['data'][0]['name'], '番茄')
        self.assertEqual(int(headers['Content-Length']), len(body))
        self.assertIn('charset=utf-8', headers['Content-Type'])

    def test_head_headers_without_body(self):
        status, get_headers, body = self.request('GET', '/v1/ingredients')
        status, head_headers, empty = self.request('HEAD', '/v1/ingredients')
        self.assertEqual(status, 200)
        self.assertEqual(empty, b'')
        self.assertEqual(head_headers['Content-Length'], str(len(body)))
        self.assertEqual(head_headers['ETag'], get_headers['ETag'])

    def test_304_no_body(self):
        _, headers, _ = self.request('GET', '/v1/meta')
        status, headers, body = self.request('GET', '/v1/meta', {'If-None-Match':headers['ETag']})
        self.assertEqual(status, 304)
        self.assertEqual(body, b'')
        self.assertNotIn('Content-Length', headers)

    def test_method_not_allowed(self):
        status, headers, body = self.request('POST', '/v1/ingredients')
        self.assertEqual(status, 405)
        self.assertEqual(headers['Allow'], 'GET, HEAD, OPTIONS')
        self.assertEqual(json.loads(body)['error']['code'], 'method_not_allowed')

    def test_options_no_body(self):
        status, headers, body = self.request('OPTIONS', '/v1/ingredients')
        self.assertEqual(status, 204)
        self.assertEqual(body, b'')

    def test_download_content_disposition(self):
        status, headers, body = self.request('GET', '/v1/exports/ingredients.json')
        self.assertEqual(status, 200)
        self.assertIn('attachment', headers['Content-Disposition'])
        self.assertEqual(body, (ROOT/'data'/'ingredients.json').read_bytes())

    def test_unknown_head_has_no_body(self):
        status, headers, body = self.request('HEAD', '/missing')
        self.assertEqual(status, 404)
        self.assertEqual(body, b'')


if __name__ == '__main__':
    unittest.main()
