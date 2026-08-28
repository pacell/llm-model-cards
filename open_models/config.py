"""Endpoints, tuning knobs and the small amount of hand-maintained mapping."""

from __future__ import annotations

import os

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT_SECONDS = 45
MAX_RETRIES = 4

HF_API = "https://huggingface.co/api/models"
HF_RAW = "https://huggingface.co/{repo}/raw/{revision}/{path}"

AA_BASE = "https://artificialanalysis.ai"
# Every model detail page ships the whole model catalogue in its React
# Server Components payload, so any one of these works as a seed. They are
# tried in order in case a slug is renamed or retired.
AA_SEED_PAGES = (
    "/models/kimi-k3",
    "/models/glm-5-3",
    "/models/deepseek-v4-pro",
    "/models/qwen3-8-27b",
)

# Floor on release date. The point of the index is each lab's *current*
# lineup, and superseded releases are dropped by rule rather than by date,
# so this only exists to keep genuinely historical entries out.
RELEASED_SINCE = "2025-01-01"

# Artificial Analysis links weights to a lab's own download page for a
# handful of models, or points at a quantised mirror. These map the model
# slug onto the first-party Hugging Face repo that carries the model card.
HF_REPO_OVERRIDES = {
    "motif-3": "Motif-Technologies/Motif-3",
    "ling-3-0-flash": "inclusionAI/Ling-3.0-flash",
    "ling-3-0-tiny": "inclusionAI/Ling-3.0-tiny",
    "k-exaone-2-0-0803": "LGAI-EXAONE/K-EXAONE-2.0-750B-A37B",
    "nemotron-3-5-lightning": "nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16",
}

# Repos that are gated or otherwise unreadable anonymously get skipped with
# a note rather than failing the run.
# Anchored to the repo root so the scripts write to the same place whatever
# directory they are invoked from.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARD_DIR = os.path.join(_ROOT, "data", "model_cards")
INDEX_JSON = os.path.join(_ROOT, "data", "open_model_index.json")
INDEX_CSV = os.path.join(_ROOT, "data", "open_model_index.csv")
