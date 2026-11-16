#!/usr/bin/env bash
# Download Qwen3-14B-FP8 weights into docker/models/ (not committed).
# Run once on a machine with network before `docker build`.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
DEST="${ROOT}/models/Qwen3-14B-FP8"
REPO="${DATAMATE_HF_REPO:-Qwen/Qwen3-14B-FP8}"
REV="${DATAMATE_HF_REV:-9a283b4a5efbc09ce247e0ae5b02b744739e525a}"

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
echo "Next: docker build -f docker/Dockerfile -t zaic2026_datamate_team:final ."
