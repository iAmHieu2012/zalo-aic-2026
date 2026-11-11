# Nhật Ký Thực Nghiệm & Nộp Bài (Experiment & Submission Log)

Tài liệu này lưu lại toàn bộ lịch sử cấu hình, cách chạy, phân bổ câu trả lời, file log và điểm số thực tế qua từng lần chạy của dự án **Zalo AI Challenge 2026 — DataMate**.

---

## 1. Bảng Tổng Hợp Các Lần Chạy & Điểm Số

| Lần chạy | Thời gian | Chế độ (`--system`) | Thứ tự xử lý | Số câu trả lời / Abstain | Điểm **PA** | File Submission lưu trữ | File Log lưu trữ |
|---|---|---|---|---|---:|---|---|
| **Train `dev`** | 07/11 09:29 | `fastcore` (CPU) | Chỉ dùng `FastCore` | `2410 / 37` (2447 câu) | **0.9849** (100% Prec) | `eval/runs/20261107_092937_dev/` | `eval/runs/20261107_092937_dev/` |
| **Train `holdout`** | 07/11 09:36 | `fastcore` (CPU) | Chỉ dùng `FastCore` | `495 / 58` (553 câu) | **0.8590** (97.98% Prec) | `eval/runs/20261107_093655_holdout/` | `eval/runs/20261107_093655_holdout/` |
| **Sub #1 (Public)** | 07/11 12:05 | `hybrid` (FastCore $\rightarrow$ LLM) | Tier-1 `FastCore` (130 câu) $\rightarrow$ Tier-2 `PipelineSystem` (870 câu) | **839 / 161** | **0.62900** | [`run1_062900_fastcore_first_hybrid.jsonl`](file:///home/iamhieu2012/Dev/zalo-aic-2026/result_submission/history/run1_062900_fastcore_first_hybrid.jsonl) | [`run1_062900_log.jsonl`](file:///home/iamhieu2012/Dev/zalo-aic-2026/result_submission/history/run1_062900_log.jsonl) |
| **Sub #2 (Public)** | 07/11 12:47 | `pipeline_llm` (Pure LLM+DuckDB) | 100% `PipelineSystem` (`Qwen3-14B-FP8` + DuckDB ETL) | **825 / 175** | **0.64500** (`+0.016`) | [`run2_064500_pure_pipeline_llm.jsonl`](file:///home/iamhieu2012/Dev/zalo-aic-2026/result_submission/history/run2_064500_pure_pipeline_llm.jsonl) | [`run2_064500_log.jsonl`](file:///home/iamhieu2012/Dev/zalo-aic-2026/result_submission/history/run2_064500_log.jsonl) |
| **Sub #3 (Public)** | 07/11 12:52 | `llm_first_hybrid` (LLM $\rightarrow$ FastCore) | Tier-1 `PipelineSystem` (825 câu) $\rightarrow$ Tier-2 `FastCore` cứu 14 câu `abstain` | **839 / 161** | **0.64300** (`-0.002`) | [`submission_v3_llm_first_hybrid.jsonl`](file:///home/iamhieu2012/Dev/zalo-aic-2026/result_submission/submission_v3_llm_first_hybrid.jsonl) | [`result_submission/logs/`](file:///home/iamhieu2012/Dev/zalo-aic-2026/result_submission/logs) |
| **Sub #4 (Public)** | 09/11 09:03 | `pipeline_llm` (Fix Rulebook Poisoning) | 100% `PipelineSystem` (`Qwen3-14B-FP8` + DuckDB ETL + Đã sửa rulebook cache) | **815 / 185** | **0.65100** (`+0.006`) | [`result_fresh/submission.jsonl`](file:///home/iamhieu2012/Dev/zalo-aic-2026/result_fresh/submission.jsonl) | [`result_fresh/logs/`](file:///home/iamhieu2012/Dev/zalo-aic-2026/result_fresh/logs) |

---

## 2. Chi Tiết Từng Lần Chạy Trên Tập Public Test (1.000 Câu)

### Lần 1 — `Sub #1`: FastCore-First Hybrid (`PA = 0.62900`)
- **Lệnh chạy:**
  ```bash
  .venv/bin/python -m datamate.predict --data-dir ./public_test --out-dir ./result_submission --system hybrid --workers 12
  ```
