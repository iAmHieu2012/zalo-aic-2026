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

Máy local không đủ ổ đĩa, nên build trên Google Cloud (tài khoản mới có 300 USD credit dùng thử). Không cần GPU.

1. **[Máy thật, trình duyệt] Tạo VM:** Compute Engine → VM instances → Create instance: `asia-southeast1`,
   `e2-standard-4`, Ubuntu 22.04 LTS, Balanced persistent disk **200 GB**. Mở terminal bằng nút **SSH**.
2. **[Máy ảo] Tải script và build** (giữ tab SSH mở tới khi xong). Chép `build_vm.sh` của branch nào cũng được:
   script tự clone repo, checkout `BRANCH`, rồi chạy `build_vm.sh` của chính branch đó.
   ```bash
   curl -fsSL https://raw.githubusercontent.com/iAmHieu2012/zalo-aic-2026/main/docker/build_vm.sh -o build_vm.sh
   TEAM=fithcmus-09 bash build_vm.sh                         # FP8 gốc      → ~/build-main/
   TEAM=fithcmus-09 BRANCH=main-robust bash build_vm.sh      # FP8 + telex  → ~/build-main-robust/
   TEAM=fithcmus-09 BRANCH=lora-parser bash build_vm.sh      # BF16 + LoRA  → ~/build-lora-parser/
   ```
   - `TEAM` phải **viết thường** (Docker không nhận chữ hoa trong tên image).
   - Đóng tab SSH hoặc rớt mạng sẽ dừng build. Muốn bỏ máy đi được thì chạy trong `tmux`:
     `tmux new -s build`, chạy lệnh build thêm `2>&1 | tee build.log`, thoát bằng `Ctrl+B` rồi `D`,
     vào lại bằng `tmux attach -t build`.
   - Chạy lại được: weights đã tải thì bỏ qua, code tự `git pull`.
   - Biến tuỳ chọn: `BASE_REPO` / `BASE_REV` (đổi model), `LORA_URL` (thư mục Drive chứa adapter, chỉ
     `lora-parser`), `TRAIN_URL` (link Drive tới `train.zip`, đóng gói vào `/code/training_code/train/`; chỉ cần
     cho `lora-parser` vì có train, `main` / `main-robust` không train nên không cần).
3. **Script làm:** cài Docker + `git pigz pip hf gdown` → clone, checkout branch → tải weights đúng revision
   (`lora-parser` tải thêm adapter) → `docker build` → kiểm tra image có `/models`, `/code/README.md`,
   `/code/training_code/README.md`, `data_manifest.json`, import được `datamate`, `vllm` →
   `docker save | pigz -1` → ghi `.md5`, `.sha256`, `.tar_bytes`.
4. **Thời gian đo được** (bản `lora-parser`): build ~35 phút, gần hết là export layer 30 GB; file nén 31 GB.
   Bản FP8 khoảng 21 GB.
5. **Xong khi** màn hình in `image ok 0.32.0`, dòng MD5, dòng SHA256, số byte `.tar` và `ls -lh` của `.tar.gz`.
   Kết quả nằm trong `~/build-<branch>/`; mỗi branch một thư mục nên build nhiều bản không ghi đè nhau.
   **Không đổi tên file `.tar.gz`** sau khi đã tạo `.md5`.

### Kiểm tra thêm (không cần GPU)

```bash
# [Máy ảo]
IMG=zaic2026_datamate_fithcmus-09:final
# nội dung image
sudo docker run --rm --entrypoint bash $IMG -c 'du -sh /models/*; ls /code /code/training_code; env | grep -E "DATAMATE_|LLM_"'
# luồng predict.sh với dữ liệu giả: không GPU → vLLM không lên → phải ra 1 dòng abstain
mkdir -p ~/fake_data ~/fake_out
echo '{"id":"q_test1","business_id":"x","question":"test","as_of_date":"2026-01-01"}' > ~/fake_data/questions.jsonl
sudo docker run --rm --network none --entrypoint bash -v ~/fake_data:/data:ro -v ~/fake_out:/result $IMG /code/predict.sh
cat ~/fake_out/submission.jsonl
# file nén nguyên vẹn
pigz -t ~/build-main/zaic2026_datamate_fithcmus-09.tar.gz && echo "tar.gz OK"
```

### Chạy thật với GPU

Cần 2 card ≥ 32 GB (như BTC), hoặc 1 card 80 GB (bản `lora-parser` thêm `-e DATAMATE_TP_SIZE=1`).
Dùng đúng lệnh chấm của BTC ở đầu file, mount `train/` vào `/data` để chấm được bằng `evals`
(xem mục 6). Colab không chạy được Docker.

