# DataMate Offline Docker Package (Private Test / 2 × RTX 5090)

Gói Docker nộp bài theo chuẩn **Zalo AI Challenge 2026 — DataMate Track** ([`docs/competition/RULE.MD`](../docs/competition/RULE.MD)):
- **Phần cứng chấm bài (Rule 7):** `2 × NVIDIA RTX 5090` (32 GB VRAM mỗi card, Blackwell / `sm_120`, CUDA ≥ 12.8),
  512 GB RAM, tối đa **6 giờ** wall-clock (tính cả load model), `--network none`, `/data` read-only, `/result` writable.
- **Tái lập (Rule 8):** `|PA(uploaded) − PA(re-run)| ≤ 0.03`.
- **Nộp (SUBMISSION_GUIDANCE):** file Docker + checksum + link Google Drive công khai, qua form "Solution Submission".
- **Lệnh chấm chuẩn của BTC:**
  ```bash
  docker run --rm --gpus '"device=0,1"' --network none --shm-size=16g \
    --entrypoint bash \
    -v /path/to/test:/data:ro \
    -v /path/to/output:/result \
    zaic2026_datamate_<team_name>:final /code/predict.sh
  ```

---

## 1. Bản Đã Nộp

| | |
|---|---|
| Image | `zaic2026_datamate_fithcmus-09:final` |
| Code | branch `lora-parser`, commit `a086cb0` |
| Base model | `Qwen/Qwen3-14B` (BF16, 28 GB), tensor parallel 2 |
| Adapter | `lora-parse` (LoRA rank 16, 256 MB), served as `datamate-parse` |
| vLLM | `vllm/vllm-openai:v0.32.0` |
| File | `zaic2026_datamate_fithcmus-09.tar.gz`, 31 GB (30.5 GiB) |
| Link | https://drive.google.com/open?id=17Zujnk-CkMZRL3NrCgyqSlVPdhlbsG-L |
| MD5 | `29a45cc6bd81699c3485dde278bf9841` |
| SHA256 | `47c11e1fbfd4d1c6b652e94e7d1a1a493cc7450f9f07f7830fe4918814d377b2` |
| Public PA của cấu hình này | 0.629 (chạy qua Colab, `result/20261114_qwen3_lora`) |

Image **chưa chạy với GPU** (VM build không có GPU). Đã kiểm tra: build thành công, `image ok 0.32.0`
(import được `datamate`, `vllm`), `/models` có `Qwen3-14B` và `lora-parse`, `/code` có `predict.sh` và `training_code`.

---

## 2. Bên Trong Image

| Đường dẫn | Nội dung |
|---|---|
| `/models/Qwen3-14B/` | Weights base (từ `docker/fetch_model.sh` / `build_vm.sh`) |
| `/models/lora-parse/` | Adapter LoRA (`adapter_config.json`, `adapter_model.safetensors`) |
| `/app/` | Mã nguồn đã cài (`src/`, `rules/`, `evals/`, `lora/`) |
| `/code/predict.sh` | Entrypoint chấm bài |
| `/code/training_code/` | `src/`, `rules/`, `lora/` (sinh nhãn + train QLoRA), `evals/`, `pyproject.toml`, `data_manifest.json` |

`train/` là dữ liệu của BTC, bị `.gitignore` nên **không có trong image** (`/app/train` rỗng). Lúc chạy pipeline
đọc `/data/rulebook.md` của split đang chấm. `lora/data/labels.jsonl` (nhãn train) cũng không có trong image;
tái tạo bằng `python -m lora.build_labels` (xem `docs/PIPELINE.md` mục 6).

### Biến môi trường mặc định (`ENV` trong Dockerfile)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `DATAMATE_MODEL_DIR` | `/models/Qwen3-14B` | Base model cho vLLM |
| `DATAMATE_LORA_DIR` | `/models/lora-parse` | Có `adapter_config.json` → bật LoRA |
| `DATAMATE_TP_SIZE` | `2` | Tensor parallel (BF16 14B không vừa một card 32 GB kèm KV cache) |
| `LLM_MODEL` | `qwen3-14b` | Tên model base trong vLLM |
| `LLM_DISABLE_THINKING` | `true` | Tắt thinking ở lệnh gọi thường |
| `DATAMATE_WORKERS` | `8` | Số câu chạy song song |
| `DATAMATE_TIME_BUDGET_S` | `18900` | 5 giờ 15 phút cho predict |
| `DATAMATE_GPU_UTIL` / `DATAMATE_MAX_NUM_SEQS` | `0.90` / `16` | Tham số vLLM |
| `DATAMATE_VLLM_WAIT_S` | `900` | Thời gian chờ vLLM lên tối đa |

