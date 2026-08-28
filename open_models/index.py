"""Join Hugging Face model cards to the Artificial Analysis Intelligence Index.

Selection rules, applied in order:

1. Candidates are Artificial Analysis records that are open weights (or that
   already point at a public Hugging Face repo - a lab's weights sometimes
   land before Artificial Analysis re-classifies the entry), are not marked
   deprecated, and were released on or after `config.RELEASED_SINCE`.
2. Reasoning-effort variants of one release ("max", "high", "low",
   "Non-reasoning") collapse into a single row per release, scored
   at its best setting; the spread is kept alongside.
3. A release is dropped as superseded when the same lab has a newer release
   in the same size class that scores at least as well.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

from . import config
from .hf_cards import fetch_card, repo_from_url, total_parameters

_EFFORT = re.compile(r"\s*\((max|xhigh|high|medium|low|minimal|reasoning|non-reasoning"
                     r"|with fallback)[^)]*\)\s*$", re.I)


@dataclass
class ModelRow:
    """One open-weights release, as it appears in the published table."""

    name: str
    creator: str
    country: str
    hf_repo: str
    hf_url: str
    release_date: str
    hub_last_modified: str
    intelligence_index: Optional[float]
    intelligence_is_estimated: bool
    best_effort: str
    effort_spread: dict[str, float]
    openness_index: Optional[float]
    params_billions: Optional[float]
    active_params_billions: Optional[float]
    context_window_tokens: Optional[int]
    license: str
    license_url: str
    license_category: str
    aa_open_weights: bool
    reasoning: bool
    modalities_in: list[str]
    modalities_out: list[str]
    architecture: str
    pipeline_tag: str
    downloads_30d: Optional[int]
    likes: Optional[int]
    knowledge_cutoff: str
    agentic_index: Optional[float] = None
    evals: dict[str, Optional[float]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _base_name(name: str) -> str:
    return _EFFORT.sub("", name).strip()


def _effort_label(name: str) -> str:
    m = _EFFORT.search(name)
    return m.group(1).lower() if m else "default"


def candidates(catalogue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter the Artificial Analysis catalogue down to current open weights."""
    out = []
    for rec in catalogue:
        if rec.get("deprecated"):
            continue
        url = rec.get("modelWeightsSourceUrl") or ""
        on_hub = url.startswith("https://huggingface.co/")
        if not (rec.get("isOpenWeights") or on_hub):
            continue
        if (rec.get("releaseDate") or "") < config.RELEASED_SINCE:
            continue
        repo = config.HF_REPO_OVERRIDES.get(rec["slug"]) or repo_from_url(url)
        if not repo:
            continue
        rec = dict(rec, _repo=repo)
        out.append(rec)
    return out


