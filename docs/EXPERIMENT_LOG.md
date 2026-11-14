# Nhật Ký Thực Nghiệm & Nộp Bài (Experiment & Submission Log)

Tài liệu này theo dõi các lần chạy thực nghiệm và nộp bài của dự án **Zalo AI Challenge 2026 — DataMate Track**.
Mô tả pipeline và các phiên bản code: [`PIPELINE.md`](PIPELINE.md).

---

## 1. Bảng Tổng Hợp Các Lần Chạy & Điểm Số

| Lần chạy | Thời gian | Code (branch / commit) | Cấu hình & Mô hình | Trả lời / Abstain | Điểm **Public PA** | File Submission |
|---|---|---|---|:---:|---:|---|
| **Run #1** | 09/11/2026 09:03 | bản gốc (`2d3f78d`) | `Qwen3-14B-FP8`, verifier 0.5 | **815 / 185** | **`0.65100`** | `result_fresh/submission.jsonl` |
| **Run #2** | 13/11/2026 | `gemma-fixes`, trước bản sửa | `gemma-4-12B-it`, code như Run #1, verifier 0.5 | 735 / 265 | `0.52300` | `result/20261113_gemma4_12b/submission.jsonl` |
| **Run #3** | 14/11/2026 01:00 | `gemma-fixes` (`810fd8e`) | `gemma-4-12B-it` + 3 bản sửa, **verifier tắt (ngưỡng 0)** | 831 / 169 | `0.50500` | `result/20261114_gemma4_12b_fix/submission.jsonl` |
| **Run #4** | 14/11/2026 11:50 | `main` (`97f6a5e`) | `Qwen3-14B-FP8`, code như Run #1 — chạy lại kiểm tra tái lập | 821 / 179 | `0.64300` | `result/20261114_qwen3_main/submission.jsonl` |
| **Run #5** | 14/11/2026 14:00 | `gemma-fixes` (`810fd8e` + answer-agreement, chưa commit) | `gemma-4-12B-it` + 3 bản sửa + chấp nhận 2 spec cùng đáp án, verifier 0.5 | 763 / 237 | `0.55900` | `result/20261114_gemma4_12b_v2/submission.jsonl` |
| **Run #6** | 14/11/2026 17:00 | `gemma-fixes` (`810fd8e` + answer-agreement, chưa commit) | `Qwen3-14B-FP8` + 3 bản sửa + answer-agreement, verifier 0.5 | 814 / 186 | chưa nộp | `result/20261114_qwen3_fix_v2/submission.jsonl` |
| **Run #7** | 15/11/2026 00:20 | `lora-parser` (`50b6ded`) | `Qwen3-14B` BF16 + adapter LoRA parser + đối chiếu phạm vi, verifier 0.5 | 849 / 151 | `0.62900` | `result/20261114_qwen3_lora/submission.jsonl` |

Số câu đúng / sai suy ra từ PA (đúng − sai = PA × 1000, đúng + sai = số câu trả lời):

| Lần chạy | Đúng | Sai | Precision |
|---|---:|---:|---:|
| Run #1 (Qwen) | ~733 | ~82 | 89.9% |
| Run #2 (Gemma) | ~629 | ~106 | 85.6% |
| Run #3 (Gemma, verifier tắt) | ~668 | ~163 | 80.4% |
| Run #4 (Qwen, chạy lại) | ~732 | ~89 | 89.2% |
| Run #5 (Gemma + sửa, verifier bật) | ~661 | ~102 | 86.6% |
| Run #7 (Qwen + LoRA) | ~739 | ~110 | 87.0% |

---

## 2. Chi Tiết Từng Lần Chạy

Mọi lần chạy dùng cùng lệnh, chỉ khác `--out-dir` (và biến môi trường nếu ghi chú):

```bash
.venv/bin/python -m datamate.predict \
  --data-dir ./public_test \
  --out-dir <out-dir> \
  --system pipeline_llm \
  --workers 12 \
  --time-budget-s 18900
```

