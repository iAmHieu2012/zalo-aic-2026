# DataMate — Zalo AI Challenge 2026 (inference image)

Answers Vietnamese questions about a small shop's CSV / Excel / SQLite files, scored by
Penalized Accuracy (correct +1, abstain 0, wrong −1). When unsure, the system abstains.

## Run

```bash
bash /code/predict.sh          # no arguments; reads /data, writes /result
```

`predict.sh` starts vLLM on `127.0.0.1:8000` with the packaged weights, then runs
`python3 -m datamate.predict --data-dir /data --out-dir /result`. Every setting is fixed
inside the script and the image ENV (model, seed 0, temperature 0, `--max-model-len 16384`,
8 workers, 18 900 s time budget). Network is not used.

Output:

| Path | Content |
|---|---|
| `/result/submission.jsonl` | one line per question, written and fsynced as soon as it is answered |
| `/result/logs/log.jsonl` | one record per question: `id`, `answer`, `elapsed_ms`, `thinking`, `code`, `inputs`, `output` |
| `/result/logs/<id>.json` | the same record plus the full trace (parser votes, SQL, checks) |
| `/result/timing.json`, `/result/vllm.log` | run timing, vLLM server log |

`thinking` is `null`: Qwen3 thinking mode is disabled (`LLM_DISABLE_THINKING=true`), so no
reasoning text is generated. `code` is the SQL that was executed on DuckDB (or the packaged
function used), `inputs` the parsed query spec, `output` the computed value.

## Approach

1. **Per shop** — the LLM maps each raw column to a canonical schema (orders, order lines,
   products, customers, payments, debts, purchases, stock, batches). Cells are parsed by
   deterministic code (money, dates, quantities) and loaded into DuckDB; integrity checks
   quarantine tables whose mapping fails.
2. **Rulebook** — the LLM classifies each line of `/data/rulebook.md` and extracts the
   calculation parameters (revenue statuses, shifts, week start, rounding, ...).
3. **Per question** — the LLM (base + LoRA adapter for parsing) parses the question into a `QuerySpec` twice; only when both
   votes agree is the answer computed by `MetricEngine` (deterministic SQL on DuckDB).
   Questions outside the main schema go through an extension parser (~30 business families)
   with a verifier. Subjective questions get `unanswerable`. Anything uncertain is abstained.

No answer is hard-coded and no logic depends on question or business IDs.

## Models

| | Model | Source | Revision | Released | License | Parameters |
|---|---|---|---|---|---|---:|
| LLM (base) | Qwen3-14B (BF16) | https://huggingface.co/Qwen/Qwen3-14B | `40c069824f4251a91eefaf281ebe4c544efd3e18` | 2025-04-27 | Apache-2.0 | 14.77B |
| LoRA adapter (question parser) | `lora-parse`, trained by us on the train split | this image | `/models/lora-parse` | 2026-11-14 | Apache-2.0 (same as base) | ~0.06B |
| Embedding / reranker / classifier | not used | | | | | 0 |
| **Total** | | | | | | **≈14.83B (≤ 15B)** |

Weights: `/models/Qwen3-14B` (served by vLLM as `qwen3-14b`, tensor parallel 2) and the adapter
`/models/lora-parse` (served as `datamate-parse`, used only by the question parsers; column
mapping, rulebook and verifier use the base model).

## Data

Only the organizers' **train** split was used during development, to write and check the
code and the parsing prompts (`evals/` scores a run against `train/answers.jsonl`).
The LoRA adapter was trained on labels generated from the train split only — see
`/code/training_code/README.md`. Public/private test data were not used for training.

## Folder layout

| Path | Content |
|---|---|
| `/code/predict.sh` | entry point |
| `/code/README.md` | this file |
| `/app/src/datamate/` | inference code (installed as the `datamate` package) |
| `/app/rules/`, `/app/evals/` | train rulebook parameters (tests/evals), evaluation scripts |
| `/models/` | model weights |
| `/code/training_code/` | label generation and training code, labels, adapter checkpoint, `data_manifest.json` |
