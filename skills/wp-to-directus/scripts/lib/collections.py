"""Directus collection schema definitions. Each factory returns the
full JSON body accepted by `POST /collections`.
"""


def _id_field():
    return {
        "field": "id", "type": "integer",
        "meta": {"hidden": True, "readonly": True, "interface": "input", "special": None},
        "schema": {"is_primary_key": True, "has_auto_increment": True},
    }


def _wp_id_field():
    return {
        "field": "wp_original_id", "type": "integer",
        "meta": {"interface": "input", "note": "Original WordPress ID"},
        "schema": {},
    }


def authors_def():
    return {
        "collection": "authors",
        "meta": {"icon": "person", "note": "Migrated from WordPress wp_users"},
        "schema": {},
        "fields": [
            _id_field(),
            {"field": "name", "type": "string",
             "meta": {"interface": "input"}, "schema": {"max_length": 255}},
            {"field": "email", "type": "string",
             "meta": {"interface": "input"}, "schema": {"max_length": 255}},
            {"field": "slug", "type": "string",
             "meta": {"interface": "input"}, "schema": {"max_length": 255}},
            _wp_id_field(),
        ],
    }


def categories_def():
    return {
        "collection": "categories",
        "meta": {"icon": "folder"},
        "schema": {},
        "fields": [
            _id_field(),
            {"field": "name", "type": "string",
             "meta": {"interface": "input"}, "schema": {"max_length": 255}},
            {"field": "slug", "type": "string",
             "meta": {"interface": "input"}, "schema": {"max_length": 255}},
            {"field": "description", "type": "text",
             "meta": {"interface": "input-multiline"}, "schema": {}},
            _wp_id_field(),
        ],
    }


def tags_def():
    return {
        "collection": "tags",
        "meta": {"icon": "label"},
        "schema": {},
        "fields": [
            _id_field(),
            {"field": "name", "type": "string",
             "meta": {"interface": "input"}, "schema": {"max_length": 255}},
            {"field": "slug", "type": "string",
             "meta": {"interface": "input"}, "schema": {"max_length": 255}},
            _wp_id_field(),
        ],
    }


def posts_def():
    return {
        "collection": "posts",
        "meta": {"icon": "article"},
        "schema": {},
        "fields": [
            _id_field(),
            {"field": "title", "type": "string",
             "meta": {"interface": "input"}, "schema": {"max_length": 500}},
            {"field": "slug", "type": "string",
             "meta": {"interface": "input"}, "schema": {"max_length": 500}},
            {"field": "content", "type": "text",
             "meta": {"interface": "input-rich-text-html"}, "schema": {}},
            {"field": "excerpt", "type": "text",
             "meta": {"interface": "input-multiline"}, "schema": {}},
            {"field": "status", "type": "string",
             "meta": {"interface": "select-dropdown",
                      "options": {"choices": [
                          {"text": "Published", "value": "published"},
                          {"text": "Draft", "value": "draft"},
                          {"text": "Archived", "value": "archived"}]}},
             "schema": {"max_length": 50, "default_value": "draft"}},
            {"field": "published_date", "type": "timestamp",
             "meta": {"interface": "datetime"}, "schema": {}},
            {"field": "modified_date", "type": "timestamp",
             "meta": {"interface": "datetime"}, "schema": {}},
            {"field": "author", "type": "integer",
             "meta": {"interface": "select-dropdown-m2o", "special": ["m2o"]},
             "schema": {"foreign_key_table": "authors", "foreign_key_column": "id"}},
            {"field": "featured_image", "type": "uuid",
             "meta": {"interface": "file-image", "special": ["file"]}, "schema": {}},
            {"field": "extra_meta", "type": "json",
             "meta": {"interface": "input-code",
                      "options": {"language": "json"}}, "schema": {}},
            _wp_id_field(),
        ],
    }


