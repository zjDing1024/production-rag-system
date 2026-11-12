import http.client
import json
from pathlib import Path
import threading
import unittest

from rag_foundation.service import RetrievalService, make_server, expand

ROOT = Path(__file__).resolve().parents[1]


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = RetrievalService(ROOT)
        cls.server = make_server(cls.service, 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method='POST', path='/retrieve', body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        conn.request(method, path, body, headers or {'Content-Type': 'application/json'})
        response = conn.getresponse()
        result = response.status, json.loads(response.read())
        conn.close()
        return result

    def test_health_socket(self):
        status, body = self.request('GET', '/health')
        self.assertEqual(status, 200)
        self.assertEqual(body['chunks'], 91)

    def test_retrieve_socket(self):
        status, result = self.request(body=json.dumps({'query': '测试客户端 真实服务器', 'k': 3}))
        self.assertEqual(status, 200)
        self.assertIsNone(result['answer'])
        self.assertEqual(result['answerability'], 'unverified')
        self.assertEqual(len(result['results']), 3)
        self.assertTrue(all(h['citation'] for h in result['results']))
        self.assertEqual(result['effective_query'].split(), ['test', 'client', 'live', 'server'])

    def test_expand_longest_first(self):
        self.assertEqual(expand('真实服务器')[0].split(), ['live', 'server'])
        self.assertTrue(self.service.retrieve({'query': '测试客户端需要服务器吗'})['untranslated_cjk'])

    def test_gate_no_vocabulary(self):
        result = self.service.retrieve({'query': 'zqxv blorptastic neutrinoquux'})
        self.assertEqual(result['status'], 'abstained')
        self.assertEqual(result['results'], [])

    def test_gate_is_not_answerability(self):
        # Entire vocabulary exists; corpus cannot establish this personal fact.
        result = self.service.retrieve({'query': 'What is my secret key?'})
        self.assertEqual(result['status'], 'candidates')
        self.assertIsNone(result['answer'])

    def test_invalid_inputs(self):
        for payload in [None, [], {}, {'query': ''}, {'query': 4}, {'query': 'a'*1001},
                        {'query': 'x', 'k': True}, {'query': 'x', 'k': 0},
                        {'query': 'x', 'k': 11}, {'query': 'x', 'k': 1.2},
                        {'query': 'x', 'gate': 1}, {'query': 'x', 'expand_zh': 'yes'},
                        {'query': 'x', 'url': 'http://example.org'}]:
            with self.subTest(payload=payload):
                status, _ = self.request(body=json.dumps(payload))
                self.assertEqual(status, 400)

    def test_malformed_json(self):
        self.assertEqual(self.request(body=b'{bad')[0], 400)
        self.assertEqual(self.request(body=b'\xff')[0], 400)

    def test_body_limit(self):
        self.assertEqual(self.request(body='x'*8193)[0], 413)

    def test_media_type(self):
        self.assertEqual(self.request(body='{}', headers={'Content-Type': 'text/plain'})[0], 415)

    def test_not_found(self):
        self.assertEqual(self.request('GET', '/etc/passwd')[0], 404)
        self.assertEqual(self.request(path='/other', body='{}')[0], 404)

    def test_repeatable(self):
        a = self.service.retrieve({'query': 'logging'})
        self.assertEqual(a, self.service.retrieve({'query': 'logging'}))


if __name__ == '__main__':
    unittest.main()
