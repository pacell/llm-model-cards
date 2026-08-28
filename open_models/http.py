"""Tiny stdlib HTTP helper with a browser UA, retries and backoff."""

from __future__ import annotations

import gzip
import json
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from . import config


def fetch(url: str, *, timeout: int = config.REQUEST_TIMEOUT_SECONDS,
          retries: int = config.MAX_RETRIES) -> Optional[str]:
    """GET a URL and return decoded text, or None on persistent failure.

    Retries with exponential backoff (2s, 4s, 8s, 16s) on transient errors.
    """
    headers = {
        "User-Agent": config.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip",
    }
    delay = 2.0
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except urllib.error.HTTPError as e:
            # Gated repos answer 401, missing ones 404 - neither is transient.
            if e.code in (401, 403, 404, 410):
                return None
        except Exception:  # noqa: BLE001 - network errors of many kinds
            pass
        if attempt < retries:
            time.sleep(delay)
            delay *= 2
    return None


def fetch_json(url: str, **kw: Any) -> Optional[Any]:
    """GET a URL and parse it as JSON, or None if either step fails."""
    text = fetch(url, **kw)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