- **Hạ tầng:** Local CPU + Remote GPU `G4` (RTX PRO 6000 Blackwell 96GB trên Google Colab Pro) chạy `vLLM` (`Qwen/Qwen3-14B-FP8`, `--max-model-len 16384`, `LLM_DISABLE_THINKING=true`).
- **Cơ chế hoạt động:**
  1. Câu hỏi đi qua `Dynamic Rulebook Diff Guard` và `FastCore` (Tier 1) trước.
  2. Có **130 / 1000 câu** vượt qua cổng từ vựng `gate.py` của `FastCore` và được `FastCore` trả lời ngay (`number=79, percent=27, list=10, unanswerable=9, date=4, table=1`).
  3. Có **870 / 1000 câu** `FastCore` từ chối (`abstain`) được đẩy sang `PipelineSystem` (`Qwen3-14B-FP8` + DuckDB), trả lời thêm được **709 câu** và `abstain` **161 câu**.
- **Tổng phân bổ câu trả lời (`839 answered | 161 abstain`):**
  `number=478, percent=172, list=55, string=45, date=38, unanswerable=34, boolean=11, table=6, abstain=161`
- **Nhận xét & Nguyên nhân mất điểm:**
  - Vì `FastCore` chạy trước nên đã chặn 130 câu không cho `PipelineSystem` xử lý. Trong 130 câu đó, có những câu thuộc cửa hàng mới có quy ước cột/rulebook khác với `train`, khiến rule cứng của `FastCore` tính sai đáp án (mỗi câu sai mất $-2$ điểm so với trả lời đúng).

---

### Lần 2 — `Sub #2`: Pure `PipelineSystem` (`Qwen3-14B-FP8` + DuckDB) (`PA = 0.64500`, tăng `+0.01600`)
- **Lệnh chạy:**
  ```bash
  .venv/bin/python -m datamate.predict --data-dir ./public_test --out-dir ./result_submission --system pipeline_llm --workers 12
  ```
- **Cơ chế hoạt động:**
  - Tái sử dụng toàn bộ cache của 14 cửa hàng (`result_submission/work/cache/mappings/`) và 870 câu đã chạy ở Lần 1.
  - Gọi GPU Colab chạy bổ sung `PipelineSystem` (`Qwen3-14B-FP8`) cho **130 câu** mà ở Lần 1 `FastCore` đã tự trả lời.
- **Tổng phân bổ câu trả lời (`825 answered | 175 abstain`):**
  `number=470, percent=174, list=55, string=45, date=38, unanswerable=27, boolean=11, table=5, abstain=175`
- **Đối chiếu 130 câu giữa `FastCore` (Lần 1) và `PipelineSystem` (Lần 2):**
  - **95 / 130 câu:** Cả `FastCore` và `PipelineSystem` ra kết quả **giống hệt nhau 100%**.
  - **35 / 130 câu khác nhau:**
    - `21 câu` cả 2 đều trả lời nhưng khác kết quả:
      - `7 câu` khác giá trị `number`
      - `5 câu` khác giá trị `percent`
      - `2 câu` `FastCore` báo `unanswerable` nhưng `PipelineSystem` tìm được sản phẩm và ra `number`
      - `2 câu` `FastCore` báo `unanswerable` nhưng `PipelineSystem` tính ra `percent`
      - `2 câu` khác `unanswerable` reason, `2 câu` khác thứ tự/mã `list`, `1 câu` `number` vs `list`
    - `14 câu` `PipelineSystem` bị `abstain` nhưng `FastCore` trả lời được (`9 number, 3 unanswerable, 1 list, 1 table`).
- **Kết quả:** Điểm Public Leaderboard tăng từ **`0.62900` $\rightarrow$ `0.64500` (`+16 điểm ròng`)**, chứng minh trong 21 câu bất đồng giữa hai hệ thống, `PipelineSystem` (`Qwen3-14B-FP8` + DuckDB) chính xác vượt trội so với rule cứng của `FastCore`.

---

