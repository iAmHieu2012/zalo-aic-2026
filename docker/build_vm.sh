#!/usr/bin/env bash
# Build the submission image on a fresh Ubuntu 22.04 cloud VM (no GPU needed, >= 200 GB disk).
#   TEAM=<team_name> [OUT=~/name.tar.gz] bash build_vm.sh
# Output: ~/zaic2026_datamate_<team>.tar.gz and its .sha256.
set -euo pipefail

TEAM="${TEAM:?set TEAM=<team_name>}"
BRANCH="${BRANCH:-main}"
BASE_REPO="${BASE_REPO:-Qwen/Qwen3-14B-FP8}"
LORA_URL="${LORA_URL-}"  # this branch has no LoRA support; leave empty
IMG="zaic2026_datamate_${TEAM}:final"
OUT="${OUT:-${HOME}/zaic2026_datamate_${TEAM}.tar.gz}"  # set OUT to keep an earlier .tar.gz

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh   # Docker Engine + buildx
fi
sudo apt-get update -y && sudo apt-get install -y git pigz python3-pip
pip3 install --user -q -U "huggingface_hub[cli,hf_transfer]" gdown
export PATH="${HOME}/.local/bin:${PATH}" HF_HUB_ENABLE_HF_TRANSFER=1

cd "${HOME}"
[[ -d zalo-aic-2026 ]] || git clone -b "${BRANCH}" https://github.com/iAmHieu2012/zalo-aic-2026.git
cd zalo-aic-2026
git fetch origin && git checkout "${BRANCH}" && git pull --ff-only

BASE_DIR="docker/models/$(basename "${BASE_REPO}")"
# Only this build's weights go into the image: drop leftovers of an earlier build on the same VM.
mkdir -p docker/models
find docker/models -mindepth 1 -maxdepth 1 ! -name "$(basename "${BASE_REPO}")" ! -name lora-parse -exec rm -rf {} +
[[ -z "${LORA_URL}" ]] && rm -rf docker/models/lora-parse
hf download "${BASE_REPO}" --local-dir "${BASE_DIR}"
if [[ -n "${LORA_URL}" ]]; then
  gdown --folder "${LORA_URL}" -O docker/models/lora-parse
  test -f docker/models/lora-parse/adapter_config.json
fi
du -sh docker/models/*

sudo docker build -f docker/Dockerfile -t "${IMG}" .
sudo docker run --rm --entrypoint bash "${IMG}" -c \
  'ls /models /code && python3 -c "import datamate, vllm; print(\"image ok\", vllm.__version__)"'

sudo docker save "${IMG}" | pigz -1 > "${OUT}"
sha256sum "${OUT}" | tee "${OUT}.sha256"
ls -lh "${OUT}"
