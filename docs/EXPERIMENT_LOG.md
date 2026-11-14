# Nhật Ký Thực Nghiệm & Nộp Bài (Experiment & Submission Log)

Tài liệu này theo dõi các lần chạy thực nghiệm và nộp bài của dự án **Zalo AI Challenge 2026 — DataMate Track**.

---

## 1. Bảng Tổng Hợp Các Lần Chạy & Điểm Số

| Lần chạy | Thời gian | Chế độ (`--system`) | Cấu hình & Mô hình | Số câu trả lời / Abstain | Điểm **Public PA** | File Submission | Thư mục Logs |
|---|---|---|---|:---:|---:|---|---|
| **Run #1** | 09/11/2026 09:03 | `pipeline_llm` | Pure LLM (`Qwen3-14B-FP8`) + DuckDB Canonical ETL | **815 / 185** | **`0.65100`** | [`result_fresh/submission.jsonl`](file:///home/iamhieu2012/Dev/zalo-aic-2026/result_fresh/submission.jsonl) | [`result_fresh/logs/`](file:///home/iamhieu2012/Dev/zalo-aic-2026/result_fresh/logs) |

---

## 2. Chi Tiết Thực Nghiệm Run #1 (`result_fresh`)

### 2.1. Cấu Hình & Tham Số Thực Thi
- **Lệnh chạy:**
  ```bash
  .venv/bin/python -m datamate.predict \
    --data-dir ./public_test \
    --out-dir ./result_fresh \
    --system pipeline_llm \
    --workers 12 \
    --time-budget-s 18900
  ```
- **Hạ tầng & Mô hình:**
  - Mô hình: `Qwen/Qwen3-14B-FP8` (14.8B parameters $\le 15$B).
  - Backend: vLLM với `--max-model-len 16384`, `--enable-prefix-caching`, `--seed 0`.
  - Luồng xử lý: 12 workers song song.
- **Thời gian thực thi:**
  - Tổng thời gian (`total_wall_s`): **`3.122,36 giây` (~52 phút)** cho 1.000 câu hỏi.
  - Tốc độ trung bình: **`36,95 giây/câu`**.
  - Timeout: **`0 câu`**.

### 2.2. Phân Bổ Đáp Án Bài Nộp (`result_fresh/submission.jsonl`)

Tổng số câu: **1.000 câu** (`815` câu trả lời, `185` câu `abstain`):

| Loại đáp án (`type`) | Số lượng câu | Tỷ lệ (%) | Ý nghĩa nghiệp vụ |
|---|:---:|:---:|---|
| **`number`** | **464** | 46.4% | Doanh thu, số lượng bán, số đơn hàng, tồn kho, công nợ |
| **`abstain`** | **185** | 18.5% | Chủ động từ chối khi dữ liệu thiếu hoặc không chắc chắn để tránh phạt $-1$ điểm |
| **`percent`** | **173** | 17.3% | Tỷ lệ tăng trưởng, tỷ lệ hủy, tỷ trọng doanh thu (làm tròn 2 chữ số thập phân) |
| **`list`** | **53** | 5.3% | Danh sách mã/tên hàng bán chạy, khách hàng nợ |
| **`string`** | **44** | 4.4% | Tên hàng bán chạy nhất, tên nhà cung cấp |
| **`date`** | **38** | 3.8% | Ngày doanh thu cao nhất, hạn dùng lô hàng gần nhất |
| **`unanswerable`** | **27** | 2.7% | Bắt đúng các câu hỏi không có dữ liệu (hỏi ý kiến, thuộc tính không ghi chép) |
| **`boolean`** | **11** | 1.1% | Xu hướng liên tục tăng/giảm (`monotonic`) |
| **`table`** | **5** | 0.5% | Bảng số liệu chi tiết công nợ/nhân viên |

---

## 3. Kiến Trúc & Cấu Hình Đang Sử Dụng

- **Hệ thống suy luận:** Pure `PipelineSystem` ([src/datamate/systems/pipeline.py](file:///home/iamhieu2012/Dev/zalo-aic-2026/src/datamate/systems/pipeline.py)).
- **ETL:** DuckDB Canonical (11 bảng chuẩn hóa).
- **Phân tích câu hỏi:** 2-Vote Self-Consistency Parser (QuerySpec / ExtQuerySpec 34 họ mở rộng).
- **Kiểm chứng ngược (Reverse Description Verifier):** Đo logprob $p_{\text{yes}}$:
  - Ngưỡng chuẩn: $p_{\text{yes}} \ge 0.85$.
  - Ngưỡng khi split-vote: $p_{\text{yes}} \ge 0.90$.
- **Trích xuất quy tắc:** Phân tích toàn bộ `rulebook.md` của tập test và ánh xạ vào các tham số nghiệp vụ `RuleConfig`.

---

## 4. Kế Hoạch Thử Nghiệm Tiếp Theo

1. **Quét ngưỡng Verifier:** Chạy `evals/ext_threshold.py` để tìm ngưỡng $p_{\text{yes}}$ tối ưu nhằm tăng độ phủ mà vẫn giữ precision cao.
2. **Cải thiện họ `list` & `table`:** Tối ưu prompt sinh $K$ và tiêu chí sắp xếp cho các câu hỏi liệt kê.
3. **Mở rộng nhận diện `unanswerable`:** Tăng cường kiểm tra các thuộc tính bị thiếu ở các bảng kho và nhà cung cấp.
4. **Bật Thinking Retry:** Kích hoạt `ThinkingClient` cho các câu hỏi phức tạp bị bất đồng ở fast-pass.

---

## 5. Vị Trí Dữ Liệu & Cache

- **File nộp bài hiện tại:** [`result_fresh/submission.jsonl`](file:///home/iamhieu2012/Dev/zalo-aic-2026/result_fresh/submission.jsonl)
- **Log chi tiết 1.000 câu:** [`result_fresh/logs/`](file:///home/iamhieu2012/Dev/zalo-aic-2026/result_fresh/logs)
- **Cache LLM & ETL:** [`result_fresh/work/cache/`](file:///home/iamhieu2012/Dev/zalo-aic-2026/result_fresh/work/cache)
- **Thống kê thời gian:** [`result_fresh/timing.json`](file:///home/iamhieu2012/Dev/zalo-aic-2026/result_fresh/timing.json)
