#!/usr/bin/env python3
"""
Build "Email Sorter.html" -- the no-install version that runs in any browser.

It combines web/app.html, web/sorter_core.js and the sorting rules from
categories.py and replies.py into one self-contained file. Re-run this after
changing any of those:

    python3 build_web.py
"""

import json
import os

import categories as C
import replies

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(HERE, "Email Sorter.html")


def rules():
    return {
        "categories": C.CATEGORIES,
        "priority_categories": [c for c in C.CATEGORIES if c in C.PRIORITY_CATEGORIES],
        "descriptions": C.DESCRIPTIONS,
        "platform_domains": sorted(C.PLATFORM_DOMAINS),
        "platform_names": C.PLATFORM_NAMES,
        "licensing_domains": sorted(C.LICENSING_DOMAINS),
        "keyword_order": list(C.KEYWORDS),
        "keywords": {cat: {str(w): kws for w, kws in levels.items()} for cat, levels in C.KEYWORDS.items()},
        "min_score": C.MIN_SCORE,
        "page_categories": [[c, limit] for c, limit in replies.PAGE_CATEGORIES.items()],
        "templates": replies.TEMPLATES,
        "generic_name_words": sorted(replies.GENERIC_NAME_WORDS),
        "signature": replies.SIGNATURE,
        "reply_page": replies.PAGE,
    }


def build(output=OUTPUT):
    with open(os.path.join(HERE, "web", "app.html"), encoding="utf-8") as f:
        page = f.read()
    with open(os.path.join(HERE, "web", "sorter_core.js"), encoding="utf-8") as f:
        core = f.read()
    # "</" must not appear inside an inline <script>, or the browser ends the script early.
    data = json.dumps(rules(), ensure_ascii=False, indent=1).replace("</", "<\\/")
    assert "</script" not in core.lower()
    page = page.replace("/*__CORE__*/", core)
    page = page.replace("/*__RULES__*/", data)
    with open(output, "w", encoding="utf-8") as f:
        f.write(page)
    return output


if __name__ == "__main__":
    print(f"Wrote {build()}")
