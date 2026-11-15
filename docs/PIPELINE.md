# DataMate — Toàn Bộ Pipeline & Các Phiên Bản

Hệ thống `pipeline_llm` trả lời câu hỏi tiếng Việt trên dữ liệu bán hàng (CSV, Excel, SQLite) của hộ kinh doanh, tối
ưu Penalized Accuracy (đúng +1, abstain 0, sai −1). **LLM không tự tính số**: LLM chỉ đọc hiểu (ánh xạ cột, rulebook,
câu hỏi) và sinh cấu trúc; mọi con số do SQL tất định trên DuckDB tính.

Kết quả từng lần chạy: [`EXPERIMENT_LOG.md`](EXPERIMENT_LOG.md). Thể lệ: [`competition/`](competition/).

> **Trạng thái hiện tại (branch `lora-parser`, `50b6ded`):** LoRA cho bước đọc câu hỏi đã train xong (mục 6). Trên
> train tốt hơn base (`val` 0.9176 so với 0.9065, `holdout_family` 1.000 so với 0.983) nhưng **public chỉ 0.629**, thấp
> hơn bản gốc 0.651. Bản nộp tốt nhất vẫn là bản gốc (`result_fresh`, 0.651). Khi chạy không đặt `LLM_PARSE_MODEL`,
> pipeline chạy như `gemma-fixes`.

---

## 1. Tổng Quan Luồng Chạy

```text
<split>/                                   python -m datamate.predict --system pipeline_llm
├── questions.jsonl ─────────────┐
├── rulebook.md ──► [B] Rulebook ─┤  (1 lần / split)
├── calendar.csv ─────────────────┤
└── data/<shop>/ ─► [A] Dữ liệu ──┤  (1 lần / shop: đọc file → ánh xạ cột → ETL DuckDB)
                                  ▼
                         [C] Mỗi câu hỏi (song song --workers)
                                  │  parse → (verify) → MetricEngine SQL → định dạng đáp án
                                  ▼
<out-dir>/submission.jsonl, logs/<qid>.json, logs/log.jsonl, timing.json, work/cache/
```

| Bước | Mã nguồn | Chạy bao nhiêu lần | Gọi LLM? |
|---|---|---|---|
| A1. Đọc file thô | `io/raw.py` | 1 lần / shop | Không |
| A2. Hồ sơ cột | `io/profile.py` | 1 lần / shop | Không |
| A3. Ánh xạ cột → schema chuẩn | `mapping/infer.py`, `mapping/validate.py` | 1 lần / shop (cache) | Có |
| A4. ETL vào DuckDB | `etl/build.py`, `etl/store.py`, `etl/schema.py` | 1 lần / shop (cache) | Không |
| B. Rulebook → tham số | `rules/parse_rulebook.py`, `rules/from_rulebook.py`, `rules/knobs.py` | 1 lần / split (cache) | Có |
| C. Trả lời câu hỏi | `systems/pipeline.py`, `query/`, `metrics/`, `timeres/` | Mỗi câu | Có |
| D. Ghi kết quả | `predict.py`, `scoring/answer.py` | Mỗi câu + cuối lượt | Không |

---

## 2. Entrypoint — `src/datamate/predict.py`

```bash
.venv/bin/python -m datamate.predict \
  --data-dir ./public_test --out-dir ./result/<tên> \
  --system pipeline_llm --workers 12 --time-budget-s 18900
```

- `--system`: chỉ còn `pipeline_llm` (mặc định).
- `--workers`: số câu chạy song song (thread pool). Mỗi shop dựng dữ liệu một lần; câu của shop đó chờ khi đang dựng.
- `--time-budget-s` (mặc định 18.900 s = 5h15m): quá hạn thì không bắt đầu câu mới, câu còn lại ghi `abstain`
  (`abstain_reason = "time_budget"`) để luôn kịp trước mốc 6 giờ của Rule 7.
- Ghi `submission.jsonl` **từng dòng ngay khi có đáp án** (có `fsync`), nên dừng giữa chừng vẫn còn đáp án đã ghi.
- Mỗi câu có log `logs/<qid>.json` (id, đáp án, thời gian, trace: các vote, spec, SQL, lý do abstain…) và một dòng
  trong `logs/log.jsonl`.