### Lần 3 — `Sub #3`: Reverse-Cascade Hybrid (`PipelineSystem` Tier-1 $\rightarrow$ `FastCore` Tier-2 Rescue)
- **File xuất:** [`result_submission/submission_v3_llm_first_hybrid.jsonl`](file:///home/iamhieu2012/Dev/zalo-aic-2026/result_submission/submission_v3_llm_first_hybrid.jsonl) (và bản sao tại [`result_submission/history/run3_llm_first_hybrid.jsonl`](file:///home/iamhieu2012/Dev/zalo-aic-2026/result_submission/history/run3_llm_first_hybrid.jsonl)).
- **Cơ chế hoạt động:**
  - **Tier 1:** Lấy nguyên vẹn **825 câu trả lời** của `PipelineSystem` (`Sub #2` — `0.64500`).
  - **Tier 2:** Với 175 câu mà `PipelineSystem` bị `abstain`, dùng `FastCore` cứu viện cho **14 câu** mà `FastCore` giải được:
    1. `q_0ca19cd317cb` (`dev_006`): `list` `['SP0075', 'SP0023', 'SP0069', 'SP0043', 'SP0068']` (`PipelineSystem` bị `out_of_scope`)
    2. `q_393267cfdee1` (`dev_006`): `number` `6` (`PipelineSystem` bị `parse_error`)
    3. `q_393d0d4ee0e2` (`dev_007`): `number` `81` (`PipelineSystem` bị `disagreement`)
    4. `q_3cd196c4dc4d` (`dev_007`): `number` `29` (`PipelineSystem` bị `disagreement`)
    5. `q_4c24acd737a8` (`dev_014`): `number` `1822262500` (`PipelineSystem` bị `out_of_scope`)
    6. `q_67412073e116` (`dev_008`): `unanswerable` `'no debt data'` (`PipelineSystem` bị `ext_verify_low`)
    7. `q_9e6f314a5bd8` (`dev_010`): `table` Top 5 khách nợ (`PipelineSystem` bị `engine_abstain` do quarantine)
    8. `q_9f4af1e4fecd` (`dev_011`): `number` `906060000` (`PipelineSystem` bị `out_of_scope`)
    9. `q_a6a66b57f28c` (`dev_007`): `number` `79` (`PipelineSystem` bị `disagreement`)
    10. `q_c64c6d29f583` (`dev_002`): `number` `2547` (`PipelineSystem` bị `ext_verify_low`)
    11. `q_c9afaa1f4f9e` (`dev_011`): `unanswerable` `'no payment method'` (`PipelineSystem` bị `parse_error`)
    12. `q_d1c95d7db2ae` (`dev_010`): `number` `38` (`PipelineSystem` bị `disagreement`)
    13. `q_d2c646bb39ec` (`dev_010`): `number` `20715673` (`PipelineSystem` bị `disagreement`)
    14. `q_f9a0fa4ed236` (`dev_008`): `unanswerable` `'no debt data'` (`PipelineSystem` bị `disagreement`)
- **Kết quả (`PA = 0.64300`, giảm `-0.00200` so với `Sub #2`):**
  - Trong 14 câu `FastCore` cứu viện thêm, `FastCore` đúng **6 câu (`+6`)** và sai **8 câu (`-8`)**, tổng ròng **`-2 điểm`**.
  - **Kết luận thực nghiệm:** Không sử dụng `FastCore` trên các cửa hàng chưa từng thấy ở `public_test` / `private_test`, vì cả khi `FastCore` chạy trước (`Sub #1 = 0.62900`) lẫn khi `FastCore` chạy sau cứu viện (`Sub #3 = 0.64300`) đều làm giảm điểm do regex chọn cột và luật cứng `train` không khớp dữ liệu mới.

---

### Lần 4 — `Sub #4`: Pure `PipelineSystem` Sau Khi Sửa Lỗi Rulebook Poisoning (`PA = 0.65100`, tăng `+0.00600`)
- **Lệnh chạy:**
  ```bash
  .venv/bin/python -m datamate.predict --data-dir ./public_test --out-dir ./result_fresh --system pipeline_llm --workers 12
  ```
- **Thời gian chạy:** 09/11/2026 lúc 08:11 – 09:03 (~52 phút).
- **Hạ tầng:** 100% `PipelineSystem` (`Qwen3-14B-FP8` + DuckDB ETL) trên vLLM, đã trích xuất lại toàn bộ `public_test/rulebook.md` sạch sẽ.
- **Tổng phân bổ câu trả lời (`815 answered | 185 abstain`):**
  `number=464, abstain=185, percent=173, list=53, string=44, date=38, unanswerable=27, boolean=11, table=5`
- **So sánh trực tiếp với `Sub #2` (chạy `evals/compare_runs.py`):**
  - Độ tương đồng: **96.90%** (969/1000 câu trùng khớp kết quả).
  - Có 31 câu thay đổi:
    - `18 câu` chuyển từ trả lời sang **`abstain`** (10 number, 4 percent, 2 list, 1 date, 1 string) do rulebook mới định nghĩa chặt chẽ hơn hoặc kích hoạt `unsupported_knobs`.
    - `8 câu` từ `abstain` được trả lời thành công (4 number, 3 percent, 1 string).
    - `5 câu` đổi giá trị tính toán theo đúng quy tắc mới của `public_test/rulebook.md`.
- **Kết quả:** Điểm Public Leaderboard tăng lên **`0.65100` (`+6 điểm ròng` so với Sub #2)**, tiếp tục xác lập mốc điểm kỷ lục mới của dự án!

---

## 3. Phát Hiện & Sửa Lỗi Nghiêm Trọng: Rulebook Cache Poisoning (Nguyên Nhân Điểm `0.64500` Thay Vì `~0.680+`)

Khi kiểm tra lý do tại sao `Sub #2` (`pipeline_llm`) đạt `0.64500` thay vì `~0.680+` như chuẩn của `PipelineSystem`, chúng tôi phát hiện một lỗi **Cache Poisoning** cực kỳ nghiêm trọng xảy ra lúc `11:11:28 AM`:

1. **Hiện tượng trong file cache `result_submission/work/cache/rulebook/e2-v4/959ebb63b709fad68f7e8a339cde955c96b6e9af2e48141db3ad5a2429510e10.json`:**
   - Lúc `11:11:00` – `11:11:28`, `build_rulebook_config` phân loại thành công **33 dòng đầu tiên** (`0..32`) của `public_test/rulebook.md`.
   - Đúng lúc `11:11:28.547`, đường truyền Cloudflare Tunnel bị ngắt tạm thời ở dòng 33, làm `LLMClient` kích hoạt **Circuit Breaker** (`raise LLMUnavailable("server marked down")`).
   - Tuy nhiên, hàm [`_two_vote_json`](file:///home/iamhieu2012/Dev/zalo-aic-2026/src/datamate/rules/from_rulebook.py#L220-L245) trong `src/datamate/rules/from_rulebook.py` lại bắt `except Exception:` mà **không `raise LLMUnavailable`**, khiến toàn bộ **76 dòng rulebook còn lại (`33..108`)** và **cả 10/10 lần trích xuất tham số (`rulebook_extract_*`)** đều trả về `(None, False)` ngay lập tức trong `1.9 giây`!
   - Tai hại nhất: `build_rulebook_config` đã **lưu luôn kết quả rỗng (100% luật mặc định của `train`, `0` luật trích xuất từ `public_test/rulebook.md`, `0` `unsupported_knobs`) xuống đĩa cứng**!
   - Vì file cache đó đã tồn tại trên đĩa, cả `Sub #1`, `Sub #2` và `Sub #3` đều đọc lại file cache hỏng này và **chạy toàn bộ 1.000 câu hỏi bằng luật mặc định của tập `train`** (ví dụ: `exclude_orders_with_return`, `cancel_rate_denominator`, `shifts`, `week_start`, `month_this_compare`, `ranking_measure`, `customer_tie_break`, `non_product_line_labels`... đều chưa hề được cập nhật theo `public_test/rulebook.md`)!
2. **Đã khắc phục:**
   - Sửa [`_two_vote_json`](file:///home/iamhieu2012/Dev/zalo-aic-2026/src/datamate/rules/from_rulebook.py#L237-L240) để `except LLMUnavailable: raise` (không bao giờ nuốt lỗi mất kết nối server hoặc ghi cache hỏng xuống đĩa).
   - Xoá file cache rulebook bị hỏng (`959ebb63b709fad68f7e8a339cde955c96b6e9af2e48141db3ad5a2429510e10.json`).
   - Toàn bộ `6.219` file cache LLM (`mapping`, `parse_question`, `parse_ext_question`, v.v.) trong `result_submission/work/cache/llm/` vẫn được giữ nguyên, nên lần chạy lại `pipeline_llm` tiếp theo chỉ cần trích xuất lại `rulebook` (mất khoảng **1–2 phút** trên Colab GPU) và tính lại toàn bộ đáp án theo đúng luật của `public_test/rulebook.md`!

---

## 4. Vị Trí Lưu Trữ Dữ Liệu & Cache Trên Máy

- **Cache LLM & Schema Mapping (tái sử dụng cho mọi lần chạy tiếp theo, không tốn GPU lại):**
  - `./result_submission/work/cache/llm/` (toàn bộ JSON response từ `Qwen3-14B-FP8`)
  - `./result_submission/work/cache/mappings/` (schema mapping của cả 14 cửa hàng `dev_001` $\rightarrow$ `dev_014`)
  - `./result_submission/work/cache/canonical/` (file database `.duckdb` đã chuẩn hoá của 14 cửa hàng)
- **Lịch sử các bản Submission & Log:**
  - `./result_fresh/submission.jsonl` (Sub #4 — **0.65100**, kỷ lục mới nhất)
  - `./result_fresh/logs/` (1.000 file log chi tiết của Sub #4)
  - `./result_submission/history/run1_062900_fastcore_first_hybrid.jsonl`
  - `./result_submission/history/run1_062900_log.jsonl`
  - `./result_submission/history/run2_064500_pure_pipeline_llm.jsonl`
  - `./result_submission/history/run2_064500_log.jsonl`
  - `./result_submission/history/run3_llm_first_hybrid.jsonl`
  - `./result_submission/logs/<qid>.json` (1.000 file log chi tiết từng câu hỏi)