def collapse_variants(recs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One entry per release, scored at its best reasoning effort.

    Keyed on lab plus base name rather than on the repo, because a single
    release is sometimes split across repos - a base and an `-it` instruct
    repo, say - that Artificial Analysis scores as one model.
    """
    by_release: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for rec in recs:
        key = ((rec.get("creator") or {}).get("name", ""), _base_name(rec["name"]))
        by_release.setdefault(key, []).append(rec)
    collapsed = []
    for group in by_release.values():
        group.sort(key=lambda r: -(r.get("intelligenceIndex") or -1))
        best = dict(group[0])
        best["_spread"] = {
            _effort_label(r["name"]): round(r["intelligenceIndex"], 1)
            for r in group if r.get("intelligenceIndex") is not None
        }
        best["_effort"] = _effort_label(best["name"])
        best["_base_name"] = _base_name(best["name"])
        best["_repos"] = sorted({r["_repo"] for r in group})
        collapsed.append(best)
    return collapsed


def drop_superseded(recs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove releases a lab has already replaced with something better."""
    kept = []
    for rec in recs:
        creator = (rec.get("creator") or {}).get("name")
        score = rec.get("intelligenceIndex") or 0.0
        date = rec.get("releaseDate") or ""
        newer = any(
            other is not rec
            and (other.get("creator") or {}).get("name") == creator
            and other.get("sizeClass") == rec.get("sizeClass")
            and (other.get("releaseDate") or "") > date
            and (other.get("intelligenceIndex") or 0.0) >= score
            for other in recs
        )
        if not newer:
            kept.append(rec)
    return kept


# The nine evaluations that make up Intelligence Index v4.1.1, in the order
# Artificial Analysis lists them. The scale factor puts each on 0-100: the
# raw benchmarks are reported as fractions, the AA indices already are not.
_EVAL_FIELDS = (
    ("gdpvalNormalized", "GDPval-AA v2", 100),
    ("tauBanking", "\u03c4\u00b3-Banking", 100),
    ("terminalbenchV21", "Terminal-Bench v2.1", 100),
    ("scicode", "SciCode", 100),
    ("hle", "Humanity's Last Exam", 100),
    ("gpqa", "GPQA Diamond", 100),
    ("critpt", "CritPt", 100),
    ("omniscience", "AA-Omniscience", 1),
    ("lcr", "AA-LCR", 100),
)


_LICENSE_DISPLAY = {
    "mit": "MIT",
    "apache-2.0": "Apache 2.0",
    "bsd-3-clause": "BSD 3-Clause",
    "cc-by-4.0": "CC BY 4.0",
    "cc-by-nc-4.0": "CC BY-NC 4.0",
    "gemma": "Gemma Terms of Use",
    "llama3": "Llama 3 Community",
    "llama3.1": "Llama 3.1 Community",
    "llama4": "Llama 4 Community",
}


def _license(meta: dict[str, Any], rec: dict[str, Any]) -> str:
    """The licence the repo itself declares, falling back to the index's label.

    The model card is authoritative here: Artificial Analysis sometimes
    carries a simplified label (or none at all) for a bespoke lab licence.
    A card sets `license: other` and names the real one in `license_name`.
    """
    declared = str(meta.get("license") or "").strip().lower()
    named = str(meta.get("license_name") or "").strip()
    if declared and declared != "other":
        return _LICENSE_DISPLAY.get(declared, declared.replace("-", " ").title())
    # A card that declares `other` is under a bespoke licence, so an index
    # label of "MIT" or "Apache" for it is stale and gets ignored.
    label = str(rec.get("licenseName") or "").strip()
    if label and label.lower().replace(" ", "-") not in _LICENSE_DISPLAY:
        return label
    if named:
        return _prettify_licence(named)
    return label


_ACRONYMS = {"glm": "GLM", "lfm": "LFM", "mit": "MIT", "tii": "TII", "llm": "LLM",
             "ai": "AI", "nvidia": "NVIDIA", "exaone": "EXAONE", "openmdw": "OpenMDW",
             "ernie": "ERNIE", "olmo": "OLMo", "cc": "CC", "bsd": "BSD"}


def _prettify_licence(slug: str) -> str:
    """Turn a licence slug such as `nvidia-open-model` into a readable label."""
    words = []
    for word in slug.replace("_", "-").split("-"):
        if word.lower() in _ACRONYMS:
            words.append(_ACRONYMS[word.lower()])
        elif any(ch.isdigit() for ch in word):
            words.append(word)
        else:
            words.append(word.capitalize())
    text = " ".join(words)
    return text if "licen" in text.lower() else text + " License"


def build_row(rec: dict[str, Any], card: dict[str, Any]) -> ModelRow:
    """Merge one Artificial Analysis record with its Hugging Face card."""
    hub = card.get("hub_metadata") or {}
    meta = card.get("card_metadata") or {}
    cfg = card.get("model_config") or {}
    params = total_parameters(card)
    architectures = (cfg.get("architectures") or hub.get("config", {}).get("architectures") or [])
    modal_in = [k for k, v in (
        ("text", rec.get("inputModalityText")), ("image", rec.get("inputModalityImage")),
        ("speech", rec.get("inputModalitySpeech")), ("video", rec.get("inputModalityVideo")),
    ) if v]
    modal_out = [k for k, v in (
        ("text", rec.get("outputModalityText")), ("image", rec.get("outputModalityImage")),
        ("speech", rec.get("outputModalitySpeech")), ("video", rec.get("outputModalityVideo")),
    ) if v]
    license_name = _license(meta, rec)
    return ModelRow(
        name=rec.get("_base_name") or rec["name"],
        creator=(rec.get("creator") or {}).get("name", ""),
        country=(rec.get("creator") or {}).get("country", ""),
        hf_repo=card["repo"],
        hf_url=card["url"],
        release_date=rec.get("releaseDate") or "",
        hub_last_modified=(hub.get("lastModified") or "")[:10],
        intelligence_index=(round(rec["intelligenceIndex"], 1)
                            if rec.get("intelligenceIndex") is not None else None),
        intelligence_is_estimated=bool(rec.get("intelligenceIndexIsEstimated")),
        best_effort=rec.get("_effort", "default"),
        effort_spread=rec.get("_spread", {}),
        openness_index=(round((rec.get("openness") or {}).get("opennessIndex"), 1)
                        if (rec.get("openness") or {}).get("opennessIndex") is not None else None),
        params_billions=(round(params / 1e9, 1) if params else
                         (float(rec["parameters"]) if rec.get("parameters") else None)),
        active_params_billions=(float(rec["inferenceParametersActiveBillions"])
                                if rec.get("inferenceParametersActiveBillions") else None),
        context_window_tokens=rec.get("contextWindowTokens"),
        license=license_name,
        license_url=rec.get("licenseUrl") or "",
        license_category=rec.get("openSourceCategorization") or "",
        aa_open_weights=bool(rec.get("isOpenWeights")),
        reasoning=bool(rec.get("isReasoning")),
        modalities_in=modal_in,
        modalities_out=modal_out,
        architecture=architectures[0] if architectures else "",
        pipeline_tag=hub.get("pipeline_tag") or meta.get("pipeline_tag") or "",
        downloads_30d=hub.get("downloads"),
        likes=hub.get("likes"),
        knowledge_cutoff=(rec.get("knowledgeCutoffDate") or "")[:10],
        agentic_index=(round(rec["agenticIndex"], 1)
                       if isinstance(rec.get("agenticIndex"), (int, float)) else None),
        evals={label: (round(rec[key] * scale, 1)
                       if isinstance(rec.get(key), (int, float)) else None)
               for key, label, scale in _EVAL_FIELDS},
    )
