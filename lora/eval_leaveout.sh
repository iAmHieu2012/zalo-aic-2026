#!/usr/bin/env bash
# Leave-one-industry-out check. Needs the vLLM server of colab_vllm.ipynb with
# MODEL_CHOICE = "qwen3-14b-bf16-lora-lo" (base qwen3-14b-bf16 + adapters lo-<industry>) in .env.
# For each industry: base run and LoRA run (adapter trained without it) on --subset ind_<industry>,
# then lora.compare_runs. Logs and the result table go to runs/leaveout_<timestamp>/.
#   [LIMIT=150] bash lora/eval_leaveout.sh [pharmacy building restaurant]
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $# -gt 0 ]]; then FOLDS=("$@"); else FOLDS=(pharmacy building restaurant); fi
WORKERS="${WORKERS:-8}"
LIMIT_ARGS=(); [[ -n "${LIMIT:-}" ]] && LIMIT_ARGS=(--limit "${LIMIT}")  # LIMIT=150: first 150 questions per fold
OUT="runs/leaveout_$(date +%Y%m%d-%H%M%S)"
mkdir -p "${OUT}"

run() {  # $1 = log name, $2 = LLM_PARSE_MODEL value (empty = base), $3 = subset
  LLM_PARSE_MODEL="$2" .venv/bin/python -m evals.run_eval --system pipeline_llm --subset "$3" \
    --workers "${WORKERS}" "${LIMIT_ARGS[@]}" > "${OUT}/$1.log" 2>&1
  sed -n 's/^Run saved to //p' "${OUT}/$1.log" | tail -1
}

for f in "${FOLDS[@]}"; do
  echo "=== ${f}"
  base_dir=$(run "base_${f}" "" "ind_${f}")
  lora_dir=$(run "lora_${f}" "lo-${f}" "ind_${f}")
  {
    echo "## ${f}  (base: ${base_dir}, lora: ${lora_dir})"
    .venv/bin/python -m lora.compare_runs "${base_dir}" "${lora_dir}"
    echo
  } | tee -a "${OUT}/results.md"
done
echo "results -> ${OUT}/results.md"