- Câu mất vì server LLM không trả lời (`llm_unavailable`) được **chạy lại một lượt** cuối nếu còn thời gian.
- Cuối lượt: viết lại `submission.jsonl` đúng thứ tự `questions.jsonl` (đủ 1 dòng / câu), ghi `timing.json`, rồi kiểm
  tra định dạng bằng `evals/check_submission.py`.
- Cache (LLM, mapping, bảng chuẩn, rulebook) nằm trong `<out-dir>/work/cache/` → chạy lại cùng `--out-dir` không gọi
  lại LLM cho cùng truy vấn.

---

## 3. [A] Dữ Liệu Của Mỗi Shop

### A1. Đọc file thô — `io/raw.py`
- Đọc mọi `.csv`, `.xlsx` (python-calamine), `.sqlite` trong `data/<shop>/`.
- Dò dòng tiêu đề, gộp các sheet / file cùng cấu trúc (ví dụ mỗi tháng một sheet) thành một bảng, bỏ dòng trống và
  dòng tổng cộng / ghi chú. Mỗi dòng giữ nguồn `__file`, `__sheet`, `__row`. Ô giữ nguyên chuỗi gốc.

### A2. Hồ sơ cột — `io/profile.py`
- Mỗi cột: tỉ lệ trống, số giá trị khác nhau, loại giá trị (`date_dmy`, `money_text`, `number`, `int_serial_range`,
  `phone`, `id_like`, `text`…), giá trị hay gặp, ví dụ. Kèm README của shop. Đây là đầu vào cho bước ánh xạ.

### A3. Ánh xạ cột — `mapping/infer.py` (LLM, nhiều bước có kiểm tra)
| Bước | Việc LLM làm |
|---|---|
| A — vai trò bảng | Bảng nào là đơn hàng, dòng hàng, sản phẩm, khách, thanh toán, nợ, nhập hàng, tồn kho, lô… |
| B — trường theo thực thể | Cột thô nào ứng với trường chuẩn nào (`order_id`, `order_date`, `line_amount`, `qty`…) |
| C — trạng thái đơn | Giá trị trạng thái thô → `completed` / `cancelled` / `returned` / `shipping` |
| D — khách lẻ & trả hàng | Nhãn khách lẻ (`walk_in_values`) và cách ghi trả hàng (`negative_qty` hay `status`) |
| Trường bổ sung, trạng thái phiếu nhập | Các cột còn lại, trạng thái phiếu nhập (huỷ hay không) |

- Mỗi bước có nhiều biến thể prompt (độ dài README khác nhau) và vòng sửa khi kết quả không hợp lệ.
- `mapping/validate.py` kiểm tra mapping trên dữ liệu thật (cột tồn tại, đọc được ngày / tiền, nối khớp…). Trường hoặc
  bảng kiểm tra lỗi bị **cách ly** (`quarantined`) thay vì làm hỏng cả shop.
- Cache theo nội dung file của shop + model (`mapping/cache.py`).

### A4. ETL vào DuckDB — `etl/build.py`, `etl/store.py`
- 22 bảng chuẩn (`etl/schema.py`): `orders`, `order_lines`, `products`, `unit_conversions`, `customers`, `payments`,
  `debts`, `purchases`, `purchase_lines`, `suppliers`, `stock_snapshot`, `stock_moves`, `lots`, `sale_lots`,
  `price_history`, `expenses`, `employees`, `deliveries`, `drug_info`, `order_attributes`, `order_adjustments`,
  `order_measures`.
- Theo rulebook §8: điền tiếp mã đơn và ô cấp đơn cho các dòng sau của cùng đơn (theo từng file / sheet); bỏ dòng
  trùng y hệt **trong cùng một đơn**; bảng không có mã đơn thì không bỏ trùng.
- Đọc tiền (`19tr990`, `120k`, `1.480.000đ`), ngày (dd/mm/yyyy, serial Excel, ngày không năm → năm theo sheet), số
  lượng kèm đơn vị; quy đổi về đơn vị cơ bản (`qty_base`) theo bảng quy đổi / README.
