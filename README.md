# Zalo AI Challenge 2026 — DataMate Track (Hybrid Agentic System)

Hệ thống **Hybrid DataMate (`datamate`)** giải quyết bài toán **Trợ lý Dữ liệu cho Hộ Kinh Doanh Việt Nam** với hàm mục tiêu **Penalized Accuracy (PA: Đúng $+1$, Từ chối $0$, Sai $-1$)**.

Thiết kế kết hợp ưu thế của 2 nhánh kiến trúc mạnh nhất:
1. **Tier 1 (`datamate.fastcore` — Deterministic Engine + Runtime Invariants):** Xử lý cực nhanh trên CPU với độ chính xác tuyệt đối (**Precision 99.7%**, **PA = 0.985 trên `dev`**, **PA = 0.859 trên `holdout`**, tổng **PA = 0.962 trên 3.000 câu `train`**).
2. **Tier 2 (`PipelineSystem` — `Qwen3-14B-FP8` + DuckDB Canonical ETL + Reverse Verifier + Thinking Retry):** Giải quyết các câu hỏi diễn đạt tự nhiên (paraphrase), quy tắc mới phát sinh trong `<split>/rulebook.md`, và câu hỏi không thể trả lời (`unanswerable`) với cơ chế kiểm chứng ngược (**Reverse Description Verification**) và bỏ phiếu đồng thuận (**2-Vote Self-Consistency**).

---

## 1. Kiến Trúc Hệ Thống (`HybridSystem` Cascade)

```text
Câu hỏi (question, business_id, as_of_date) + <split>/rulebook.md + <split>/data/<biz_id>/
 │
 ├─► [Tier 0: Dynamic Rulebook Diff Guard]
 │     So sánh tự động <split>/rulebook.md với train/rulebook.md.
 │     Nếu câu hỏi chứa thuật ngữ mới / quy tắc thay đổi định nghĩa ──► Chuyển thẳng sang Tier 2
 │
 ├─► [Tier 1: FastCore Deterministic Engine (CPU, ~10ms/câu)]
 │     ├─ Ingest siêu tốc bằng python-calamine (nhanh gấp 8.5x openpyxl)
 │     ├─ 3-Tier Schema Mapping + Runtime Invariant Checker (checks.py: 7,345 -> 0 lỗi)
 │     ├─ Chuẩn hoá Telex / VNI / teencode + Phân giải Âm/Dương lịch (timeparse)
 │     ├─ Vocabulary Coverage Gate (gate.py): Từ chối ngay nếu có từ vựng lạ
 │     └─ Nếu trả lời được (number / text / table / boolean / unanswerable) ──► Trả về ngay (99.7% Precision)
 │
 ├─► [Tier 2: LLM DuckDB Pipeline (Qwen/Qwen3-14B-FP8 trên vLLM)] (Khi Tier 1 abstain)
 │     ├─ Subjective Check (logprob yes/no phát hiện câu hỏi cảm tính / lời khuyên)
 │     ├─ LLM Schema Mapper (infer.py + validate.py) -> DuckDB Canonical ETL (11 bảng chuẩn)
 │     ├─ Dynamic Rulebook Extractor (from_rulebook.py + defined_terms.py)
 │     ├─ 2-Vote Self-Consistency Parser (QuerySpec & ExtQuerySpec 9 họ truy vấn mở rộng)
 │     ├─ Reverse Description Verifier (verify.py: dịch ngược spec -> tiếng Việt để đối chiếu)
 │     ├─ ThinkingClient Retry (bật <think> khi fast-pass bất đồng hoặc out_of_scope)
 │     └─ Missing Group / Missing Attribute Check (phát hiện cột/nhóm hàng không được ghi chép)
 │
 └─► [Tier 3: Direct Sandbox Fallback (Tuỳ chọn)]
       └─ Sinh code Python chạy trong sandbox cô lập với điều kiện 2/2 Self-Consistency
```

---

## 2. Khai Báo Mô Hình & Tuân Thủ Yêu Cầu Phần Cứng Đề Bài (`RULE.MD`)

### Khai Báo Mô Hình (Rule 2 — Tổng tham số $\le 15\text{B}$)

| Thành phần | Tên Model (HuggingFace) | Số tham số | Định dạng / Lượng tử hoá | Ngày phát hành | Giấy phép |
|---|---|---:|---|---|---|
| **LLM chính (Tier 2/3)** | `Qwen/Qwen3-14B-FP8` | **14.8B** | FP8 (`W8A8`) | Trước 01/10/2026 (04/2025) | Apache-2.0 |
| **Tier 1 (`FastCore`)** | Không dùng model (100% thuật toán tất định) | **0** | — | — | — |
| **Embedding / Reranker / Classifier** | Không sử dụng | **0** | — | — | — |
| **Tổng cộng toàn hệ thống** | | **14.8B ($\le 15\text{B}$)** | | | |

### Cấu Hình Phần Cứng Tham Chiếu Của BTC (Rule 7 & Rule 8)

- **Máy chấm Private Test của BTC (Rule 7):**
  - **GPU:** `2 × NVIDIA RTX 5090` (**32 GB VRAM mỗi card = 64 GB VRAM tổng**, kiến trúc Blackwell `sm_120`, yêu cầu **CUDA ≥ 12.8** và bản build PyTorch/vLLM tương thích).
  - **RAM:** **512 GB RAM**.
  - **Giới hạn thời gian:** Tối đa **6 giờ** wall-clock cho toàn bộ tập Private Test (bao gồm cả thời gian khởi động và load model; hệ thống đặt `DEFAULT_TIME_BUDGET_S = 18900` = 5h15m để luôn dừng an toàn trước mốc 6h).