---

## 3. Upload lên Google Drive và nộp

Cách đã chạy được (không cần menu `rclone config`):

| Bước | Chạy ở đâu |
|---|---|
| `rclone authorize "drive"` | **Máy thật** (có trình duyệt) |
| Ghi `rclone.conf`, `rclone lsd`, `rclone copy`, `rclone link` | **Máy ảo** (nơi có file `.tar.gz`) |

1. **[Máy thật] Lấy token** (cần cài rclone, vd. `sudo pacman -S rclone`):
   ```bash
   rclone authorize "drive"      # trình duyệt mở → đăng nhập Google → Allow → terminal in {"access_token":...}
   ```
   Copy nguyên đoạn `{...}` (kể cả hai dấu ngoặc nhọn). Token này là quyền truy cập Drive: không dán vào chat
   hay chỗ công khai.
2. **[Máy ảo] Ghi cấu hình**, dán token vào dòng `token =` (phải nằm trọn **một dòng**):
   ```bash
   mkdir -p ~/.config/rclone && cat > ~/.config/rclone/rclone.conf <<'EOF'
   [gdrive]
   type = drive
   scope = drive
   token = {"access_token":"...","token_type":"Bearer","refresh_token":"...","expiry":"..."}
   EOF
   rclone lsd gdrive:            # phải ra danh sách thư mục Drive
   ```
   Không dùng `rclone config create ... token=...`: lệnh này vẫn mở lại bước đăng nhập và chờ trình duyệt trên VM.
3. **[Máy ảo] Upload và lấy link công khai** (~15 phút, ~30 MiB/s):
   ```bash
   cd ~/build-main && rclone copy zaic2026_datamate_fithcmus-09.tar.gz gdrive:datamate_submit -P
   rclone link gdrive:datamate_submit/zaic2026_datamate_fithcmus-09.tar.gz
   cat zaic2026_datamate_fithcmus-09.tar.gz.md5 zaic2026_datamate_fithcmus-09.tar.gz.tar_bytes
   ```
   Hai bản từ hai branch trùng tên file: upload vào hai thư mục Drive khác nhau (vd. `datamate_submit_main`,
   `datamate_submit_lora`), không đổi tên file.
4. **Ghi lại MD5 và số byte `.tar` trước** khi gỡ rclone và xoá VM. Nếu lỡ xoá VM, đọc MD5 Drive lưu sẵn bằng
   một cell [Colab]:
   ```python
   from google.colab import auth; auth.authenticate_user()
   from googleapiclient.discovery import build
   print(build("drive","v3").files().get(fileId="<FILE_ID>", fields="md5Checksum,size").execute())
   ```
5. **[Máy thật] Kiểm tra link:** tải lại từ link trên một máy khác (hoặc mở tab ẩn danh), chạy
   `md5sum -c zaic2026_datamate_fithcmus-09.tar.gz.md5`, phải ra `OK`.
6. **Nộp** qua form "Solution Submission": link, dòng trong file `.md5`, số trong file `.tar_bytes`.
   Mỗi đội nộp tối đa 2 lần, BTC chấm bản nộp cuối.
7. **[Máy thật, trình duyệt] Dọn dẹp:** thu hồi quyền rclone tại https://myaccount.google.com/permissions;
   xoá máy ảo (Compute Engine → VM instances → Delete).

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
| `LLM_MODEL` (tên model trong vLLM) | `qwen3-14b` | `qwen3-14b` (adapter: `datamate-parse`) |
| `DATAMATE_GPU_UTIL` / `DATAMATE_MAX_NUM_SEQS` | `0.90` / `16` | `0.90` / `16` |
| `DATAMATE_VLLM_WAIT_S` | `900` | `900` |

Cảnh báo `SecretsUsedInArgOrEnv` (ENV `LLM_API_KEY`) khi build là vô hại: giá trị là `EMPTY`, chỉ dùng cho vLLM nội bộ.

### Đầu ra trong `/result`

| Đường dẫn | Nội dung |
|---|---|
| `submission.jsonl` | Mỗi câu 1 dòng, đúng thứ tự `questions.jsonl`, ghi dần + fsync |
| `logs/log.jsonl` | Log tổng hợp: `id, answer, elapsed_ms, thinking, code, inputs, output` |
| `logs/<qid>.json` | Log chi tiết từng câu |
| `timing.json` | Thời gian chạy |
| `vllm.log` | Log vLLM |
| `work/` | Cache DuckDB và LLM (không ghi vào `/data`) |

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