Hạ tầng chung: vLLM trên Google Colab qua Cloudflare Tunnel, `--max-model-len 16384`, `--enable-prefix-caching`,
`temperature 0`, seed cố định, thinking retry bật (`parse_thinking = "retry"`). Không lần nào bị timeout.

### Run #1 — `result_fresh` (Qwen3-14B, bản gốc) — `0.65100`
- Thời gian: 3.122 s (~52 phút), 36,95 s/câu.
- Phân bổ: `number` 464, `abstain` 185, `percent` 173, `list` 53, `string` 44, `date` 38, `unanswerable` 27,
  `boolean` 11, `table` 5.
- Đây vẫn là bản điểm cao nhất.

### Run #2 — `result/20261113_gemma4_12b` (Gemma 4 12B, code như Run #1) — `0.52300`
- Server: `google/gemma-4-12B-it`, `--reasoning-parser gemma4`.
- Thời gian: 3.021 s (~50 phút).
- Phân bổ: `number` 421, `abstain` 265, `percent` 137, `list` 47, `string` 42, `unanswerable` 39, `date` 33,
  `boolean` 11, `table` 5.
- So với Run #1: 754/1000 câu trùng đáp án; Gemma abstain thêm ~130 câu Qwen trả lời được.
- Kiểm tra train trước khi chạy: 20 câu `poc` → PA 0.95 (19 đúng, 0 sai).

### Run #3 — `result/20261114_gemma4_12b_fix` (Gemma + 3 bản sửa, verifier tắt) — `0.50500`
- Biến môi trường: `EXT_VERIFY_THRESHOLD=0 EXT_VERIFY_THRESHOLD_SPLIT=0`.
- 3 bản sửa (commit `810fd8e`, không gắn với model):
  1. Tên ca chuẩn hoá (`ca sáng` / `ca chiều` → `morning` / `afternoon`), kể cả cấu hình rulebook trong cache.
  2. Nhãn khách lẻ thêm dạng rút gọn (`khách lẻ` → `lẻ`); `ETL_VERSION` 1.14 → 1.15.
  3. `qty_sold` nêu đủ tên mặt hàng mà spec thiếu mặt hàng → abstain (`qty_sold_named_product_check`).
- Thời gian: 2.937 s (~49 phút).
- Phân bổ: `number` 458, `abstain` 169, `percent` 153, `unanswerable` 63, `string` 55, `list` 53, `date` 33,
  `boolean` 11, `table` 5.
- Kết quả: **−0.018** so với Run #2 (~+39 đúng, ~+57 sai). **Tắt verifier là sai lầm**: trên train verifier chủ yếu
  chặn nhầm câu đúng, nhưng trên public (cửa hàng loại mới) nó là lớp chặn câu bị ép sai nhóm.

### Run #4 — `result/20261114_qwen3_main` (Qwen3-14B, code như Run #1, chạy lại từ đầu) — `0.64300`
- Mục đích: đo độ tái lập (Rule 8: `|PA(uploaded) − PA(re-run)| ≤ 0.03`).
- Thời gian: 2.870 s (~48 phút).
- Phân bổ: `number` 469, `abstain` 179, `percent` 171, `list` 55, `string` 45, `date` 38, `unanswerable` 27,
  `boolean` 11, `table` 5.
- So với Run #1 (`evals.compare_runs`): **970/1000 câu trùng đáp án (97%)**. 30 câu khác: 17 abstain → trả lời,
  10 trả lời → abstain, 4 đổi đáp án.
- Ánh xạ cột giống hệt ở 11/14 shop (dev_001, dev_013, dev_014 khác — 7/30 câu lệch); phần còn lại do LLM đọc câu hỏi
  hơi khác giữa hai lần chạy (vLLM batch / GPU khác).
