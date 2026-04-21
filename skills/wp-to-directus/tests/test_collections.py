import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from lib.collections import (
    authors_def, categories_def, tags_def, posts_def, pages_def,
    junction_def, custom_post_type_def, custom_taxonomy_def,
)


class CollectionDefTests(unittest.TestCase):
    def test_authors_has_wp_original_id(self):
        d = authors_def()
        fields = [f["field"] for f in d["fields"]]
        self.assertIn("wp_original_id", fields)
        self.assertIn("email", fields)

    def test_posts_has_content_and_author_m2o(self):
        d = posts_def()
        fields = {f["field"]: f for f in d["fields"]}
        self.assertEqual(fields["content"]["type"], "text")
        self.assertIn("m2o", fields["author"]["meta"].get("special", []))

    def test_junction_has_two_fks(self):
        d = junction_def("posts", "categories")
        self.assertEqual(d["collection"], "posts_categories")
        fields = {f["field"]: f for f in d["fields"]}
        self.assertIn("posts_id", fields)
        self.assertIn("categories_id", fields)

    def test_custom_post_type_slug_snake(self):
        d = custom_post_type_def("product")
        self.assertEqual(d["collection"], "products")

    def test_custom_taxonomy_slug(self):
        d = custom_taxonomy_def("product_cat")
        self.assertEqual(d["collection"], "product_cats")


if __name__ == "__main__":
    unittest.main()
