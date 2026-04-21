import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from mcp_install import build_mcp_config, merge_mcp, url_encode_password


class McpInstallTests(unittest.TestCase):
    def test_url_encode_special_chars(self):
        self.assertEqual(url_encode_password("p@ss/w:rd"), "p%40ss%2Fw%3Ard")

    def test_build_includes_mysql_always(self):
        env = {
            "WP_DB_HOST": "h", "WP_DB_PORT": "3307", "WP_DB_USER": "u",
            "WP_DB_PASSWORD": "p", "WP_DB_NAME": "d",
        }
        cfg = build_mcp_config(env)
        self.assertIn("wordpress-mysql", cfg["mcpServers"])
        self.assertNotIn("directus-postgres", cfg["mcpServers"])

    def test_build_includes_postgres_when_all_set(self):
        env = {
            "WP_DB_HOST": "h", "WP_DB_PORT": "3307", "WP_DB_USER": "u",
            "WP_DB_PASSWORD": "p", "WP_DB_NAME": "d",
            "DIRECTUS_DB_HOST": "h2", "DIRECTUS_DB_PORT": "5433",
            "DIRECTUS_DB_USER": "r", "DIRECTUS_DB_PASSWORD": "s",
            "DIRECTUS_DB_NAME": "dir",
        }
        cfg = build_mcp_config(env)
        self.assertIn("directus-postgres", cfg["mcpServers"])
        dsn = cfg["mcpServers"]["directus-postgres"]["args"][-1]
        self.assertIn("postgresql://r:s@h2:5433/dir", dsn)

    def test_merge_preserves_existing(self):
        existing = {"mcpServers": {"foo": {"command": "x"}}}
        new = {"mcpServers": {"wordpress-mysql": {"command": "y"}}}
        merged = merge_mcp(existing, new)
        self.assertIn("foo", merged["mcpServers"])
        self.assertIn("wordpress-mysql", merged["mcpServers"])

    def test_merge_overwrites_managed_entries(self):
        existing = {"mcpServers": {"wordpress-mysql": {"command": "old"}}}
        new = {"mcpServers": {"wordpress-mysql": {"command": "new"}}}
        merged = merge_mcp(existing, new)
        self.assertEqual(merged["mcpServers"]["wordpress-mysql"]["command"], "new")


if __name__ == "__main__":
    unittest.main()