- Kết quả: **0.643**, lệch **0.008** so với Run #1 (~−1 đúng, ~+7 sai) → **đạt Rule 8** (≤ 0.03). Cùng code, điểm dao
  động khoảng ±0.01 giữa các lần chạy, nên so sánh hai cấu hình chỉ có ý nghĩa khi chênh lớn hơn mức đó.

### Run #5 — `result/20261114_gemma4_12b_v2` (Gemma + 3 bản sửa + answer-agreement, verifier 0.5) — `0.55900`
- Thêm (chưa commit): khi 2 vote của parser mở rộng lệch nhau, chạy cả 2 spec; nếu cả hai ra **cùng một đáp án thật**
  (không phải abstain / unanswerable) thì nhận (`ext_answer_agreement`).
- Thời gian: 2.945 s (~49 phút).
- Phân bổ: `number` 439, `abstain` 237, `percent` 154, `list` 47, `string` 41, `date` 33, `unanswerable` 32,
  `table` 6, `boolean` 11.
- Kết quả: **+0.036** so với Run #2 (~+32 đúng, ~−4 sai). Các bản sửa có ích, nhưng Gemma vẫn kém Qwen ~0.09.


### Run #6 — `result/20261114_qwen3_fix_v2` (Qwen + 3 bản sửa + answer-agreement, verifier 0.5) — chưa nộp
- Code giống Run #5, model Qwen3-14B-FP8.
- Thời gian: 2.869 s (~48 phút).
- Phân bổ: `number` 459, `abstain` 186, `percent` 174, `list` 53, `string` 48, `date` 37, `unanswerable` 27,
  `boolean` 11, `table` 5.
- So với Run #1: **975/1000 câu trùng đáp án** — trong mức dao động giữa hai lần chạy cùng code (Run #4: 970/1000).
  Các bản sửa gần như không đổi gì với Qwen (lỗi tên ca, khách lẻ, `qty_sold` chủ yếu là lỗi của Gemma). Điểm dự kiến
  ~0.64–0.66, tương đương Run #1.

### Run #7 — `result/20261114_qwen3_lora` (Qwen + LoRA parser + đối chiếu phạm vi) — `0.62900`
- Server: `qwen3-14b-bf16` + adapter `datamate-parse` (`colab_vllm.ipynb`, `MODEL_CHOICE = "qwen3-14b-bf16-lora"`);
  `.env` có `LLM_PARSE_MODEL=datamate-parse`.
- Thời gian: 3.117 s (~52 phút), 12 worker. 1 câu mất do server không phản hồi, pipeline tự chạy lại.
- Phân bổ: `number` 483, `percent` 179, `abstain` 151, `list` 55, `string` 48, `date` 37, `unanswerable` 30,
  `boolean` 12, `table` 5.
- So với Run #1: trả lời thêm ~34 câu nhưng sai thêm ~28 → **−0.022**. Train lại tăng (xem mục 3): adapter tự tin sai
  trên loại shop mới.
---

## 3. Đánh Giá Trên Train (dùng để chỉnh, không phải điểm nộp)

Chấm bằng `evals.run_eval` trên `train/answers.jsonl`. Subset theo `evals/splits.yaml`.

