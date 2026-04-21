"""Detect WordPress form plugins from rendered markup."""

from __future__ import annotations

from dataclasses import dataclass, field

from bs4 import BeautifulSoup

PLUGIN_SIGNATURES: dict[str, str] = {
    "contact-form-7": "form.wpcf7-form",
    "wpforms": ".wpforms-container form",
    "gravity-forms": ".gform_wrapper form",
    "ninja-forms": ".nf-form-cont form",
}


@dataclass
class FormMatch:
    plugin: str
    fields: list[str] = field(default_factory=list)
    action: str | None = None


class FormPluginMapper:
    def detect(self, html: str) -> list[FormMatch]:
        """Detect WP form plugins from rendered markup.

        Returns one FormMatch per form element. If a form matches multiple
        plugin signatures, the first plugin in PLUGIN_SIGNATURES wins.
        """
        soup = BeautifulSoup(html, "html.parser")
        matches: list[FormMatch] = []
        seen_forms: set[int] = set()
        for plugin, selector in PLUGIN_SIGNATURES.items():
            for form in soup.select(selector):
                form_id = id(form)
                if form_id in seen_forms:
                    continue
                seen_forms.add(form_id)
                fields: list[str] = []
                for inp in form.find_all(["input", "textarea", "select"]):
                    name = inp.get("name")
                    if isinstance(name, list):
                        name = name[0] if name else None
                    if isinstance(name, str) and name:
                        fields.append(name)
                action_raw = form.get("action")
                if isinstance(action_raw, list):
                    action_raw = action_raw[0] if action_raw else None
                action: str | None = action_raw if isinstance(action_raw, str) else None
                matches.append(FormMatch(plugin=plugin, fields=fields, action=action))
        return matches
