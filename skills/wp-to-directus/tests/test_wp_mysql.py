import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from lib.wp_mysql import MySQLClient


class MySQLClientTests(unittest.TestCase):
    def setUp(self):
        self.client = MySQLClient(
            host="localhost", port=3307,
            user="wp", password="pw", database="wp",
        )

    @patch("subprocess.run")
    def test_query_returns_rows_split_by_tab(self, m_run):
        m_run.return_value = MagicMock(
            returncode=0,
            stdout=b"1\tfoo\n2\tbar\n",
            stderr=b"",
        )
        rows = self.client.query("SELECT id, name FROM t")
        self.assertEqual(rows, [["1", "foo"], ["2", "bar"]])

    @patch("subprocess.run")
    def test_query_json_decodes(self, m_run):
        m_run.return_value = MagicMock(
            returncode=0,
            stdout=b'{"c":"hello\\nworld"}\n',
            stderr=b"",
        )
        obj = self.client.query_json("SELECT JSON_OBJECT('c', x) FROM t LIMIT 1")
        self.assertEqual(obj["c"], "hello\nworld")

    @patch("subprocess.run")
    def test_query_uses_batch_raw_flags(self, m_run):
        m_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        self.client.query("SELECT 1")
        args = m_run.call_args[0][0]
        self.assertIn("--batch", args)
        self.assertIn("--raw", args)
        self.assertIn("--skip-column-names", args)

    @patch("subprocess.run")
    def test_password_passed_via_env_not_argv(self, m_run):
        """Password must go through MYSQL_PWD env var, never on the cmdline."""
        m_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")

        # Direct (non-docker) mode
        self.client.query("SELECT 1")
        args = m_run.call_args[0][0]
        kwargs = m_run.call_args[1]

        # No -p<password> token anywhere in argv
        self.assertNotIn("-ppw", args)
        for tok in args:
            self.assertFalse(
                tok.startswith("-p") and len(tok) > 2,
                f"password leaked in argv token: {tok!r}",
            )

        # env kwarg was passed and contains MYSQL_PWD
        self.assertIn("env", kwargs)
        self.assertEqual(kwargs["env"].get("MYSQL_PWD"), "pw")

        # Docker mode: password must be forwarded INTO the container via `-e`
        m_run.reset_mock()
        docker_client = MySQLClient(
            host="localhost", port=3307,
            user="wp", password="pw", database="wp",
            docker_service="wordpress-db",
        )
        docker_client.query("SELECT 1")
        dargs = m_run.call_args[0][0]
        dkwargs = m_run.call_args[1]

        # Still no `-p<password>` style token
        for tok in dargs:
            self.assertFalse(
                tok.startswith("-p") and len(tok) > 2,
                f"password leaked in argv token: {tok!r}",
            )
        # `-e MYSQL_PWD=pw` must be present so the container sees it
        self.assertIn("-e", dargs)
        self.assertIn("MYSQL_PWD=pw", dargs)
        # And the host env still carries it too
        self.assertEqual(dkwargs["env"].get("MYSQL_PWD"), "pw")

    @patch("subprocess.run")
    def test_query_json_raises_on_invalid_json(self, m_run):
        """Non-JSON stdout must raise, not be silently swallowed."""
        m_run.return_value = MagicMock(
            returncode=0,
            stdout=b"not json at all {]",
            stderr=b"",
        )
        with self.assertRaises(RuntimeError) as ctx:
            self.client.query_json("SELECT JSON_OBJECT('c', x) FROM t LIMIT 1")
        self.assertIn("query_json", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
