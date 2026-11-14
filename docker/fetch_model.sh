#!/usr/bin/env bash
# Download base weights into docker/models/<name>/ (not committed).
# Run once on a machine with network before `docker build`.
#   bash docker/fetch_model.sh                           # Qwen/Qwen3-14B-FP8 (no LoRA)
#   DATAMATE_HF_REPO=Qwen/Qwen3-14B bash docker/fetch_model.sh   # BF16 base for the LoRA parser
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="${DATAMATE_HF_REPO:-Qwen/Qwen3-14B-FP8}"
DEST="${ROOT}/models/$(basename "${REPO}")"

mkdir -p "${DEST}"
if command -v huggingface-cli >/dev/null 2>&1; then
  huggingface-cli download "${REPO}" --local-dir "${DEST}" --local-dir-use-symlinks False
elif command -v hf >/dev/null 2>&1; then
  hf download "${REPO}" --local-dir "${DEST}"
else
  python3 - <<PY
from huggingface_hub import snapshot_download
snapshot_download(repo_id="${REPO}", local_dir=r"${DEST}", local_dir_use_symlinks=False)
print("downloaded ${REPO} -> ${DEST}")
PY
fi

echo "Model ready at ${DEST}"
echo "LoRA parser: copy the adapter (adapter_config.json, adapter_model.safetensors) to docker/models/lora-parse/"
echo "Next: docker build -f docker/Dockerfile -t zaic2026_datamate_team:final ."
