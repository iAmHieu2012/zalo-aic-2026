# Training code — DataMate LoRA question parser

The inference model is the public `Qwen/Qwen3-14B` checkpoint (revision
`40c069824f4251a91eefaf281ebe4c544efd3e18`, Apache-2.0) plus one LoRA adapter for the
question parsers, trained by us. **Only the organizers' train split was used.**

## Contents

| Path | Content |
|---|---|
| `lora/build_labels.py` | label generation (below) |
| `lora/train_qlora.py` | QLoRA training script |
| `lora/data/labels.jsonl` | the training data: 2 790 chat examples (prompt + target JSON) |
| `lora/leave_out.py`, `lora/data/labels_lo_*.jsonl`, `lora/eval_leaveout.sh`, `lora/compare_runs.py` | leave-one-industry-out check (evaluation only, not used by the submitted adapter) |
| `notebooks/train_lora.ipynb` | the Colab notebook that ran the training |
| `checkpoints/lora-parse/` | the final adapter (identical to `/models/lora-parse`) |
| `src/`, `rules/`, `evals/`, `pyproject.toml` | system source, train rulebook parameters, evaluation code |
| `train/` | the organizers' train split when it was supplied at build time (not redistributed in git) |
| `data_manifest.json` | path, size and SHA-256 of every file, base model reference, dataset counts |

## 1. Labels — `lora/build_labels.py`

1. Run the base model (Qwen3-14B, temperature 0, seed 0) on the train subsets `dev` (1 735 q)
   and `poc` (256 q) with `python -m evals.run_eval`, which fills the LLM cache.
2. `python -m lora.build_labels --subsets dev poc --out lora/data/labels.jsonl --workers 12`
   re-runs the parsers exactly as the pipeline does (replies from that cache). Each vote's
   JSON is converted to a spec and computed by `MetricEngine`; a vote whose answer matches
   `train/answers.jsonl` becomes one example. The prompt is the parser prompt without
   few-shot examples (`example_limit=0`).
3. Result: 2 790 examples from 1 890 questions of 21 train shops (main parser 2 073,
   of which 524 "out of scope"; extension parser 717). Train subsets `val` (631 q) and
   `holdout_family` (120 q) are not in the labels and were used for validation.

Prompts and responses of the generated data are stored in `labels.jsonl` itself.

## 2. Training — `lora/train_qlora.py`

```bash
pip install -U transformers peft bitsandbytes accelerate
python lora/train_qlora.py --data lora/data/labels.jsonl --base Qwen/Qwen3-14B \
    --out lora-parse --rank 16 --alpha 32 --epochs 2 --lr 1e-4 --max-len 2560 --grad-accum 16
```

- QLoRA 4-bit (nf4) on all linear layers, LoRA dropout 0.05, cosine schedule, batch 1,
  seed 0. Loss only on the target JSON; prompts rendered with the chat template and
  `enable_thinking=False`, as vLLM does at inference.
- Hardware: one Colab GPU with ≥ 40 GB (see the notebook). Run: 350 steps, 1 h 17 min,
  mean train loss 0.034, final loss 0.004.
- Non-deterministic steps: GPU kernels in 4-bit training; re-training gives a close but not
  bit-identical adapter. The exact adapter used is in `checkpoints/lora-parse/`.

## 3. Validation (train split)

| | base | base + adapter |
|---|---|---|
| `val` (631) | 0.9065 | 0.9176 |
| `holdout_family` (120) | 0.9833 | 1.0000 |
