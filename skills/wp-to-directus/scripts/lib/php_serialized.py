"""Minimal PHP-serialized array parser: handles `a:N:{...}` of string items.

Only supports the subset needed to parse `active_plugins` in wp_options.
For richer parsing, store raw in `extra_meta`.
"""

import re
from typing import List


STRING_RE = re.compile(r's:(\d+):"', re.ASCII)


def parse_serialized_array(s: str) -> List[str]:
    """Parse a PHP-serialized array of strings: `a:2:{i:0;s:5:"one";...}`.

    Returns list of string values. Non-string items are skipped.

    Note: the declared length is used as a hint; the actual string content is
    terminated by the closing `";` sequence. This tolerates malformed/mb-byte
    length mismatches (PHP counts bytes, not characters).
    """
    if not s or not s.startswith("a:"):
        return []
    result = []
    pos = s.find("{")
    if pos < 0:
        return []
    pos += 1
    while pos < len(s):
        if s[pos] == "}":
            break
        # skip key (e.g., "i:0;")
        semi = s.find(";", pos)
        if semi < 0:
            break
        pos = semi + 1
        # parse value
        if pos < len(s) and s[pos] == "s":
            m = STRING_RE.match(s, pos)
            if not m:
                break
            start = m.end()
            # Find the terminating `";` — the declared length may not match
            # actual byte count for mb strings or malformed input.
            end = s.find('";', start)
            if end < 0:
                break
            value = s[start:end]
            result.append(value)
            pos = end + 2  # past `";`
        else:
            # unsupported type — skip to next `;`
            semi = s.find(";", pos)
            if semi < 0:
                break
            pos = semi + 1
    return result
