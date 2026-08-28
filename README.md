# Open Weights Index

The **machine-format Hugging Face model card** for the current release of every
open-weights LLM, joined to its **Artificial Analysis Intelligence Index** score.

**Standard library only** — no `pip install`, Python 3.10+.

Latest run: **88 models across 45 labs**, Intelligence Index v4.1.1.

| | Model | Lab | Index | Params | Context | Licence |
|--|-------|-----|------:|-------:|--------:|---------|
| 1 | Kimi K3 | Kimi | 59.7 | 2.78T / 104B act | 1M | Kimi K3 License |
| 2 | GLM-5.3 | Z AI | 59.5 | 753B / 40B act | 1M | GLM-5.3 License |
| 3 | Qwen3.8 2.4T A95B | Alibaba | 57.7 | 2.45T / 95B act | 984k | Qwen3.8-Max License |
| 4 | GLM-5.3-Flash | Z AI | 57.5 | 321B / 18B act | 1M | MIT |
| 5 | Qwen3.8-Flash-Next | Alibaba | 55.8 | 180B / 6B act | 256k | Qwen Community 1.0 |
| 6 | DeepSeek V4 Pro 0813 | DeepSeek | 53.2 | 1.65T / 49B act | 1M | MIT |

## Output

| File | What it is |
|------|------------|
| `data/open_model_index.csv` | The table, flat: 88 rows × 38 columns, one column per Intelligence Index component, ASCII headers |
| `data/open_model_index.json` | The same table plus provenance — index version, source labels, and the models skipped for want of a readable card |
| `data/model_cards/<org>__<name>.json` | One raw card per model: the Hub's `/api/models/<repo>?full=true` document, the YAML front matter of the card README, and the repo's `config.json` |
| `site/index.html` | Self-contained sortable/filterable page built from the JSON — no server, no build step |

Every row keys on `hf_repo`, so the table joins straight back to the archived
cards or to the Hub.

### Columns

`rank`, `name`, `creator`, `country`, `intelligence_index`, `best_effort`,
`effort_spread`, `agentic_index`, `openness_index`, `params_billions`,
`active_params_billions`, `context_window_tokens`, `license`, `license_url`,
`license_category`, `reasoning`, `release_date`, `hub_last_modified`,
`knowledge_cutoff`, `architecture`, `pipeline_tag`, `modalities_in`,
`modalities_out`, `downloads_30d`, `likes`, `aa_open_weights`,
`intelligence_is_estimated`, `hf_repo`, `hf_url`, then the nine index
components: `GDPval-AA v2`, `tau3-Banking`, `Terminal-Bench v2.1`, `SciCode`,
`Humanity's Last Exam`, `GPQA Diamond`, `CritPt`, `AA-Omniscience`, `AA-LCR`.

All nine components are normalised to 0–100. The raw benchmarks arrive as
fractions and the AA indices do not, so mixing them unconverted would be wrong
by 100×. `AA-Omniscience` is legitimately negative for models that hallucinate
more than they answer correctly.

## Running it

```sh
python3 scripts/build_model_index.py     # fetch cards + scores -> data/
python3 scripts/build_model_table.py     # data/ -> site/index.html
```

`--no-cards` reuses the archived cards instead of re-fetching the Hub;
`--limit N` stops after N models.

## Where the numbers come from

**Model cards.** A card on the Hub is a README whose YAML front matter is the
machine-readable half. The Hub also exposes that metadata — plus facts the front
matter does not carry, such as parameter counts summed from the safetensors
index — through `/api/models/<repo>?full=true`. Both are pulled, so parameter
totals are the shipped weights rather than a rounded marketing figure.

**Intelligence Index.** Artificial Analysis gates its API behind a key, but every
model detail page on `artificialanalysis.ai` server-renders the whole catalogue
into its React Server Components payload — one flat JSON object per model with
the index score, its nine component evaluations, licence, parameter counts and
the Hugging Face URL the weights live at. `open_models/artificial_analysis.py`
reassembles that payload from the page's `self.__next_f.push([1,"…"])` chunks
and reads the objects straight out of it. That last field is what makes the join
to the Hub reliable: the pairing is the benchmarker's own, not a name match.

## What "latest version" means here

Applied in order, in `open_models/index.py`:

1. **Candidates** are open-weights entries that are not marked deprecated and
   were released on or after `config.RELEASED_SINCE`. An entry also qualifies
   when it already points at a public Hub repo — a lab's weights sometimes land
   before Artificial Analysis re-classifies the entry (GLM-5.3 on this run).
2. **Reasoning-effort variants** of one release (`max`, `high`, `low`,
   `Non-reasoning`) collapse into a single row, scored at its best setting; the
   spread is kept in `effort_spread`. Keying on lab plus base name rather than
   on the repo also merges releases split across a base and an `-it` repo.
3. **Superseded releases drop out**: a release goes when the same lab has a newer
   one in the same size class scoring at least as well. What remains is each
   lab's live lineup across size tiers, rather than only the newest thing each
   lab shipped — so gpt-oss-120b and Llama 4 stay in, while Qwen3.6 and Granite
   4.1 drop out behind their own successors.

Anything with no readable card — gated behind a licence click, or moved — is
skipped and named in `skipped` in the JSON and at the foot of the page. One
model on this run: `perplexity-ai/r1-1776`, which answers 401 anonymously.

## Layout

```
open_models/
  artificial_analysis.py   catalogue + Intelligence Index out of the RSC payload
  hf_cards.py              Hub API, card front matter, config.json
  index.py                 the join, the selection rules, the output row
  http.py                  stdlib GET with retries and backoff
  config.py                endpoints, date floor, repo overrides
  table_template.html      the page, with a __DATA__ placeholder
scripts/
  build_model_index.py     -> data/
  build_model_table.py     -> site/index.html
```

## Known joins that need a hand

`config.HF_REPO_OVERRIDES` maps a handful of model slugs onto the first-party
repo carrying the card, where Artificial Analysis links a lab's own download page
or a quantised mirror instead. Licence labels prefer the card over the index,
since a card that declares `license: other` and names a bespoke licence is
authoritative for its own repo.

## Sources

- Model cards: [huggingface.co](https://huggingface.co) — each lab's own repo
- Scores: [artificialanalysis.ai](https://artificialanalysis.ai/models/open-source)