- Xác định khách: theo mã khách nếu shop có mã, ngược lại theo tên đã chuẩn hoá; nhãn khách lẻ → `is_walk_in`.
- Cache theo nội dung file + fingerprint mapping + `ETL_VERSION`.

---

## 4. [B] Rulebook — `rules/`

1. `parse_rulebook.py`: tách `<split>/rulebook.md` thành từng dòng luật (`RuleRow`: mục, tên, nội dung).
2. `from_rulebook.py`: LLM **phân loại** từng dòng vào một tham số (`knob`) hoặc `other` (2 vote), rồi **trích giá trị**
   cho từng tham số (2 vote, phải khớp).
3. Kết quả là `RuleConfig` (`rules/model.py`), ví dụ: trạng thái tính doanh thu, có bỏ đơn có trả hàng, mẫu số tỉ lệ
   huỷ, ca sáng / chiều, ngày đầu tuần, cách so "tháng này", khoảng Tết, làm tròn, tiêu chí xếp hạng, nhãn COD / sàn
   không tính nợ, dòng không phải mặt hàng ("Phí phục vụ")…
4. Dòng luật không quy được về tham số được giữ làm `notes` (dùng cho thuật ngữ xếp hạng, đơn vị, thuộc tính).
   Tham số mà rulebook đổi sang giá trị code không hỗ trợ → `unsupported` → câu phụ thuộc vào nó abstain.
5. Cache theo SHA-256 của rulebook + `PROMPT_VERSION`. Khi server LLM mất kết nối, kết quả không được ghi cache.

---

## 5. [C] Trả Lời Một Câu Hỏi — `systems/pipeline.py`

Thứ tự xử lý (dừng ở bước đầu tiên ra đáp án):

1. **Chuẩn hoá cách viết** năm / tháng tắt (`th 11/25` → `tháng 11/2025`).
2. **Câu chủ quan** (LLM trả lời có / không, đọc xác suất; ngưỡng 0.9) → `unanswerable`. Bỏ qua bước này nếu câu hỏi
   dùng một thuật ngữ xếp hạng rulebook định nghĩa ("khách trung thành nhất" không phải hỏi ý kiến).
3. **Thuật ngữ xếp hạng trong rulebook** ("khách sộp nhất", "giờ cao điểm"…) → nhánh xếp hạng (`query/rank.py`,
   `metrics/rank.py`), có verifier (ngưỡng 0.9). Không khớp nhánh xếp hạng thì đi tiếp bước 4.
4. **Parser chính** (`query/parse.py`, `query/spec.py`): 2 vote LLM sinh `QuerySpec` dạng JSON theo schema:
   - chỉ số: `revenue`, `order_count`, `cancel_count`, `cancel_rate`, `avg_order_value`, `revenue_share`;
   - kiểu câu: `value`, `compare`, `series`, `multi`, `trend`, `argmax`;
   - kỳ thời gian (`timeres/periods.py`) và bộ lọc (kênh, hình thức thanh toán, nhóm khách, mặt hàng, nhóm hàng, ca).
   - Hai vote phải khớp sau khi quy kỳ về khoảng ngày; khớp → `MetricEngine` chạy SQL.
   - Khi đặt `LLM_PARSE_MODEL` (adapter LoRA, mục 6), parser chính và parser mở rộng gọi adapter với prompt **không
     kèm ví dụ mẫu**; mọi bước khác vẫn gọi model gốc.
   - **Đối chiếu phạm vi** (`lora_scope_crosscheck`, chỉ khi dùng adapter): adapter trả spec nhưng parser chính của
     model gốc (prompt có ví dụ) báo ngoài phạm vi → thử parser mở rộng trước; parser mở rộng abstain thì mới dùng spec
     của adapter. Lý do: adapter hay giành câu của nhóm mở rộng (vd. "bán được mấy đĩa" bị đọc thành doanh thu).
