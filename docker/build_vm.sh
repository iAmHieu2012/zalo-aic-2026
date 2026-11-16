#!/usr/bin/env bash
# Build the submission image on a fresh Ubuntu 22.04 cloud VM (no GPU needed, >= 200 GB disk).
#   TEAM=<team_name> [TRAIN_URL=<Drive link to train.zip>] bash build_vm.sh
# Output: ~/build-<branch>/zaic2026_datamate_<team>.tar.gz, its .md5 (send to the organizers), .sha256,
# and .tar_bytes (uncompressed .tar size to send). Do not rename the archive afterwards.
set -euo pipefail
SELF="$(readlink -f "$0")"

TEAM="${TEAM:?set TEAM=<team_name>}"
BRANCH="${BRANCH:-main}"
BASE_REPO="${BASE_REPO:-Qwen/Qwen3-14B-FP8}"
BASE_REV="${BASE_REV:-9a283b4a5efbc09ce247e0ae5b02b744739e525a}"  # pinned; see docker/manifest_meta.json
TRAIN_URL="${TRAIN_URL-}"  # optional: link to train.zip (Drive or direct), packaged under /code/training_code/train
LORA_URL="${LORA_URL-}"  # this branch has no LoRA support; leave empty
IMG="zaic2026_datamate_${TEAM}:final"
# One folder per branch, so builds of different branches never overwrite each other;
# the file name itself stays as the guideline requires.
OUT="${OUT:-${HOME}/build-${BRANCH}/zaic2026_datamate_${TEAM}.tar.gz}"
mkdir -p "$(dirname "${OUT}")"

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
# Always run the build script of the branch being built (its model / LoRA defaults),
# whichever copy of this file was started.
if [[ -z "${BUILD_VM_REEXEC:-}" ]] && ! cmp -s "${SELF}" docker/build_vm.sh; then
  export BUILD_VM_REEXEC=1 TEAM BRANCH
  exec bash docker/build_vm.sh
fi

BASE_DIR="docker/models/$(basename "${BASE_REPO}")"
# Only this build's weights go into the image: drop leftovers of an earlier build on the same VM.
mkdir -p docker/models
find docker/models -mindepth 1 -maxdepth 1 ! -name "$(basename "${BASE_REPO}")" ! -name lora-parse -exec rm -rf {} +
[[ -z "${LORA_URL}" ]] && rm -rf docker/models/lora-parse
hf download "${BASE_REPO}" --revision "${BASE_REV}" --local-dir "${BASE_DIR}"
if [[ -n "${TRAIN_URL}" ]]; then
  # TRAIN_URL: link (Google Drive or direct, e.g. the organizers' train.zip) to ONE archive of the split.
  find docker/train_data -mindepth 1 ! -name .gitkeep -exec rm -rf {} +
  rm -rf /tmp/train_pkg && mkdir -p /tmp/train_pkg
  if [[ "${TRAIN_URL}" == *drive.google.com* ]]; then
    gdown --fuzzy "${TRAIN_URL}" -O /tmp/train_pkg/
  else
    curl -fL "${TRAIN_URL}" -o "/tmp/train_pkg/$(basename "${TRAIN_URL%%\?*}")"
  fi
  python3 -c "import glob,shutil; shutil.unpack_archive(glob.glob('/tmp/train_pkg/*')[0], '/tmp/train_pkg/x')"
  src="$(dirname "$(find /tmp/train_pkg/x -name questions.jsonl | head -1)")"
  test -f "${src}/questions.jsonl" && cp -r "${src}/." docker/train_data/ && rm -rf /tmp/train_pkg
fi
if [[ -n "${LORA_URL}" ]]; then
  gdown --folder "${LORA_URL}" -O docker/models/lora-parse
  test -f docker/models/lora-parse/adapter_config.json
fi
du -sh docker/models/*

sudo docker build -f docker/Dockerfile -t "${IMG}" .
sudo docker run --rm --entrypoint bash "${IMG}" -c \
  'ls /models /code /code/training_code && test -f /code/README.md && test -f /code/training_code/README.md \
   && python3 -c "import json; m=json.load(open(\"/code/training_code/data_manifest.json\")); print(m[\"n_files\"], \"files in manifest\")" \
   && python3 -c "import datamate, vllm; print(\"image ok\", vllm.__version__)"'

# Free disk before export: the weights are inside the image now; drop downloaded weights,
# build cache and any archive left by an earlier failed run (a 200 GB disk filled up here).
rm -rf docker/models
sudo docker builder prune -af >/dev/null
rm -f "${OUT}" "${OUT}".md5 "${OUT}".sha256 "${OUT}".tar_bytes
df -h "$(dirname "${OUT}")"
set -o pipefail
sudo docker save "${IMG}" | pigz -1 > "${OUT}"
cd "$(dirname "${OUT}")"
md5sum "$(basename "${OUT}")" | tee "$(basename "${OUT}").md5"
sha256sum "$(basename "${OUT}")" | tee "$(basename "${OUT}").sha256"
pigz -dc "$(basename "${OUT}")" | wc -c | tee "$(basename "${OUT}").tar_bytes"
ls -lh "${OUT}"
