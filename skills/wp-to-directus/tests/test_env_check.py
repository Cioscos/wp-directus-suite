import unittest
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from env_check import load_env, write_env, required_vars_for_mode


class EnvTests(unittest.TestCase):
    def test_required_vars_test_mode(self):
        v = required_vars_for_mode("test")
        self.assertIn("MYSQL_ROOT_PASSWORD", v)
        self.assertIn("WP_DB_HOST", v)
        self.assertIn("DIRECTUS_DB_USER", v)

    def test_required_vars_external_mode(self):
        v = required_vars_for_mode("external")
        self.assertIn("WP_DB_HOST", v)
        self.assertIn("DIRECTUS_URL", v)
        self.assertIn("DIRECTUS_ADMIN_TOKEN", v)
        self.assertNotIn("MYSQL_ROOT_PASSWORD", v)

    def test_roundtrip_write_read(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env"
            write_env(p, {"A": "1", "B": "two three"})
            got = load_env(p)
            self.assertEqual(got["A"], "1")
            self.assertEqual(got["B"], "two three")

    def test_load_preserves_unknown_keys(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text("A=1\n# comment\nB=two\n", encoding="utf-8")
            got = load_env(p)
            self.assertEqual(got, {"A": "1", "B": "two"})


if __name__ == "__main__":
    unittest.main()
