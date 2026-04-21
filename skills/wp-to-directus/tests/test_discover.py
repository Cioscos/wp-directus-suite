import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from discover import classify_plugin, CORE_TABLES
from lib.php_serialized import parse_serialized_array


class DiscoverTests(unittest.TestCase):
    def test_core_tables_fixed(self):
        self.assertIn("wp_posts", CORE_TABLES)
        self.assertIn("wp_term_relationships", CORE_TABLES)

    def test_classify_unsupported_known(self):
        self.assertEqual(classify_plugin("yoast-seo/wp-seo.php", []), "unsupported")
        self.assertEqual(classify_plugin("wordfence/wordfence.php", []), "unsupported")

    def test_classify_partial_with_custom_table(self):
        self.assertEqual(
            classify_plugin("my-plugin/my-plugin.php", ["wp_myplugin_data"]),
            "partial",
        )

    def test_classify_migratable_default(self):
        self.assertEqual(classify_plugin("unknown-plugin/main.php", []), "migratable")


class PhpSerializedTests(unittest.TestCase):
    def test_parse_simple_array(self):
        s = 'a:2:{i:0;s:5:"one.php";i:1;s:5:"two.php";}'
        self.assertEqual(parse_serialized_array(s), ["one.php", "two.php"])

    def test_parse_empty(self):
        self.assertEqual(parse_serialized_array("a:0:{}"), [])


if __name__ == "__main__":
    unittest.main()