5. **Parser mở rộng** (`query/ext/`) khi parser chính báo ngoài phạm vi: 2 vote chọn một trong 34 nhóm nghiệp vụ —
   `qty_sold`, `top_products`, `unsold_products`, `products_in_min_orders`, `price_on_date`,
   `price_increase_effect`, `customers_min_orders`, `top_customers`, `orders_min_amount`, `days_min_revenue`,
   `debt_total`, `top_debtors`, `debt_aging`, `debt_added`, `debt_collected`, `customer_debt_flow`,
   `purchase_total`, `top_supplier`, `avg_purchase_cost`, `stock_on_hand`, `stock_value`, `ingredient_revenue`,
   `rx_share`, `rx_revenue`, `otc_revenue`, `gross_profit`, `top_employee`, `employee_revenue`, `delivery_count`
   (bật) và `out_of_stock_count`, `lots_expiring`, `nearest_expiry_lot`, `net_profit`, `orders_min_deliveries`
   (tắt trong `config.enabled_families`). Shop có sổ giao hàng hỏi parser sự kiện giao hàng trước (`query/events.py`).
   - Hai vote lệch nhau: chạy cả hai spec; nếu cả hai ra **cùng một đáp án thật** (không phải abstain /
     unanswerable) thì nhận spec đầu (`ext_answer_agreement`, chưa commit). Train: 41/41 câu được nhận đều đúng.
   - Nhóm `qty_sold` nêu đủ tên mặt hàng mà spec bỏ trống mặt hàng → abstain (`qty_sold_named_product_check`).
6. **Verifier mô tả ngược** (`query/ext/verify.py`): code dịch spec thành mô tả tiếng Anh, hỏi LLM "mô tả này có đúng là
   câu hỏi muốn không", đọc $p_{yes}$ từ logprob. Ngưỡng `ext_verify_threshold = 0.5`; khi một vote nói "ngoài phạm vi"
   (split-vote) thì `ext_verify_threshold_split = 0.9`.
7. **Thinking retry**: câu abstain vì `disagreement` / `parse_error` / `out_of_scope` / `ext_verify_low` được parse
   lại với thinking (`llm/thinking.py`, `thinking_max_tokens = 3072`).
8. **Viết lại câu hỏi** bằng tiếng Việt chuẩn (`parse/plain.py`) rồi parse lại.
9. **Nhánh phụ** sau khi vẫn abstain:
   - thuật ngữ đơn vị trong rulebook ("lượt xe", "phiếu") — `query/units.py`, `metrics/units.py`;
   - thuộc tính văn bản của sổ bán (dòng xe, việc làm, ghi chú) — `query/attributes.py`, `metrics/attributes.py`;
   - nhóm hàng shop không ghi → `unanswerable` (`query/missing_groups.py`);
   - thuộc tính khách shop không ghi (địa chỉ, giới tính…) → `unanswerable` (`query/missing_attributes.py`).
10. **Chặn unanswerable do mapping lỗi**: `unanswerable` mà lý do trỏ vào trường bị cách ly → đổi thành `abstain`.

Mọi lỗi ngoài dự kiến trong một câu đều thành `abstain` (không làm hỏng cả lượt chạy).

### MetricEngine — `metrics/engine.py`, `metrics/ext_families.py`, `metrics/ext_e4d.py`
- SQL tất định trên DuckDB, tham số lấy từ `RuleConfig`. Ví dụ: doanh thu = tổng `line_amount` của đơn có trạng thái
  tính doanh thu, bỏ đơn có trả hàng; tỉ lệ huỷ chia cho mọi đơn trong kỳ; giá trị trung bình đơn = doanh thu / số đơn
  hợp lệ; phần trăm thay đổi = (A − B) / B × 100; chênh lệch = A − B.
- Kỳ thời gian (`timeres/periods.py`, `timeres/calendar.py`): cắt cuối kỳ về `as_of_date`; tháng / quý không ghi năm mà
  sau hôm nay → năm trước; tuần từ thứ Hai; Tết theo lịch âm `calendar.csv`.
