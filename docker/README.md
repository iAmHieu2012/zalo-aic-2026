# DataMate Offline Docker Package (Private Test / 2 × RTX 5090)

Gói Docker nộp bài theo đúng chuẩn **Zalo AI Challenge 2026 — DataMate Track** ([`docs/competition/RULE.MD`](../docs/competition/RULE.MD)):
- **Phần cứng chấm bài (Rule 7):** `2 × NVIDIA RTX 5090` (**32 GB VRAM mỗi card, tổng 64 GB VRAM**, kiến trúc Blackwell / `sm_120`, **CUDA ≥ 12.8**), **512 GB RAM**, thời gian chạy tối đa **6 giờ** wall-clock (tính cả thời gian load model), `--network none`, `/data` read-only, `/result` writable.
- **Yêu cầu tái lập kết quả (Rule 8):** Điểm lệch giữa lần chạy nộp `submission.jsonl` và lần BTC chạy lại Docker trên `2 × RTX 5090` phải thoả mãn `|PA(uploaded) − PA(re-run)| ≤ 0.03`.
- **Lệnh chấm chuẩn của BTC:**
  ```bash
  docker run --rm \
    --gpus '"device=0,1"' \
    --network none \
    --shm-size=16g \
    --entrypoint bash \
    -v /path/to/test:/data:ro \
    -v /path/to/output:/result \
    zaic2026_datamate_<team_name>:final /code/predict.sh
  ```

## 1. Tải Trọng Số Model Trước Khi Build Image

Chạy trên máy/VM có kết nối mạng trước khi `docker build`:

```bash
bash docker/fetch_model.sh
```

Lệnh này tải `Qwen/Qwen3-14B-FP8` vào `docker/models/Qwen3-14B-FP8/`.

## 2. Build Docker Image

```bash
docker build -f docker/Dockerfile -t zaic2026_datamate_<team_name>:final .
```

## 3. Kiểm Tra Offline Trước Khi Nộp

```bash
docker run --rm \
  --gpus '"device=0,1"' \
  --network none \
  --shm-size=16g \
  --entrypoint bash \
  -v "$(pwd)/train:/data:ro" \
  -v "$(pwd)/docker_out:/result" \
  zaic2026_datamate_<team_name>:final /code/predict.sh
```

## 4. Cấu Trúc Đầu Ra Trong `/result`

| Đường dẫn | Nội dung |
|---|---|
| `/result/submission.jsonl` | Mỗi câu hỏi 1 dòng JSON đúng thứ tự `questions.jsonl`, ghi incremental + fsync |
| `/result/logs/log.jsonl` | File log JSONL tổng hợp gồm `id, answer, elapsed_ms, thinking, code, inputs, output` |
| `/result/logs/<qid>.json` | File log chi tiết cho từng câu hỏi |
| `/result/timing.json` | Thống kê thời gian chạy thực tế |
| `/result/work/` | Thư mục cache tạm của DuckDB & LLM (tuyệt đối không ghi vào `/data`) |

## Nội dung bắt buộc theo Docker guideline (mục 4, 8, 11)

| Trong image | Nguồn trong repo |
|---|---|
| `/code/README.md` | `docker/CODE_README.md` (cách làm, model + revision cố định, license, số tham số, dữ liệu) |
| `/code/training_code/README.md` | `docker/TRAINING_README.md` |
| `/code/training_code/data_manifest.json` | `docker/make_manifest.py` + `docker/manifest_meta.json` (SHA-256 từng file, base model URL/revision/license) |
| `/code/training_code/train/` | tập train của BTC nếu build với `TRAIN_URL=<link Drive tới train.zip>` |

Build trên VM: `TEAM=<team> [TRAIN_URL=...] bash docker/build_vm.sh`. Kết quả gửi BTC:
`zaic2026_datamate_<team>.tar.gz` (không đổi tên sau khi tạo `.md5`), file `.md5`, và số byte `.tar`
chưa nén trong file `.tar_bytes`.