- **Tính tái lập kết quả (Rule 8):** `|PA(uploaded) − PA(re-run)| ≤ 0.03` (cố định `--seed 0`, `temperature = 0.0`, cùng `--max-model-len 16384`).

---

## 3. Kết Quả Kiểm Chứng Trên Tập `train` (3.000 Câu Hỏi)

| Tập đánh giá | Số câu ($N$) | Đúng ($+1$) | Sai ($-1$) | Abstain ($0$) | Precision | Coverage | Điểm **PA** |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`dev`** (24 hộ kinh doanh) | 2.447 | 2.410 | **0** | 37 | **100.00%** | 98.49% | **0.9849** |
| **`holdout`** (6 hộ kinh doanh ẩn) | 553 | 485 | 10 | 58 | **97.98%** | 89.51% | **0.8590** |
| **Tổng `train` (Tier-1 CPU)** | 3.000 | 2.895 | 10 | 95 | **99.66%** | 96.83% | **0.9617** |

---

## 3. Hướng Dẫn Chạy (Máy Không Có GPU + Có Google Colab Pro)

### Cài Đặt Môi Trường Local

```bash
uv sync --extra dev
```

### Cách 1: Chạy Local CPU-Only (Không cần GPU — `fastcore`)

```bash
# Đánh giá trên tập dev / holdout
.venv/bin/python eval/run_eval.py --split dev --by intent
.venv/bin/python eval/run_eval.py --split holdout --by intent

# Chạy xuất submission.jsonl bằng chế độ fastcore (hoặc hybrid tự động fallback khi không có vLLM)
.venv/bin/python -m datamate.predict --data-dir ./train --out-dir ./result_cpu --system fastcore --workers 4
```

### Cách 2: Dùng GPU của Google Colab Pro Qua Cloudflare Tunnel (`deploy/colab_vllm.ipynb`)

Phù hợp khi bạn muốn giữ dữ liệu và chạy code trên máy cá nhân, chỉ mượn GPU của **Colab Pro (L4 / A100 / G4 RTX PRO 6000)** để chạy `vLLM` (`Qwen/Qwen3-14B-FP8`):
1. Mở [`deploy/colab_vllm.ipynb`](file:///home/iamhieu2012/Dev/zalo-aic-2026/deploy/colab_vllm.ipynb) trên **Google Colab Pro** (chọn GPU `G4`, `A100`, hoặc `L4`).
2. Chạy các cell để khởi động `vLLM` và lấy đường dẫn `LLM_BASE_URL=https://xxxx.trycloudflare.com/v1`.
3. Tạo file `.env` tại thư mục gốc của project trên máy cá nhân:
   ```env
   LLM_BASE_URL=https://xxxx.trycloudflare.com/v1
   LLM_API_KEY=datamate-colab-key
   LLM_MODEL=qwen3-14b
   ```
4. Chạy hệ thống **Hybrid** ở máy local (mọi kết quả gọi LLM đều được lưu vào `cache/llm/` nên không bao giờ tốn GPU lần 2 cho cùng một truy vấn):
   ```bash
   # Đánh giá thông qua evals/run_eval.py
   .venv/bin/python -m evals.run_eval --split train --subset poc --system hybrid --workers 8

   # Xuất file nộp bài submission.jsonl
   .venv/bin/python -m datamate.predict --data-dir <duong_dan_split> --out-dir ./result_hybrid --system hybrid --workers 8
   ```

### Cách 3: Chạy Trực Tiếp 100% Trên Google Colab Pro (`notebooks/colab_pro_hybrid_runner.ipynb`)

Phù hợp khi bạn muốn chạy toàn bộ từ đầu đến cuối ngay trên ổ SSD và GPU của **Colab Pro** (không bị độ trễ mạng qua tunnel) và lưu thẳng `submission.jsonl` + `cache/` về Google Drive:
1. Mở [`notebooks/colab_pro_hybrid_runner.ipynb`](file:///home/iamhieu2012/Dev/zalo-aic-2026/notebooks/colab_pro_hybrid_runner.ipynb) trên **Google Colab Pro**.
2. Làm theo từng cell trong notebook để mount Google Drive, bật `vLLM` tại `127.0.0.1:8000`, và chạy `python -m datamate.predict --system hybrid`.

### Cách 4: Đóng Gói Docker Offline Nộp Bài (2 × RTX 5090 — `docker/`)

Xem chi tiết tại [`docker/README.md`](file:///home/iamhieu2012/Dev/zalo-aic-2026/docker/README.md):
```bash
# 1. Tải model Qwen/Qwen3-14B-FP8 về docker/models/Qwen3-14B-FP8
bash docker/fetch_model.sh

# 2. Build image chuẩn thi đấu
docker build -f docker/Dockerfile -t zaic2026_datamate_<team_name>:final .

# 3. Chạy kiểm thử đúng lệnh chấm offline của BTC
docker run --rm \
  --gpus '"device=0,1"' \
  --network none \
  --shm-size=16g \
  --entrypoint bash \
  -v /path/to/test:/data:ro \
  -v /path/to/output:/result \
  zaic2026_datamate_<team_name>:final /code/predict.sh
```

---

## 4. Kiểm Thử (Unit & Integration Tests)

```bash
# Chạy toàn bộ hơn 720 unit tests & integration tests
.venv/bin/pytest -q

# Kiểm tra hợp lệ file submission.jsonl
.venv/bin/python -m evals.check_submission --submission ./result_hybrid/submission.jsonl --split train
```