- Kỳ nằm hoàn toàn ngoài dữ liệu → `unanswerable`; kỳ có một phần dữ liệu → tính trên phần có.
- Shop thiếu trường cần cho nhóm câu hỏi → `Unanswerable(<trường>)`.
- Định dạng đáp án (`metrics/format.py`, `scoring/answer.py`): tiền nguyên VND, phần trăm 2 chữ số, ngày ISO, list theo
  thứ tự, bảng `{columns, rows}`.

---

## 6. LoRA Cho Bước Đọc Câu Hỏi (đã train, public kém hơn bản gốc)

Mục tiêu: model đọc câu hỏi ra `QuerySpec` / spec mở rộng đúng hơn và ổn định hơn. Chỉ dùng **train**; tổng tham số
14.8B + adapter (~0.06B) vẫn ≤ 15B.

### 6.1. Sinh nhãn — `lora/build_labels.py` (đã chạy)
1. Chạy `evals.run_eval` với Qwen3-14B trên `dev` + `poc` để lấp cache LLM (`cache/llm/`).
   Kết quả: `dev` 0.956 (1669 / 10 / 56), `poc` 0.984 (252 / 0 / 4).
2. `python -m lora.build_labels --subsets dev poc --out lora/data/labels.jsonl --workers 12`:
   - chạy lại parser chính (và parser mở rộng nếu chính báo ngoài phạm vi) đúng như pipeline — lấy từ cache;
   - mỗi vote: JSON → spec → `MetricEngine`; vote nào **ra đúng đáp án** `train/answers.jsonl` thành một ví dụ
     (vote đúng của câu bị lệch cũng được giữ);
   - câu cần parser mở rộng: thêm ví dụ dạy parser chính trả lời "ngoài phạm vi";
   - prompt của ví dụ là prompt parser **không kèm ví dụ mẫu** (`example_limit=0`, ~1.3k token thay vì ~5.8k).
3. Kết quả: **2.790 ví dụ từ 1.890 câu, 21 shop** (main 2.073 — trong đó 524 "ngoài phạm vi", ext 717). Bỏ 48 câu không
   có vote đúng, 53 câu đáp án unanswerable. `val` và `holdout_family` **không** có trong nhãn (dùng để đo).

### 6.2. Train — `lora/train_qlora.py`, `notebooks/train_lora.ipynb` (đã chạy, Colab)
- QLoRA 4-bit (nf4) trên `Qwen/Qwen3-14B`, LoRA rank 16 / alpha 32 trên mọi lớp linear, 2 epoch, lr 1e-4 cosine,
  batch 1 × grad-accum 16, độ dài tối đa 2.560 token.
- Prompt render bằng chat template với `enable_thinking=False` (giống vLLM lúc chạy); loss chỉ tính trên JSON trả lời.
- File đầu vào trên Drive: `MyDrive/datamate/labels.jsonl`, `MyDrive/datamate/train_qlora.py`.
  Checkpoint và adapter: `MyDrive/datamate/lora-parse-ckpt/`, `MyDrive/datamate/lora-parse/`. Colab ngắt thì chạy lại
  cell train, tự train tiếp từ checkpoint.
- Tương thích transformers 5.x: dùng `warmup_steps` (3% số bước) thay `warmup_ratio`, `dtype` thay `torch_dtype`.
- Kết quả: 350 bước, 1 giờ 17 phút, train loss trung bình 0.034, loss cuối 0.004 (rất thấp — dấu hiệu học thuộc).

### 6.3. Chạy với adapter
- `notebooks/colab_vllm.ipynb`: `MODEL_CHOICE = "qwen3-14b-lora"` (base FP8 + adapter) hoặc `"qwen3-14b-bf16-lora"`
  (base BF16, dự phòng nếu vLLM không chạy LoRA trên FP8). vLLM chạy với
  `--enable-lora --lora-modules datamate-parse=<adapter> --max-lora-rank 16`.
- `.env` thêm `LLM_PARSE_MODEL=datamate-parse`. Pipeline (`PipelineSystem.parse_client`) tạo client riêng cho adapter
  với `parse_example_limit = 0`; ánh xạ cột, rulebook, verifier, thinking retry, parser sự kiện giao hàng vẫn dùng model
  gốc với prompt có ví dụ.
