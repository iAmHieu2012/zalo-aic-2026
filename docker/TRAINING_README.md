# Training code — DataMate (Qwen3-14B-FP8, no fine-tuning)

**No training or fine-tuning was performed for this image.** One small resource is
generated from train text: `src/datamate/parse/vi_syllables.txt` (715 Vietnamese syllables
written with diacritics, taken from `train/rulebook.md`, the train shops' `README.md` files
and the train questions), used to undo Telex typing in questions. Rebuild it with

```bash
python scripts/build_vi_syllables.py      # needs train/ at the repo root
```
The inference model is the public `Qwen/Qwen3-14B-FP8` checkpoint, unchanged
(revision `9a283b4a5efbc09ce247e0ae5b02b744739e525a`, Apache-2.0, see `data_manifest.json`).

What this folder contains, for verification:

| Path | Content |
|---|---|
| `src/` | the full system source (same as the inference code) |
| `scripts/build_vi_syllables.py` | generates `src/datamate/parse/vi_syllables.txt` from train text (deterministic) |
| `rules/train.json` | calculation parameters of the **train** rulebook (`train/rulebook.md`); used only by tests and evals (at inference the rulebook in `/data` is read by the LLM) |
| `evals/` | scoring of a run against `train/answers.jsonl`, subsets, run comparison |
| `pyproject.toml` | package metadata and dependencies |
| `train/` | the organizers' train split when it was supplied at build time (it is not redistributed in git) |
| `data_manifest.json` | path, size and SHA-256 of every file here, plus the base model reference |

Development data: the organizers' train split only (questions, answers, shop files,
rulebook). Prompts and code were checked with

```bash
python -m evals.run_eval --split train --subset val --system pipeline_llm --workers 12
```

against a vLLM server running the same checkpoint (temperature 0, seed 0).
