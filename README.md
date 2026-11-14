# Zalo AI Challenge 2026 — DataMate Track (`pipeline_llm`)

Hệ thống trả lời câu hỏi tiếng Việt trên dữ liệu bán hàng của hộ kinh doanh (CSV, Excel, SQLite), tối ưu theo
**Penalized Accuracy** (đúng +1, abstain 0, sai −1). Thể lệ cuộc thi: [`docs/competition/`](docs/competition/).

**Kết quả:** public PA **0.651** (`--system pipeline_llm`, 815 trả lời / 185 abstain). Chi tiết các lần chạy:
[`docs/EXPERIMENT_LOG.md`](docs/EXPERIMENT_LOG.md).

---

## 1. Kiến Trúc

`Qwen3-14B-FP8` (vLLM, temperature 0, seed cố định) + DuckDB.

1. **Mỗi shop:** LLM map cột dữ liệu thô sang schema chuẩn (đơn hàng, dòng hàng, sản phẩm, khách hàng, thanh toán,
   công nợ, nhập hàng, tồn kho, lô), ETL vào DuckDB và kiểm tra toàn vẹn. Bảng map lỗi thì bị cách ly.
2. **Rulebook:** LLM phân loại từng dòng của `<split>/rulebook.md` và trích các tham số tính toán.
3. **Mỗi câu hỏi:**
   - Câu hỏi chủ quan thì trả `unanswerable`. Thuật ngữ xếp hạng có trong rulebook thì đi nhánh xếp hạng.
   - Parser chính: 2 vote LLM sinh `QuerySpec`, khớp nhau mới chạy `MetricEngine` (SQL tất định trên DuckDB).
   - Ngoài phạm vi thì qua parser mở rộng (~30 nhóm nghiệp vụ) có verifier xác suất.
   - Còn abstain thì parse lại với thinking, rồi thử các nhánh phụ (đơn vị, thuộc tính, dữ liệu shop không ghi).
4. Không chắc chắn thì abstain.

---

## 2. Khai Báo Mô Hình & Phần Cứng ([`RULE.MD`](docs/competition/RULE.MD))

| Thành phần | Model (HuggingFace) | Số tham số | Định dạng | Phát hành | Giấy phép |
|---|---|---:|---|---|---|
| LLM | `Qwen/Qwen3-14B-FP8` | **14.8B** | FP8 (`W8A8`) | 04/2025 | Apache-2.0 |
| Embedding / Reranker / Classifier | Không sử dụng | 0 | — | — | — |
| **Tổng** | | **14.8B (≤ 15B)** | | | |

- **Máy chấm (Rule 7):** 2 × RTX 5090 (32 GB mỗi card), 512 GB RAM, tối đa 6 giờ cả load model.
  `DEFAULT_TIME_BUDGET_S = 18900` (5h15m) để dừng an toàn trước mốc 6h.
- **Tái lập (Rule 8):** `|PA(uploaded) − PA(re-run)| ≤ 0.03` — `--seed 0`, `temperature = 0`, `--max-model-len 16384`.

---

## 3. Cấu Trúc Thư Mục

```text
src/datamate/        mã nguồn (predict.py là entrypoint)
  io/ parse/         đọc file thô, chuẩn hoá tiền / ngày / số
  mapping/ etl/      LLM map cột → schema chuẩn, ETL vào DuckDB
  rules/             đọc rulebook.md → tham số tính toán
  query/ timeres/    parse câu hỏi → QuerySpec, giải kỳ thời gian (âm/dương lịch)
  metrics/           MetricEngine + các nhóm nghiệp vụ mở rộng (SQL tất định)
  systems/pipeline.py  PipelineSystem (pipeline_llm)
  llm/ scoring/      client vLLM (có cache), định dạng & chấm đáp án
evals/               chấm trên train (run_eval.py), kiểm tra submission, so sánh lần chạy
rules/train.json     tham số rulebook train (dùng bởi test và evals)
tests/               unit & integration tests
docker/              Dockerfile + predict.sh nộp bài offline
notebooks/           colab_vllm.ipynb (vLLM + tunnel), colab_pro_runner.ipynb (chạy toàn bộ trên Colab)
docs/                thể lệ cuộc thi (competition/) và nhật ký thực nghiệm
train/ public_test/  dữ liệu BTC (không commit)
```

---

## 4. Hướng Dẫn Chạy

```bash
uv sync --extra dev
```

### Dùng GPU Colab qua Cloudflare Tunnel ([`notebooks/colab_vllm.ipynb`](notebooks/colab_vllm.ipynb))

1. Mở notebook trên Colab Pro (A100 hoặc G4), chạy toàn bộ cell.
2. Dán `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` mà notebook in ra vào `.env` ở máy local.
3. Chạy:
   ```bash
   .venv/bin/python -m datamate.predict \
     --data-dir ./public_test \
     --out-dir ./result_fresh \
     --system pipeline_llm \
     --workers 12 \
     --time-budget-s 18900
   ```
   Mọi kết quả gọi LLM được cache trong `<out-dir>/work/cache/`, chạy lại không tốn GPU cho cùng truy vấn.

### Chạy toàn bộ trên Colab ([`notebooks/colab_pro_runner.ipynb`](notebooks/colab_pro_runner.ipynb))

Mount Google Drive, bật vLLM tại `127.0.0.1:8000` và chạy `python -m datamate.predict --system pipeline_llm`.

### Chấm trên train

```bash
.venv/bin/python -m evals.run_eval --split train --subset val --system pipeline_llm --workers 12
```

Các subset (`poc`, `val`, `holdout_family`, `dev`) định nghĩa trong [`evals/splits.yaml`](evals/splits.yaml).

### Docker offline (2 × RTX 5090)

Xem [`docker/README.md`](docker/README.md).

---

## 5. Kiểm Thử

```bash
.venv/bin/pytest -q
.venv/bin/python -m evals.check_submission --submission ./result_fresh/submission.jsonl --split public_test
```
