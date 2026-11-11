#!/usr/bin/env bash
# Offline entrypoint for Zalo AI Challenge 2026 DataMate Track:
# 1. Starts local vLLM (Qwen3-14B-FP8) if GPU + weights exist.
# 2. Runs HybridSystem (Tier-1 FastCore deterministic + Tier-2 LLM DuckDB Engine).
# 3. If vLLM fails or is absent, gracefully falls back to Tier-1 FastCore (CPU) instead of 0-score all-abstain.
set -euo pipefail

DATA_DIR="${DATAMATE_DATA_DIR:-/data}"
OUT_DIR="${DATAMATE_OUT_DIR:-/result}"
MODEL_DIR="${DATAMATE_MODEL_DIR:-/models/Qwen3-14B-FP8}"
SERVED_NAME="${LLM_MODEL:-qwen3-14b}"
SYSTEM_MODE="${DATAMATE_SYSTEM:-hybrid}"
WORKERS="${DATAMATE_WORKERS:-8}"
TIME_BUDGET_S="${DATAMATE_TIME_BUDGET_S:-18900}"
TP_SIZE="${DATAMATE_TP_SIZE:-1}"  # 14B FP8 fits one 32 GB RTX 5090 card; override with DATAMATE_TP_SIZE=2 if desired
GPU_UTIL="${DATAMATE_GPU_UTIL:-0.90}"
MAX_SEQS="${DATAMATE_MAX_NUM_SEQS:-16}"
VLLM_PORT="${DATAMATE_VLLM_PORT:-8000}"
VLLM_WAIT_S="${DATAMATE_VLLM_WAIT_S:-900}"

mkdir -p "${OUT_DIR}" "${OUT_DIR}/logs" "${OUT_DIR}/work"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export VLLM_NO_USAGE_STATS=1
export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-0}"
export LLM_BASE_URL="http://127.0.0.1:${VLLM_PORT}/v1"
export LLM_MODEL="${SERVED_NAME}"
export LLM_API_KEY="${LLM_API_KEY:-EMPTY}"
export LLM_DISABLE_THINKING="${LLM_DISABLE_THINKING:-true}"

write_all_abstain() {
  DATAMATE_DATA_DIR="${DATA_DIR}" DATAMATE_OUT_DIR="${OUT_DIR}" python3 - <<'PY'
import json
import os
from pathlib import Path

data = Path(os.environ["DATAMATE_DATA_DIR"])
out = Path(os.environ["DATAMATE_OUT_DIR"])
out.mkdir(parents=True, exist_ok=True)
qpath = data / "questions.jsonl"
ids = []
if qpath.is_file():
    for line in qpath.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        ids.append(json.loads(line)["id"])
sub = out / "submission.jsonl"
with sub.open("w", encoding="utf-8") as fh:
    for qid in ids:
        fh.write(json.dumps({"id": qid, "type": "abstain"}, ensure_ascii=False) + "\n")
print(f"wrote all-abstain submission ({len(ids)} lines) -> {sub}")
PY
}

run_fastcore_fallback() {
  echo "Running FastCore deterministic CPU fallback -> ${OUT_DIR}/submission.jsonl ..."
  if ! python3 -m datamate.predict \
    --data-dir "${DATA_DIR}" \
    --out-dir "${OUT_DIR}" \
    --system fastcore \
    --workers "${WORKERS}" \
    --time-budget-s "${TIME_BUDGET_S}"; then
    write_all_abstain
  fi
}

VLLM_PID=""
PREDICT_PID=""
cleanup() {
  if [[ -n "${PREDICT_PID}" ]] && kill -0 "${PREDICT_PID}" 2>/dev/null; then
    kill "${PREDICT_PID}" 2>/dev/null || true
    wait "${PREDICT_PID}" 2>/dev/null || true
  fi
  if [[ -n "${VLLM_PID}" ]] && kill -0 "${VLLM_PID}" 2>/dev/null; then
    kill "${VLLM_PID}" 2>/dev/null || true
    wait "${VLLM_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM

if [[ "${SYSTEM_MODE}" == "fastcore" ]]; then
  run_fastcore_fallback
  exit 0
fi

if [[ ! -d "${MODEL_DIR}" ]]; then
  echo "WARNING: model dir missing at ${MODEL_DIR}; falling back to FastCore deterministic mode" >&2
  run_fastcore_fallback
  exit 0
fi

echo "Starting vLLM (${SERVED_NAME}) on 127.0.0.1:${VLLM_PORT} tp=${TP_SIZE} ..."
vllm serve "${MODEL_DIR}" \
  --served-model-name "${SERVED_NAME}" \
  --host 127.0.0.1 \
  --port "${VLLM_PORT}" \
  --tensor-parallel-size "${TP_SIZE}" \
  --max-model-len 16384 \
  --gpu-memory-utilization "${GPU_UTIL}" \
  --max-num-seqs "${MAX_SEQS}" \
  --seed 0 \
  --enable-prefix-caching \
  --reasoning-parser qwen3 \
  >"${OUT_DIR}/vllm.log" 2>&1 &
VLLM_PID=$!

echo "Waiting for vLLM /v1/models (max ${VLLM_WAIT_S}s) ..."
ready=0
elapsed=0
while [[ "${elapsed}" -lt "${VLLM_WAIT_S}" ]]; do
  if ! kill -0 "${VLLM_PID}" 2>/dev/null; then
    echo "ERROR: vLLM exited before becoming ready; see ${OUT_DIR}/vllm.log" >&2
    break
  fi
  if curl -sf "http://127.0.0.1:${VLLM_PORT}/v1/models" >/dev/null; then
    ready=1
    break
  fi
  sleep 1
  elapsed=$((elapsed + 1))
done

if [[ "${ready}" -ne 1 ]]; then
  echo "WARNING: vLLM failed to start within ${VLLM_WAIT_S}s; falling back to FastCore deterministic mode" >&2
  run_fastcore_fallback
  exit 0
fi

echo "vLLM ready; running predict (--system ${SYSTEM_MODE}) ..."
set +e
python3 -m datamate.predict \
  --data-dir "${DATA_DIR}" \
  --out-dir "${OUT_DIR}" \
  --system "${SYSTEM_MODE}" \
  --workers "${WORKERS}" \
  --time-budget-s "${TIME_BUDGET_S}" &
PREDICT_PID=$!
wait "${PREDICT_PID}"
predict_rc=$?
PREDICT_PID=""
set -e

cleanup
trap - EXIT

exit "${predict_rc}"
