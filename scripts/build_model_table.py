#!/usr/bin/env python3
"""Render the open-weights model index as a single self-contained HTML page.

    python3 scripts/build_model_table.py [-o site/index.html]

Reads data/open_model_index.json (written by build_model_index.py) and
inlines it into open_models/table_template.html, so the result opens with no
server, no build step and no network access beyond its webfonts.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from open_models import config  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "open_models", "table_template.html")
DEFAULT_OUT = os.path.join(ROOT, "site", "index.html")

# Fields the page actually reads; everything else stays in the JSON dataset.
PAGE_FIELDS = (
    "name", "creator", "country", "hf_repo", "hf_url", "release_date",
    "intelligence_index", "effort_spread", "openness_index", "params_billions",
    "active_params_billions", "context_window_tokens", "license", "license_url",
    "reasoning", "modalities_in", "architecture", "pipeline_tag",
    "downloads_30d", "likes", "knowledge_cutoff", "agentic_index", "evals",
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    with open(config.INDEX_JSON, encoding="utf-8") as fh:
        payload = json.load(fh)

    trimmed = {
        "models": [{k: m.get(k) for k in PAGE_FIELDS} for m in payload["models"]],
        "skipped": payload.get("skipped", []),
    }
    with open(TEMPLATE, encoding="utf-8") as fh:
        html = fh.read()

    stamp = date.fromisoformat(payload["generated"]).strftime("%-d %B %Y")
    html = (html
            .replace("__DATA__", json.dumps(trimmed, separators=(",", ":"),
                                             ensure_ascii=False).replace("<", "\\u003c"))
            .replace("__GENERATED__", stamp)
            .replace("__II_VERSION__", payload.get("intelligence_index_version") or ""))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"Wrote {args.out} ({len(html) / 1024:.0f} KB, {len(trimmed['models'])} models)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
