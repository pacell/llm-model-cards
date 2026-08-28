"""Pull the Artificial Analysis model catalogue (incl. Intelligence Index).

Artificial Analysis publishes its numbers through an API that requires a
key, but every model detail page on artificialanalysis.ai server-renders the
full catalogue into its React Server Components payload. Each model there is
a flat JSON object carrying the Intelligence Index, its component
evaluations, parameter counts, licence and - crucially for the join here -
the Hugging Face URL the weights live at.

This module extracts those objects out of the `self.__next_f.push([1,"..."])`
chunks that make up the payload.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterator, NamedTuple, Optional

from . import config
from .http import fetch

_CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,\s*("(?:[^"\\]|\\.)*")\]\)')
_MODEL_KEY = '"modelWeightsSourceUrl"'


def flight_payload(html: str) -> str:
    """Reassemble the RSC flight payload from the page's script chunks."""
    parts = []
    for chunk in _CHUNK_RE.findall(html):
        try:
            parts.append(json.loads(chunk))
        except json.JSONDecodeError:
            continue
    return "".join(parts)


def _enclosing_object(text: str, hit: int) -> Optional[tuple[str, int]]:
    """Return the balanced `{...}` containing offset `hit`, plus its end offset."""
    depth, i, start = 0, hit, None
    while i >= 0:                      # walk back to the opening brace
        c = text[i]
        if c == "}":
            depth += 1
        elif c == "{":
            if depth == 0:
                start = i
                break
            depth -= 1
        i -= 1
    if start is None:
        return None
    depth, j, in_str, esc = 0, start, False, False
    while j < len(text):               # walk forward to its partner
        c = text[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:j + 1], j + 1
        j += 1
    return None


def iter_model_records(payload: str) -> Iterator[dict[str, Any]]:
    """Yield every model object embedded in an RSC flight payload."""
    idx = 0
    while True:
        hit = payload.find(_MODEL_KEY, idx)
        if hit < 0:
            return
        found = _enclosing_object(payload, hit)
        if found is None:
            idx = hit + 1
            continue
        blob, idx = found
        try:
            obj = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("slug"):
            yield obj


class Catalogue(NamedTuple):
    """Every model Artificial Analysis tracks, plus the index version used."""

    models: list[dict[str, Any]]
    index_version: str


def fetch_catalogue() -> Catalogue:
    """Fetch the full Artificial Analysis model catalogue.

    Raises RuntimeError if none of the seed pages yields a usable payload.
    """
    for seed in config.AA_SEED_PAGES:
        html = fetch(config.AA_BASE + seed)
        if not html:
            continue
        records: dict[str, dict[str, Any]] = {}
        for rec in iter_model_records(flight_payload(html)):
            prev = records.get(rec["slug"])
            # Keep the richest copy if a slug appears more than once.
            if prev is None or len(json.dumps(rec)) > len(json.dumps(prev)):
                records[rec["slug"]] = rec
        if len(records) > 100:
            return Catalogue(list(records.values()), index_version(html))
    raise RuntimeError("could not read the Artificial Analysis catalogue")


def index_version(html: str) -> str:
    """Best-effort read of the Intelligence Index version the page reports."""
    m = re.search(r"Artificial Analysis Intelligence Index (v[\d.]+)", html)
    return m.group(1) if m else ""