- Test (`pytest`) phải chạy với `LLM_PARSE_MODEL=` để trống; nếu `.env` đang trỏ vào adapter thì 1 test pipeline fail.

### 6.4. Kết quả

Base và LoRA chạy trên cùng server (`qwen3-14b-bf16` + adapter `datamate-parse`):

| | Base BF16 | LoRA | LoRA + đối chiếu phạm vi |
|---|---|---|---|
| `val` (631) | 0.9065 (576 / 4) | 0.9081 (582 / 9) | **0.9176** (585 / 6) |
| `holdout_family` (120) | 0.9833 (118 / 0) | 0.9667 (118 / 2) | **1.0000** (120 / 0) |
| Public (1000) | 0.651 (bản gốc FP8) | — | **0.629** (849 trả lời / 151 abstain) |

- LoRA không đối chiếu: +12 câu đúng, +9 câu sai; 8/9 câu sai mới do parser chính của adapter, 7 câu là giành câu của
  nhóm mở rộng (`qty_sold`, `unit`, `top_customers`).
- Có đối chiếu: train tăng, nhưng public giảm 0.022 — adapter học từ 21 shop của train nên tự tin sai trên loại shop
  mới ở public; verifier không chặn được. Điểm train **không** dự đoán được điểm public (base cũng ~0.91 trên `val`).
- Hướng còn lại: chỉ cho adapter trả lời câu mà model gốc đã abstain (không đè lên câu model gốc đã trả lời); đo bằng
  `holdout_family` mở rộng (tách thêm loại shop khỏi nhãn) trước khi nộp.

---

## 7. LLM Client — `llm/client.py`

- Gọi API tương thích OpenAI của vLLM: `chat_json` (JSON theo schema, structured output), `chat_choice_probs` (một
  token, đọc xác suất các lựa chọn từ logprob), `count_tokens` (`/tokenize`).
- `temperature 0`, `seed` cố định; mặc định tắt thinking (`LLM_DISABLE_THINKING=true`), chỉ bật ở thinking retry.
- Cache mọi phản hồi theo băm của toàn bộ request (model, messages, schema, tham số).
- Bộ ngắt mạch: nhiều lần liên tiếp không có phản hồi → báo `llm_unavailable` ngay thay vì chờ timeout.
- Bỏ khối suy nghĩ trước khi đọc JSON: `<think>…</think>` (Qwen3) và `<|channel>…<channel|>` (Gemma 4, từ `810fd8e`).

---

## 8. Hạ Tầng

- **Colab** — `notebooks/colab_vllm.ipynb`: cài vLLM, chạy `vllm serve` (`--max-model-len 16384` với GPU ≥ 40 GB,
  `--enable-prefix-caching`, reasoning parser theo model), mở Cloudflare Tunnel, in `LLM_BASE_URL` / `LLM_API_KEY` /
  `LLM_MODEL` cho `.env`. Từ `810fd8e` có `MODEL_CHOICE` (`qwen3-14b` hoặc `gemma-4-12b`).
- **Colab chạy toàn bộ** — `notebooks/colab_pro_runner.ipynb`.
- **Train LoRA** — `notebooks/train_lora.ipynb` (mục 6.2).
- **Docker** — `docker/Dockerfile`, `docker/predict.sh`: khởi động vLLM trong container, chạy `pipeline_llm`; vLLM không
  lên được thì ghi toàn bộ `abstain` (không bao giờ ra điểm âm). Từ `a578a48`: mặc định base BF16 `Qwen3-14B`
  (tensor parallel 2) + adapter `/models/lora-parse`; `docker/build_vm.sh` build trên VM cloud. Bản đã nộp, cách build,
  upload Drive, checksum: `docker/README.md`.
- **Đánh giá trên train** — `evals/run_eval.py` (chấm với `train/answers.jsonl`, subset trong `evals/splits.yaml`),
  `evals/compare_runs.py` (so hai lần chạy), `evals/ext_threshold.py` (chọn ngưỡng verifier),
  `evals/check_submission.py` (kiểm tra định dạng).

---

## 9. Cấu Hình Chính — `src/datamate/config.py`

