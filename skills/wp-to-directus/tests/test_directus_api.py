import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from lib.directus_api import DirectusClient


class FakeResponse:
    def __init__(self, code, body):
        self.code = code
        self._body = body.encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self): return self
    def __exit__(self, *a): return False


class DirectusClientTests(unittest.TestCase):
    def setUp(self):
        self.c = DirectusClient("http://d", "tok")

    @patch("lib.directus_api.urlopen")
    def test_get_returns_data(self, m_open):
        m_open.return_value = FakeResponse(200, '{"data":[{"id":1}]}')
        got = self.c.get("/items/x")
        self.assertEqual(got, [{"id": 1}])

    @patch("lib.directus_api.urlopen")
    def test_post_sends_body_with_auth(self, m_open):
        m_open.return_value = FakeResponse(200, '{"data":{"id":9}}')
        got = self.c.post("/items/x", {"a": 1})
        self.assertEqual(got, {"id": 9})
        req = m_open.call_args[0][0]
        self.assertEqual(req.get_header("Authorization"), "Bearer tok")
        self.assertEqual(json.loads(req.data.decode()), {"a": 1})

    @patch("lib.directus_api.urlopen")
    def test_ping_true_when_pong(self, m_open):
        m_open.return_value = FakeResponse(200, "pong")
        self.assertTrue(self.c.ping())

    @patch("lib.directus_api.urlopen")
    def test_exists_by_wp_id(self, m_open):
        m_open.return_value = FakeResponse(200, '{"data":[{"id":42}]}')
        self.assertEqual(self.c.find_by_wp_id("posts", 7), 42)


if __name__ == "__main__":
    unittest.main()
