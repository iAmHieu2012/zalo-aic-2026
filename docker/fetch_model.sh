#!/usr/bin/env bash
# Download base weights into docker/models/<name>/ (not committed).
# Run once on a machine with network before `docker build`.
#   bash docker/fetch_model.sh                           # Qwen/Qwen3-14B-FP8 (no LoRA)
#   DATAMATE_HF_REPO=Qwen/Qwen3-14B bash docker/fetch_model.sh   # BF16 base for the LoRA parser
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="${DATAMATE_HF_REPO:-Qwen/Qwen3-14B-FP8}"
# Pinned revisions (docker/manifest_meta.json); override with DATAMATE_HF_REV.
case "${REPO}" in
  Qwen/Qwen3-14B) DEFAULT_REV=40c069824f4251a91eefaf281ebe4c544efd3e18 ;;
  *) DEFAULT_REV=9a283b4a5efbc09ce247e0ae5b02b744739e525a ;;
esac
REV="${DATAMATE_HF_REV:-${DEFAULT_REV}}"
DEST="${ROOT}/models/$(basename "${REPO}")"

mkdir -p "${DEST}"
if command -v huggingface-cli >/dev/null 2>&1; then
  huggingface-cli download "${REPO}" --revision "${REV}" --local-dir "${DEST}" --local-dir-use-symlinks False
elif command -v hf >/dev/null 2>&1; then
  hf download "${REPO}" --revision "${REV}" --local-dir "${DEST}"
else
  python3 - <<PY
from huggingface_hub import snapshot_download
snapshot_download(repo_id="${REPO}", revision="${REV}", local_dir=r"${DEST}", local_dir_use_symlinks=False)
print("downloaded ${REPO} -> ${DEST}")
PY
fi

echo "Model ready at ${DEST}"
echo "LoRA parser: copy the adapter (adapter_config.json, adapter_model.safetensors) to docker/models/lora-parse/"
echo "Next: docker build -f docker/Dockerfile -t zaic2026_datamate_team:final ."