def pages_def():
    return {
        "collection": "pages",
        "meta": {"icon": "description"},
        "schema": {},
        "fields": [
            _id_field(),
            {"field": "title", "type": "string",
             "meta": {"interface": "input"}, "schema": {"max_length": 500}},
            {"field": "slug", "type": "string",
             "meta": {"interface": "input"}, "schema": {"max_length": 500}},
            {"field": "content", "type": "text",
             "meta": {"interface": "input-rich-text-html"}, "schema": {}},
            {"field": "status", "type": "string",
             "meta": {"interface": "select-dropdown",
                      "options": {"choices": [
                          {"text": "Published", "value": "published"},
                          {"text": "Draft", "value": "draft"}]}},
             "schema": {"max_length": 50, "default_value": "draft"}},
            {"field": "published_date", "type": "timestamp",
             "meta": {"interface": "datetime"}, "schema": {}},
            {"field": "author", "type": "integer",
             "meta": {"interface": "select-dropdown-m2o", "special": ["m2o"]},
             "schema": {"foreign_key_table": "authors", "foreign_key_column": "id"}},
            {"field": "parent_page", "type": "integer",
             "meta": {"interface": "select-dropdown-m2o", "special": ["m2o"]},
             "schema": {"foreign_key_table": "pages", "foreign_key_column": "id"}},
            {"field": "menu_order", "type": "integer",
             "meta": {"interface": "input"}, "schema": {"default_value": 0}},
            _wp_id_field(),
        ],
    }


def junction_def(parent: str, related: str):
    return {
        "collection": f"{parent}_{related}",
        "meta": {"icon": "import_export", "hidden": True},
        "schema": {},
        "fields": [
            _id_field(),
            {"field": f"{parent}_id", "type": "integer",
             "meta": {"hidden": True},
             "schema": {"foreign_key_table": parent, "foreign_key_column": "id"}},
            {"field": f"{related}_id", "type": "integer",
             "meta": {"hidden": True},
             "schema": {"foreign_key_table": related, "foreign_key_column": "id"}},
        ],
    }


def custom_post_type_def(post_type: str):
    return {
        "collection": _pluralize(post_type),
        "meta": {"icon": "category",
                 "note": f"Migrated from WordPress custom post_type '{post_type}'"},
        "schema": {},
        "fields": [
            _id_field(),
            {"field": "title", "type": "string",
             "meta": {"interface": "input"}, "schema": {"max_length": 500}},
            {"field": "slug", "type": "string",
             "meta": {"interface": "input"}, "schema": {"max_length": 500}},
            {"field": "content", "type": "text",
             "meta": {"interface": "input-rich-text-html"}, "schema": {}},
            {"field": "status", "type": "string",
             "meta": {"interface": "select-dropdown"}, "schema": {"max_length": 50}},
            {"field": "published_date", "type": "timestamp",
             "meta": {"interface": "datetime"}, "schema": {}},
            {"field": "author", "type": "integer",
             "meta": {"interface": "select-dropdown-m2o", "special": ["m2o"]},
             "schema": {"foreign_key_table": "authors", "foreign_key_column": "id"}},
            {"field": "extra_meta", "type": "json",
             "meta": {"interface": "input-code"}, "schema": {}},
            _wp_id_field(),
        ],
    }


def custom_taxonomy_def(taxonomy: str):
    return {
        "collection": _pluralize(taxonomy),
        "meta": {"icon": "local_offer",
                 "note": f"Migrated from WordPress custom taxonomy '{taxonomy}'"},
        "schema": {},
        "fields": [
            _id_field(),
            {"field": "name", "type": "string",
             "meta": {"interface": "input"}, "schema": {"max_length": 255}},
            {"field": "slug", "type": "string",
             "meta": {"interface": "input"}, "schema": {"max_length": 255}},
            _wp_id_field(),
        ],
    }


def _pluralize(name: str) -> str:
    n = name.lower().strip()
    if n.endswith("s"):
        return n
    if n.endswith("y"):
        return n[:-1] + "ies"
    return n + "s"