Cảnh báo `SecretsUsedInArgOrEnv` (ENV `LLM_API_KEY`) khi build là vô hại: giá trị là `EMPTY`, chỉ dùng cho vLLM nội bộ.

---

## 3. `predict.sh` Làm Gì

1. Nếu `DATAMATE_MODEL_DIR` không tồn tại → ghi `submission.jsonl` toàn `abstain` (điểm 0, không âm), thoát.
2. Nếu `DATAMATE_LORA_DIR/adapter_config.json` có → thêm `--enable-lora --lora-modules datamate-parse=<dir>
   --max-lora-rank 16 --max-loras 1` và `export LLM_PARSE_MODEL=datamate-parse` (parser chính + parser mở rộng dùng
   adapter, các bước khác dùng base). Không có → chạy base như cũ.
3. `vllm serve` trên `127.0.0.1:8000` (`--max-model-len 16384 --seed 0 --enable-prefix-caching --reasoning-parser qwen3`),
   log ở `/result/vllm.log`.
4. Chờ `/v1/models` (tối đa 900 s). Không lên → toàn `abstain`.
5. `python3 -m datamate.predict --data-dir /data --out-dir /result --system pipeline_llm`.

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

## 4. Build Trên Máy Ảo (cách đã dùng)

Máy local không đủ ổ đĩa, nên build trên Google Cloud (tài khoản mới có 300 USD credit dùng thử). Không cần GPU.

1. **Tạo VM:** Compute Engine → VM instances → Create instance: `asia-southeast1`, `e2-standard-4`,
   Ubuntu 22.04 LTS, Balanced persistent disk **200 GB**. Mở terminal bằng nút **SSH**.
2. **Chạy script** — lệnh đã dùng, chạy thẳng trong tab SSH (giữ tab mở tới khi xong):
   ```bash
   curl -fsSL https://raw.githubusercontent.com/iAmHieu2012/zalo-aic-2026/lora-parser/docker/build_vm.sh -o build_vm.sh && TEAM=fithcmus-09 bash build_vm.sh
   ```
   Lần đầu dừng ở `COPY train/rulebook.md` (đã sửa ở `a086cb0`); chạy lại `TEAM=fithcmus-09 bash build_vm.sh` là đủ.
   Đóng tab SSH hoặc rớt mạng sẽ dừng build. Muốn bỏ máy đi được thì chạy trong `tmux` (tuỳ chọn, lần này không dùng):
   `tmux new -s build`, chạy lệnh trên thêm `2>&1 | tee build.log`, thoát bằng `Ctrl+B` rồi `D`,
   vào lại bằng `tmux attach -t build`.
   - `TEAM` phải **viết thường** (Docker không nhận chữ hoa trong tên image).
   - Biến tuỳ chọn: `BRANCH` (mặc định `lora-parser`), `BASE_REPO` (`Qwen/Qwen3-14B`), `LORA_URL` (thư mục Drive
     chứa adapter, chia sẻ "Anyone with the link"; để rỗng = không LoRA).
3. **Script làm:** cài Docker (get.docker.com) + `git pigz pip` → clone branch → `hf download` base → `gdown --folder`
   adapter → `docker build` → chạy thử import trong image → `docker save | pigz -1` → `sha256sum`.
   Chạy lại được: weights đã tải thì bỏ qua, code tự `git pull`.
4. **Thời gian đo được:** build 2.116 s (~35 phút, gần hết là export layer 30 GB), file nén 31 GB.
5. **Xong khi** màn hình in `image ok 0.32.0`, một dòng `sha256` và `ls -lh` của `.tar.gz`.

### Kiểm tra thêm (không cần GPU)

```bash
IMG=zaic2026_datamate_fithcmus-09:final
# nội dung image
sudo docker run --rm --entrypoint bash $IMG -c 'du -sh /models/*; ls /models/lora-parse /code; env | grep -E "DATAMATE_|LLM_"'
# luồng predict.sh với dữ liệu giả: không GPU → vLLM không lên → phải ra 1 dòng abstain
mkdir -p ~/fake_data ~/fake_out
echo '{"id":"q_test1","business_id":"x","question":"test","as_of_date":"2026-01-01"}' > ~/fake_data/questions.jsonl
sudo docker run --rm --network none --entrypoint bash -v ~/fake_data:/data:ro -v ~/fake_out:/result $IMG /code/predict.sh
cat ~/fake_out/submission.jsonl
# file nén nguyên vẹn
pigz -t ~/zaic2026_datamate_fithcmus-09.tar.gz && echo "tar.gz OK"
```

