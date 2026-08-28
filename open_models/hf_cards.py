"""Fetch Hugging Face model cards in their machine-readable form.

A model card on the Hub is a README whose YAML front matter is the
machine-readable part; the Hub also exposes that same metadata (plus repo
facts the front matter does not carry - parameter counts from the
safetensors index, architecture, download and like counts) through
`/api/models/<repo>?full=true`. This module pulls both, plus `config.json`,
and keeps them together as one card document per model.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from . import config
from .http import fetch, fetch_json

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.S)


def repo_from_url(url: str) -> str:
    """Turn a huggingface.co model URL into an `org/name` repo id."""
    if not url:
        return ""
    m = re.match(r"https?://huggingface\.co/([^/]+/[^/?#]+)", url.strip())
    if not m:
        return ""
    repo = m.group(1)
    # Some links point at a subpath such as `/tree/main` or `/blob/main/...`.
    return repo.removesuffix(".git")


def parse_front_matter(readme: str) -> dict[str, Any]:
    """Parse the YAML front matter of a model card.

    Deliberately a small hand-rolled reader: model-card front matter is a
    narrow YAML subset (scalars, lists, one level of nesting) and this
    project ships without third-party dependencies.
    """
    m = _FRONT_MATTER.match(readme or "")
    if not m:
        return {}
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    for raw in m.group(1).splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if line.startswith("- "):
            item = _scalar(line[2:].strip())
            if isinstance(parent, list):
                parent.append(item)
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value:
            if isinstance(parent, dict):
                parent[key] = _scalar(value)
            continue
        child: Any = {} if _next_is_mapping(m.group(1), raw) else []
        if isinstance(parent, dict):
            parent[key] = child
            stack.append((indent, child))
    return root


def _next_is_mapping(block: str, current: str) -> bool:
    """Decide whether an empty `key:` opens a mapping or a list."""
    lines = block.splitlines()
    try:
        i = lines.index(current)
    except ValueError:
        return True
    for nxt in lines[i + 1:]:
        if not nxt.strip():
            continue
        return not nxt.strip().startswith("- ")
    return True


def _scalar(text: str) -> Any:
    text = text.strip().strip('"').strip("'")
    if text in ("true", "false"):
        return text == "true"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d*\.\d+", text):
        return float(text)
    return text


def fetch_card(repo: str) -> Optional[dict[str, Any]]:
    """Fetch the machine-format model card for `org/name`.

    Returns None when the repo is missing or gated behind a licence click,
    which the Hub answers with 404/401 respectively.
    """
    api = fetch_json(f"{config.HF_API}/{repo}?full=true")
    if api is None:
        return None
    revision = api.get("sha") or "main"
    readme = fetch(config.HF_RAW.format(repo=repo, revision=revision, path="README.md")) or ""
    model_config = fetch_json(
        config.HF_RAW.format(repo=repo, revision=revision, path="config.json")
    )
    return {
        "repo": repo,
        "url": f"https://huggingface.co/{repo}",
        "revision": revision,
        "card_metadata": parse_front_matter(readme),
        "hub_metadata": api,
        "model_config": model_config,
    }


def total_parameters(card: dict[str, Any]) -> Optional[int]:
    """Total parameter count from the safetensors index, if the repo has one."""
    st = (card.get("hub_metadata") or {}).get("safetensors") or {}
    total = st.get("total")
    if isinstance(total, int):
        return total
    params = st.get("parameters")
    if isinstance(params, dict):
        numbers = [v for v in params.values() if isinstance(v, int)]
        if numbers:
            return sum(numbers)
    return None
