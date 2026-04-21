import json
import os
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from lib.state import StateStore, INITIAL_STATE


class StateStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / ".state.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_creates_initial_when_absent(self):
        s = StateStore(self.path)
        state = s.load()
        self.assertEqual(state["phase"], "init")
        self.assertFalse(state["checkpoints"]["env_validated"])

    def test_save_and_reload_roundtrip(self):
        s = StateStore(self.path)
        state = s.load()
        state["phase"] = "discovery"
        state["checkpoints"]["mcp_installed"] = True
        s.save(state)
        s2 = StateStore(self.path)
        reloaded = s2.load()
        self.assertEqual(reloaded["phase"], "discovery")
        self.assertTrue(reloaded["checkpoints"]["mcp_installed"])

    def test_set_phase_updates_timestamp(self):
        s = StateStore(self.path)
        state = s.load()
        before = state["updated_at"]
        s.set_phase("env_check")
        after = s.load()
        self.assertEqual(after["phase"], "env_check")
        self.assertNotEqual(before, after["updated_at"])

    def test_checkpoint_mark(self):
        s = StateStore(self.path)
        s.load()
        s.mark_checkpoint("env_validated")
        self.assertTrue(s.load()["checkpoints"]["env_validated"])

    def test_append_error(self):
        s = StateStore(self.path)
        s.load()
        s.append_error(phase="migrate", subphase="media", wp_id=42,
                       error="HTTP 404", retries=3)
        errs = s.load()["errors"]
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0]["wp_id"], 42)


if __name__ == "__main__":
    unittest.main()