### Chạy thật với GPU

Cần 2 card ≥ 32 GB (như BTC), hoặc 1 card 80 GB với `-e DATAMATE_TP_SIZE=1`. Dùng đúng lệnh chấm của BTC ở đầu file,
mount `train/` vào `/data` để chấm được bằng `evals`. Colab không chạy được Docker.

---

## 5. Upload Lên Google Drive & Checksum

Cách đã chạy được (không cần menu `rclone config`):

| Bước | Chạy ở đâu |
|---|---|
| `rclone authorize "drive"` | **Máy thật** (có trình duyệt) |
| Ghi `rclone.conf`, `rclone lsd`, `rclone copy`, `rclone link`, `md5sum` | **Máy ảo** (nơi có file `.tar.gz`) |

1. **[Máy thật] Lấy token** (cần cài rclone, vd. `sudo pacman -S rclone`):
   ```bash
   rclone authorize "drive"      # trình duyệt mở → đăng nhập Google → Allow → terminal in {"access_token":...}
   ```
   Copy nguyên đoạn `{...}` (kể cả hai dấu ngoặc nhọn).
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
   cd ~ && rclone copy zaic2026_datamate_fithcmus-09.tar.gz gdrive:datamate_submit -P
   rclone link gdrive:datamate_submit/zaic2026_datamate_fithcmus-09.tar.gz
   ```
4. **Checksum** — form nộp bài đòi **MD5**:
   - [Máy ảo] `md5sum ~/zaic2026_datamate_fithcmus-09.tar.gz` hoặc `rclone md5sum gdrive:datamate_submit`.
   - [Colab] Khi đã xoá máy ảo / gỡ rclone (cách đã dùng): một cell Colab đọc MD5 Drive lưu sẵn:
     ```python
     from google.colab import auth; auth.authenticate_user()
     from googleapiclient.discovery import build
     print(build("drive","v3").files().get(fileId="<FILE_ID>", fields="md5Checksum,size").execute())
     ```
   Lấy MD5 **trước** khi gỡ rclone và xoá VM.
5. **[Máy thật, trình duyệt] Dọn dẹp:** mở link trong tab ẩn danh để chắc tải được; thu hồi quyền rclone tại
   https://myaccount.google.com/permissions; xoá máy ảo (Compute Engine → VM instances → Delete).

---

## 6. Biến Thể FP8, Không LoRA (bản gốc, public 0.651)

```bash
TEAM=<team> BRANCH=main BASE_REPO=Qwen/Qwen3-14B-FP8 LORA_URL= bash build_vm.sh
```
Branch `main` dùng Dockerfile cũ (mặc định `/models/Qwen3-14B-FP8`, 1 GPU) và vẫn có dòng `COPY train/rulebook.md`,
nên cần bỏ dòng đó như commit `a086cb0` trước khi build. Trên `lora-parser` thì đổi `ENV` trong Dockerfile thành
`DATAMATE_MODEL_DIR=/models/Qwen3-14B-FP8`, `DATAMATE_TP_SIZE=1` và không tải adapter. Image khoảng 25–30 GB.

## Nội dung bắt buộc theo Docker guideline (mục 4, 8, 11)

| Trong image | Nguồn trong repo |
|---|---|
| `/code/README.md` | `docker/CODE_README.md` (cách làm, model + revision cố định, license, số tham số, dữ liệu) |
| `/code/training_code/README.md` | `docker/TRAINING_README.md` |
| `/code/training_code/data_manifest.json` | `docker/make_manifest.py` + `docker/manifest_meta.json` (SHA-256 từng file, base model URL/revision/license) |
| `/code/training_code/checkpoints/lora-parse/` | adapter (bản sao của `/models/lora-parse`), cùng `lora/` (sinh nhãn, train, nhãn) và `notebooks/train_lora.ipynb` |
| `/code/training_code/train/` | tập train của BTC nếu build với `TRAIN_URL=<link Drive tới train.zip>` |

Build trên VM: `TEAM=<team> [TRAIN_URL=...] bash docker/build_vm.sh`. Kết quả gửi BTC:
`zaic2026_datamate_<team>.tar.gz` (không đổi tên sau khi tạo `.md5`), file `.md5`, và số byte `.tar`
chưa nén trong file `.tar_bytes`.
