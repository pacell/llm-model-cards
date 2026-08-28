#!/usr/bin/env python3
"""Build the open-weights model index.

Pulls the machine-format model card for the latest release of every
open-weights model Artificial Analysis tracks, joins on the Artificial
Analysis Intelligence Index, and writes the table as JSON and CSV.

    python3 scripts/build_model_index.py [--limit N] [--no-cards]

Raw cards are archived one JSON document per model under data/model_cards/
so the table can be rebuilt without re-fetching the Hub.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from open_models import config, index                      # noqa: E402
from open_models.artificial_analysis import fetch_catalogue  # noqa: E402
from open_models.hf_cards import fetch_card                 # noqa: E402

# Flat columns; the nine Intelligence Index components are appended after
# these, one column each, so the CSV carries everything the JSON does bar the
# raw cards themselves.
CSV_COLUMNS = [
    "rank", "name", "creator", "country", "intelligence_index", "best_effort",
    "effort_spread", "agentic_index", "openness_index", "params_billions",
    "active_params_billions", "context_window_tokens", "license", "license_url",
    "license_category", "reasoning", "release_date", "hub_last_modified",
    "knowledge_cutoff", "architecture", "pipeline_tag", "modalities_in",
    "modalities_out", "downloads_30d", "likes", "aa_open_weights",
    "intelligence_is_estimated", "hf_repo", "hf_url",
]


def card_path(repo: str) -> str:
    return os.path.join(config.CARD_DIR, repo.replace("/", "__") + ".json")


def load_or_fetch(repo: str, *, refetch: bool) -> dict | None:
    path = card_path(repo)
    if not refetch and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    card = fetch_card(repo)
    if card is None:
        return None
    os.makedirs(config.CARD_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(card, fh, indent=1, ensure_ascii=False)
    return card


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="stop after N models")
    ap.add_argument("--no-cards", action="store_true",
                    help="reuse archived cards instead of re-fetching the Hub")
    args = ap.parse_args()

    print("Fetching the Artificial Analysis catalogue ...", flush=True)
    catalogue = fetch_catalogue()
    selected = index.drop_superseded(
        index.collapse_variants(index.candidates(catalogue.models))
    )
    selected.sort(key=lambda r: -(r.get("intelligenceIndex") or -1))
    if args.limit:
        selected = selected[:args.limit]
    print(f"  {len(catalogue.models)} models tracked ({catalogue.index_version}) "
          f"-> {len(selected)} current open-weights releases")

    rows, skipped = [], []
    for i, rec in enumerate(selected, 1):
        repo = rec["_repo"]
        card = load_or_fetch(repo, refetch=not args.no_cards)
        if card is None:
            skipped.append((rec["_base_name"], repo))
            print(f"  [{i:>3}/{len(selected)}] {repo}: no readable card (gated or moved)")
            continue
        rows.append(index.build_row(rec, card))
        print(f"  [{i:>3}/{len(selected)}] {repo}", flush=True)
        if not args.no_cards:
            time.sleep(0.2)

    payload = {
        "generated": date.today().isoformat(),
        "source_intelligence": "Artificial Analysis Intelligence Index",
        "intelligence_index_version": catalogue.index_version,
        "source_cards": "Hugging Face Hub model cards (machine-readable metadata)",
        "models_tracked": len(catalogue.models),
        "models": [r.as_dict() for r in rows],
        "skipped": [{"name": n, "hf_repo": r} for n, r in skipped],
    }
    os.makedirs(os.path.dirname(config.INDEX_JSON), exist_ok=True)
    with open(config.INDEX_JSON, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False)

    # ASCII column names in the CSV so naive readers cope; the JSON keeps the
    # evaluations under their proper names.
    ascii_eval = {label: label.replace("\u03c4\u00b3", "tau3") for _, label, _ in index._EVAL_FIELDS}
    eval_columns = list(ascii_eval.values())
    with open(config.INDEX_CSV, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS + eval_columns,
                                extrasaction="ignore")
        writer.writeheader()
        for rank, row in enumerate(rows, 1):
            d = row.as_dict()
            d["rank"] = rank
            d["modalities_in"] = "+".join(d["modalities_in"])
            d["modalities_out"] = "+".join(d["modalities_out"])
            d["effort_spread"] = " ".join(f"{k}={v}" for k, v in d["effort_spread"].items())
            d.update({ascii_eval[k]: v for k, v in d.pop("evals").items()})
            writer.writerow(d)

    print(f"\nWrote {config.INDEX_JSON} and {config.INDEX_CSV} "
          f"({len(rows)} models, {len(skipped)} skipped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
