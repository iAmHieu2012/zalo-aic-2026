# Docker nộp bài — DataMate (Zalo AI Challenge 2026)

Image chạy offline trên máy chấm của BTC: 2 × RTX 5090 (32 GB mỗi card), không mạng, tối đa 6 giờ.
BTC chạy lệnh:

```bash
docker run --rm --gpus '"device=0,1"' --network none --shm-size=16g --entrypoint bash \
  -v /path/to/test:/data:ro -v /path/to/output:/result \
  zaic2026_datamate_<team>:final /code/predict.sh
```

---

## 1. Ba bản build

| Branch | Model | Train | `BRANCH=` |
|---|---|---|---|
| `main` | `Qwen/Qwen3-14B-FP8` (revision `9a283b4`), 1 GPU | không | *(mặc định)* |
| `main-robust` | như `main` + giải telex, đọc thêm định dạng tiền/ngày | không | `main-robust` |
| `lora-parser` | `Qwen/Qwen3-14B` BF16 (revision `40c0698`) + adapter LoRA, 2 GPU | có (QLoRA) | `lora-parser` |

---

## 2. Build trên VM

VM Ubuntu 22.04, không cần GPU, ổ đĩa ≥ 200 GB. Chép `docker/build_vm.sh` của branch nào cũng được:
script tự clone repo, checkout `BRANCH`, rồi chạy `build_vm.sh` của chính branch đó.

```bash
# [Máy ảo]
TEAM=fithcmus-09 bash build_vm.sh                         # → ~/build-main/
TEAM=fithcmus-09 BRANCH=main-robust bash build_vm.sh      # → ~/build-main-robust/
TEAM=fithcmus-09 BRANCH=lora-parser bash build_vm.sh      # → ~/build-lora-parser/
```

Script làm theo thứ tự:
1. Cài Docker, `pigz`, `hf`, `gdown`.
2. Tải weights đúng revision đã cố định vào `docker/models/`. Riêng `lora-parser` tải thêm adapter từ Drive.
3. `docker build`, rồi kiểm tra image có `/models`, `/code/README.md`, `/code/training_code/README.md`,
   `data_manifest.json`, và import được `datamate`, `vllm`.
4. `docker save | pigz` ra `~/build-<branch>/zaic2026_datamate_<team>.tar.gz`, kèm:
   - `.md5`: gửi BTC.
   - `.tar_bytes`: số byte `.tar` chưa nén, gửi BTC (giới hạn 100 GB).
   - `.sha256`.

Mỗi branch ghi vào một thư mục riêng nên build nhiều bản trên cùng VM không ghi đè nhau.
**Không đổi tên file `.tar.gz`** sau khi đã tạo `.md5`.

Biến tuỳ chọn: `TRAIN_URL=<link Drive tới train.zip>` để đóng gói tập train vào `/code/training_code/train/`.
Chỉ cần cho `lora-parser` (có train); `main` và `main-robust` không train nên không cần.

---

## 3. Nộp

1. Upload `.tar.gz` lên Google Drive, để link công khai.
2. Tải lại từ link trên một máy khác, chạy `md5sum -c zaic2026_datamate_<team>.tar.gz.md5`, phải ra `OK`.
3. Gửi qua form "Solution Submission": link, dòng trong file `.md5`, số trong file `.tar_bytes`.
   Mỗi đội nộp tối đa 2 lần, BTC chấm bản nộp cuối.

---

## 4. Bên trong image

| Đường dẫn | Nội dung | Nguồn trong repo |
|---|---|---|
| `/code/predict.sh` | entrypoint, không tham số | `docker/predict.sh` |
| `/code/README.md` | cách làm, model + revision, license, số tham số, dữ liệu | `docker/CODE_README.md` |
| `/code/training_code/README.md` | đã train gì / không train gì | `docker/TRAINING_README.md` |
| `/code/training_code/data_manifest.json` | SHA-256 từng file, base model URL/revision/license | `docker/make_manifest.py` + `docker/manifest_meta.json` |
| `/code/training_code/` | `src/`, `rules/`, `evals/`, `pyproject.toml` (+ `scripts/` ở `main-robust`; + `lora/`, `checkpoints/lora-parse/`, notebook train ở `lora-parser`) | |
| `/models/` | weights (+ `lora-parse/` ở `lora-parser`) | `docker/models/` (không commit) |
| `/app/` | code đã cài thành package `datamate` | |

Các file cần chỉnh khi đổi model hoặc cách làm: `docker/CODE_README.md`, `docker/TRAINING_README.md`,
`docker/manifest_meta.json`, và `BASE_REPO` / `BASE_REV` trong `docker/build_vm.sh`.

---

## 5. `predict.sh`

1. Không có weights → ghi `submission.jsonl` toàn `abstain` (điểm 0), thoát.
2. Có `/models/lora-parse/adapter_config.json` (chỉ `lora-parser`) → bật LoRA, parser câu hỏi dùng adapter.
3. `vllm serve` trên `127.0.0.1:8000`: `--max-model-len 16384 --seed 0 --enable-prefix-caching`, log ở `/result/vllm.log`.
4. Chờ server lên (tối đa 900 s), không lên → toàn `abstain`.
5. `python3 -m datamate.predict --data-dir /data --out-dir /result --system pipeline_llm`: ghi từng câu
   vào `submission.jsonl` ngay khi trả lời, log mỗi câu ở `/result/logs/` (`id`, `answer`, `elapsed_ms`, `thinking`,
   `code`, `inputs`, `output`).

Cấu hình cố định trong image (BTC không đổi):

| Biến | `main` / `main-robust` | `lora-parser` |
|---|---|---|
| `DATAMATE_MODEL_DIR` | `/models/Qwen3-14B-FP8` | `/models/Qwen3-14B` |
| `DATAMATE_TP_SIZE` | `1` | `2` |
| `DATAMATE_WORKERS` | `8` | `8` |
| `DATAMATE_TIME_BUDGET_S` | `18900` (5 giờ 15 phút) | `18900` |
| `LLM_DISABLE_THINKING` | `true` | `true` |

---

## 6. Chạy thử trước khi nộp (cần máy có GPU)

```bash
docker run --rm --gpus '"device=0,1"' --network none --shm-size=16g --entrypoint bash \
  -v "$(pwd)/train:/data:ro" -v "$(pwd)/docker_out:/result" \
  zaic2026_datamate_fithcmus-09:final /code/predict.sh
python -m evals.check_submission --submission docker_out/submission.jsonl --split train
```

---

## 7. Các bản đã upload

| | Bản 1 | Bản 2 |
|---|---|---|
| Code | `lora-parser` @ `a086cb0` | `submit-main` @ `ee97804` (nay là `main`) |
| Model | Qwen3-14B BF16 + LoRA | Qwen3-14B-FP8 |
| Public PA | 0.629 | 0.651 |
| Link | https://drive.google.com/open?id=17Zujnk-CkMZRL3NrCgyqSlVPdhlbsG-L | https://drive.google.com/open?id=1d5xPxR6W3pH0vl8pptklzrn8XOEkzKI4 |
| MD5 | `29a45cc6bd81699c3485dde278bf9841` | `cd3244712f32af00845f5a3c34af0723` |

Cả hai bản build **trước khi** có `/code/README.md`, `training_code/README.md` và manifest đầy đủ.
Muốn đủ theo guideline thì phải build lại.