| Lượt | Model | Code | Subset | Đúng / Sai / Abstain | PA |
|---|---|---|---|---|---:|
| poc 20 câu | Gemma 4 12B | trước bản sửa | `poc` (20) | 19 / 0 / 1 | 0.950 |
| `runs/20261113-150943_pipeline_llm_dev` | Gemma 4 12B | trước bản sửa, verifier 0 | `dev` (1735) | 1501 / 55 / 179 | 0.833 |
| `runs/20261113-162929_pipeline_llm_val` | Gemma 4 12B | 3 bản sửa, verifier 0 | `val` (631) | 579 / 3 / 49 | 0.913 |
| holdout_family | Gemma 4 12B | 3 bản sửa, verifier 0 | `holdout_family` (120) | 119 / 0 / 1 | 0.992 |
| `runs/*_pipeline_llm_dev` (nhãn LoRA) | Qwen3-14B | 3 bản sửa + answer-agreement | `dev` (1735) | 1669 / 10 / 56 | 0.956 |
| `runs/*_pipeline_llm_poc` (nhãn LoRA) | Qwen3-14B | 3 bản sửa + answer-agreement | `poc` (256) | 252 / 0 / 4 | 0.984 |
| `runs/20261114-154528_pipeline_llm_val` | Qwen3-14B BF16 | `50b6ded`, không LoRA | `val` (631) | 576 / 4 / 51 | 0.9065 |
| `runs/20261114-160919_pipeline_llm_holdout_family` | Qwen3-14B BF16 | `50b6ded`, không LoRA | `holdout_family` (120) | 118 / 0 / 2 | 0.9833 |
| `runs/20261114-152441_pipeline_llm_val` | Qwen3-14B BF16 + LoRA | LoRA, chưa đối chiếu | `val` (631) | 582 / 9 / 40 | 0.9081 |
| `runs/20261114-154327_pipeline_llm_holdout_family` | Qwen3-14B BF16 + LoRA | LoRA, chưa đối chiếu | `holdout_family` (120) | 118 / 2 / 0 | 0.9667 |
| `runs/20261114-162241_pipeline_llm_val` | Qwen3-14B BF16 + LoRA | `50b6ded` (có đối chiếu) | `val` (631) | 585 / 6 / 40 | 0.9176 |
| `runs/20261114-162720_pipeline_llm_holdout_family` | Qwen3-14B BF16 + LoRA | `50b6ded` (có đối chiếu) | `holdout_family` (120) | 120 / 0 / 0 | 1.0000 |

Phát hiện từ train (Gemma, `dev`):
- 43 câu theo ca crash (`KeyError: 'afternoon'/'morning'`) → bản sửa 1.
- 26 câu sai ở `top_customers` / `customers_min_orders` do "lẻ" bị tính là một khách → bản sửa 2.
- 23/24 câu `qty_sold` sai do spec bỏ trống mặt hàng → bản sửa 3.
- 82 câu `disagreement`: 39 câu hai spec ra cùng đáp án, **cả 39 đều đúng** (val: 2/2 đúng) → answer-agreement.

**Bài học:** điểm train (`val` 0.91, `holdout_family` 0.99) **không đại diện cho public** vì train không có loại cửa
hàng mới. Train chỉ dùng để bắt lỗi làm hỏng cái đang đúng; mọi thay đổi chỉ an toàn nếu nó biến câu sai thành
abstain hoặc sửa crash, không mở thêm đường trả lời.

---

## 4. Kế Hoạch Tiếp Theo

1. **LoRA cho bước đọc câu hỏi** (chi tiết: `PIPELINE.md` mục 6): đã train và nộp (Run #7, 0.629 < 0.651).
   Hướng còn lại: chỉ cho adapter trả lời câu mà model gốc abstain; tách thêm loại shop khỏi nhãn để có tập đo gần
   public hơn `holdout_family` (120 câu).
2. Nếu cần giảm lệch giữa các lần chạy: thử chế độ batch-invariant của vLLM hoặc giảm số worker.

---

## 5. Vị Trí Dữ Liệu & Cache

- **Bản điểm cao nhất:** `result_fresh/submission.jsonl` (Run #1, 0.651), log tại `result_fresh/logs/`.
- **Các lần chạy khác:** `result/<ngày>_<model>[_tag]/` — mỗi thư mục có `submission.jsonl`, `logs/`, `timing.json`,
  `work/cache/` (cache LLM, mapping, bảng chuẩn DuckDB). Log chạy: `result/<tên>.log`.
- **Đánh giá train:** `runs/<thời gian UTC>_pipeline_llm_<subset>/`.