Đọc từ `.env` / biến môi trường (pydantic-settings, không phân biệt hoa thường).

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | — | Server vLLM |
| `LLM_DISABLE_THINKING` | `true` | Tắt thinking ở lệnh gọi thường |
| `parse_votes` | 2 | Số vote của parser |
| `parse_thinking` | `retry` | Parse lại với thinking khi abstain |
| `ext_verify_threshold` / `_split` | 0.5 / 0.9 | Ngưỡng verifier — **không tắt** (xem Run #3 trong log) |
| `enabled_families` | 29 nhóm | Nhóm mở rộng được phép trả lời |
| `subjective_threshold` | 0.9 | Ngưỡng câu chủ quan |
| `qty_sold_named_product_check` | `true` | (từ `810fd8e`) `qty_sold` thiếu mặt hàng → abstain |
| `ext_answer_agreement` | `true` | (từ `50b6ded`) 2 spec lệch nhưng cùng đáp án → nhận |
| `LLM_PARSE_MODEL` (`llm_parse_model`) | không đặt | (từ `50b6ded`) tên adapter LoRA cho parser; không đặt = model gốc |
| `parse_example_limit` | 0 | (từ `50b6ded`) số ví dụ mẫu trong prompt khi dùng adapter |
| `lora_scope_crosscheck` | `true` | (từ `50b6ded`) chỉ khi dùng adapter: model gốc báo ngoài phạm vi → thử parser mở rộng trước |

---

## 10. Các Phiên Bản

### Branch và commit

| Commit | Branch | Nội dung |
|---|---|---|
| `2d3f78d` | — | Bản gốc: `pipeline_llm` + FastCore (luật tất định) + hybrid + direct. Public **0.651** (Qwen3-14B) |
| `97f6a5e` | `main` | Dọn repo: chỉ giữ `pipeline_llm` (gỡ FastCore, hybrid, direct, `eval/`, `analysis/`); tài liệu sang `docs/`, notebook sang `notebooks/`; Docker mặc định `pipeline_llm`. **Code pipeline giống hệt `2d3f78d`**. Chạy lại Qwen: **0.643** |
| `810fd8e` | `gemma-fixes` | 3 bản sửa không gắn với model (tên ca, khách lẻ `ETL_VERSION` 1.15, `qty_sold` thiếu mặt hàng), bỏ khối suy nghĩ Gemma, notebook chọn model. Gemma verifier tắt: **0.505** |
| `50b6ded` | `lora-parser` | Chấp nhận 2 spec lệch khi cùng đáp án (`ext_answer_agreement`; Gemma verifier 0.5: **0.559**; Qwen: 814 / 186, chưa nộp). LoRA cho parser: `lora/build_labels.py`, `lora/train_qlora.py`, `notebooks/train_lora.ipynb`, LoRA trong `colab_vllm.ipynb`, `LLM_PARSE_MODEL`, `lora_scope_crosscheck`. Qwen + LoRA: **0.629** |

### Điểm public theo phiên bản × model

| Code | Qwen3-14B-FP8 | Gemma-4-12B-it |
|---|---:|---:|
| `2d3f78d` / `97f6a5e` (gốc) | **0.651** / 0.643 (chạy lại) | 0.523 |
| `810fd8e`, verifier tắt | — | 0.505 |
| `810fd8e` + answer-agreement, verifier 0.5 | chưa nộp (975/1000 câu trùng Run #1) | 0.559 |
| `50b6ded` + LoRA parser + đối chiếu phạm vi (base BF16) | 0.629 | — |

### Model đã dùng (Rule 2: tổng tham số ≤ 15B, weights công bố trước 01/10/2026)

| Model | Tham số | Phát hành | Giấy phép | Ghi chú |
|---|---:|---|---|---|
| `Qwen/Qwen3-14B-FP8` | 14.8B | 04/2025 | Apache-2.0 | Model chính, điểm cao nhất |
| `google/gemma-4-12B-it` | 11.95B | 05/2026 | Apache-2.0 | Thử nghiệm; kém Qwen ~0.09 trên public |

Chỉ dùng **một** model khi chạy (không ghép hai model, vì tổng 26.8B vượt 15B).
