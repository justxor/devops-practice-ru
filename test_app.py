import json
import os
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from app import Handler


class ServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def get(self, path):
        """Вспомогательный метод: делает GET и возвращает (status, body)."""
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=2)
        try:
            conn.request('GET', path)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def test_health(self):
        status, body = self.get('/healthz')
        self.assertEqual(status, 200)
        self.assertEqual(body, {'status': 'ok'})

    def test_unknown_route(self):
        status, body = self.get('/missing')
        self.assertEqual(status, 404)
        self.assertEqual(body, {'error': 'not found'})

    def test_app_version_from_env(self):
        with patch.dict(os.environ, {'APP_VERSION': 'v1.2.3'}):
            status, body = self.get('/')
        self.assertEqual(status, 200)
        self.assertEqual(body, {'service': 'devops-lab', 'version': 'v1.2.3'})

    def test_app_version_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('APP_VERSION', None)
            status, body = self.get('/')
        self.assertEqual(status, 200)
        self.assertEqual(body['version'], 'local')


if __name__ == '__main__':
    unittest.main()
