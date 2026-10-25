---
name: data-profiling-cleaning
description: Data profiling và làm sạch dữ liệu cho mini project BI "Brazilian E-Commerce (Olist)" — profile 9 file CSV trong rawData/ bằng pandas (cấu trúc, nội dung, quan hệ khoá), tính bảng chất lượng cột (Null, Completeness, Cardinality, Uniqueness, Validity, pattern, IQR), chẩn đoán lỗi theo 6 chiều chất lượng DAMA, phân loại missing MCAR/MAR/MNAR, rồi quyết định xử lý ở tầng nào (Staging trên SQL Server / dbt models + dbt tests / Power BI) và chuyển kết quả sang thiết kế Data Warehouse (grain, Fact, Dimension). Dùng khi người dùng nói "profile dữ liệu", "data profiling", "kiểm tra chất lượng dữ liệu", "làm sạch dữ liệu", "clean data", "xử lý missing/outlier/duplicate", "viết dbt test", "bảng vấn đề dữ liệu", hoặc làm phần mô tả/chất lượng dữ liệu trong báo cáo project.
---

# Data Profiling → Làm sạch dữ liệu (Olist BI project)

> **"Garbage In, Garbage Out"** — không thiết kế Fact/Dimension hay vẽ dashboard nào trước khi
> profile dữ liệu. Mọi quyết định làm sạch phải **dựa trên số liệu profiling**, không sửa "mù".

## Bối cảnh project

- **Dataset**: [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
  — tải bằng `download_data.py` (kagglehub) vào `rawData/`. Dữ liệu **tĩnh**, ~100k đơn hàng 2016–2018.
- **Kiến trúc** (theo `2627_Yeu_cau_mini_prj.md`):
  `CSV → Mage.ai (ingestion, Full/Incremental) → SQL Server Staging → dbt (làm sạch, chuẩn hoá, tests)
  → Data Warehouse (Star/Snowflake) → Power BI (Semantic Model, DAX, 2 dashboard) → GenAI (summary/giải thích)`.
- **Vai trò của profiling trong project**: phát hiện vấn đề → ghi vào bảng vấn đề → quyết định
  **tầng xử lý** → hiện thực hoá ở dbt và **khoá lại bằng dbt tests**. Profiling bằng Python chỉ để
  *khám phá & làm bằng chứng cho báo cáo*; dữ liệu sạch được tạo ra **trong dbt**, không phải bằng
  file `*_clean.csv`.

### 9 bảng nguồn

| File (`rawData/`) | Dòng | Khoá | Ghi chú |
|---|---|---|---|
| `olist_orders_dataset.csv` | 99,441 | `order_id` | 5 cột thời gian, `order_status` |
| `olist_order_items_dataset.csv` | 112,650 | `order_id + order_item_id` | `price`, `freight_value` → grain Fact bán hàng |
| `olist_order_payments_dataset.csv` | 103,886 | `order_id + payment_sequential` | |
| `olist_order_reviews_dataset.csv` | 99,224 | `review_id` **không duy nhất** | |
| `olist_customers_dataset.csv` | 99,441 | `customer_id` | `customer_unique_id` mới là khách thật |
| `olist_products_dataset.csv` | 32,951 | `product_id` | cột sai chính tả `*_lenght` |
| `olist_sellers_dataset.csv` | 3,095 | `seller_id` | |
| `olist_geolocation_dataset.csv` | 1,000,163 | `zip_code_prefix` **không duy nhất** | nhiều toạ độ / zip |
| `product_category_name_translation.csv` | 71 | `product_category_name` | file có BOM UTF-8 |

### Tài sản đã có — đọc trước khi làm lại

Toàn bộ code profiling nằm trong package `profiling/`; chạy tất cả bằng `python run_profiling.py`
(hoặc một số bước: `python run_profiling.py issues reports`; từng module: `python -m profiling.issues`).

| Module | Nội dung | Đầu ra |
|---|---|---|
| `profiling/common.py` | Đường dẫn, `TABLE_FILES` (tên ngắn → file), khoá, hằng số nghiệp vụ (khung toạ độ Brazil, dải CEP, kích thước mặc định…), `read_table` / `load_tables`, `save_csv`, helper tính toán | – |
| `profiling/overview.py` | Tổng quan từng bảng: số dòng/cột, khoá, phạm vi thời gian (Bảng 2.1) | `output/Bang_Tong_Quan_Du_Lieu.csv` |
| `profiling/column_quality.py` | Thống kê chất lượng từng cột (Bảng 2.2) | `output/Bang_Chat_Luong_Cot.csv` (rút gọn), `output/Bang_Chat_Luong_Cot_DayDu.csv` (phụ lục) |
| `profiling/relationships.py` | Toàn vẹn tham chiếu giữa các bảng (Bảng 2.4) | `output/Bang_Quan_He_Bang.csv` |
| `profiling/issues.py` | 28 check vấn đề dữ liệu (Bảng 2.5) | `output/Bang_Van_De_Du_Lieu.csv` |
| `profiling/reports/*.py` | Báo cáo chi tiết từng nhóm bảng (products_sellers, geolocation, orders_payments_customers, items_reviews); khối Markdown dùng chung ở `reports/markdown.py` | `output/dataProfiling/Profiling_*.md` |

**Quy ước code & đầu ra của project** (giữ nguyên khi viết code mới):
- Đọc dữ liệu **chỉ qua** `read_table("<tên ngắn>")` / `load_tables(...)`: tự đọc cột mã (`*_id`, trừ
  `order_item_id`) và `*_zip_code_prefix` dạng chuỗi, parse cột thời gian, đếm lỗi định dạng ngày
  (`df.attrs["parse_errors"]`), mỗi file chỉ đọc 1 lần trong một lần chạy.
- Hằng số và helper dùng chung đặt trong `profiling/common.py`, không khai báo lại trong module khác.
- Bảng kết quả ghi bằng `save_csv(df, "Bang_<Tên>.csv")` → `output/`, `utf-8-sig`, tên cột tiếng Việt;
  báo cáo Markdown ghi bằng `run_report(...)` → `output/dataProfiling/`.
- Mỗi module có `main()` gọi `setup_console()` trước khi in (Windows terminal), và được đăng ký trong
  `STEPS` của `run_profiling.py`.
- Mỗi check nghiệp vụ là một hàm `check_xxx(t) -> dict | None` trong `profiling/issues.py`, thêm vào
  **cuối** `ISSUE_CHECKS` để STT các vấn đề cũ không đổi.

---

## Nguyên tắc bắt buộc

1. **Không sửa file trong `rawData/`.** Staging trên SQL Server cũng giữ nguyên giá trị gốc
   (chỉ ép kiểu an toàn) để truy vết; làm sạch ở dbt.
2. **Profile → ghi vấn đề → xử lý → kiểm tra lại.** Mỗi vấn đề phải có *bằng chứng số liệu* và
   một *dbt test* (hoặc truy vấn đối chiếu) chứng minh đã xử lý.
3. **Mọi thay đổi có lý do, ghi vào `output/Bang_Van_De_Du_Lieu.csv`** (qua `profiling/issues.py`) (STT – Vấn đề – Bằng chứng –
   Ảnh hưởng đến phân tích – Hướng xử lý – Tầng xử lý).
4. **Phân biệt "sai chắc chắn" và "bất thường"**: toạ độ ngoài Brazil, giao hàng trước khi mua là
   sai → gắn cờ/loại khỏi phép tính; `price` = 6,735 BRL là giao dịch thật → giữ.
   Không xoá dòng Fact chỉ vì bất thường — **gắn cờ** (`is_invalid_timeline`, `is_outlier`...) để
   Power BI lọc được.
5. **Hiểu ngữ nghĩa trước khi xử lý** — vd `customer_id` sinh mới mỗi đơn; một đơn có nhiều
   payment/review; đơn `canceled`/`unavailable` hợp lệ khi không có ngày giao.

---

## Quy trình 8 bước

```
1. Load & hiểu ngữ cảnh → 2. Profiling (Structure / Content / Relationship)
→ 3. Bảng chất lượng cột → 4. Chẩn đoán lỗi theo 6 chiều DAMA
→ 5. Phân loại missing → 6. Quyết định tầng xử lý & hiện thực (Staging / dbt / Power BI)
→ 7. Validate bằng dbt tests + re-profile → 8. Chuyển sang thiết kế DW & báo cáo
```

### Bước 1 — Load & hiểu ngữ cảnh

- Đọc cột định danh/zip dạng chuỗi; cột thời gian parse bằng `pd.to_datetime(errors="coerce")`
  và đếm số giá trị bị coerce thành NaT (đó là lỗi định dạng, không phải missing).
- Ghi lại cho mỗi bảng: số dòng, số cột, **mỗi dòng là gì** (1 đơn? 1 dòng sản phẩm trong đơn?
  1 lần thanh toán?), khoá dự kiến, phạm vi thời gian.
- `geolocation` ~1 triệu dòng: đọc `usecols`/kiểu gọn (`float32` cho lat/lng) nếu chậm.

### Bước 2 — Profiling theo 3 loại khám phá

| Loại | Câu hỏi | Kiểm tra trên Olist |
|---|---|---|
| **Structure** | Đúng định dạng/kiểu? | id = 32 ký tự hex; zip = 5 chữ số; timestamp `YYYY-MM-DD HH:MM:SS`; cột số đọc thành float chỉ vì có NULL (thực chất INT) |
| **Content** | Giá trị hợp lý? | % null, distinct, min/max/median, IQR của `price`, `freight_value`, `payment_value`, kích thước/cân nặng; giá trị 0; `not_defined` |
| **Relationship** | Liên kết đúng? | khoá chính unique; khoá ngoại tồn tại ở bảng cha; quan hệ 1–1 / 1–n / n–n; phụ thuộc hàm (zip → state, `order_status` ↔ ngày giao, thứ tự mốc thời gian) |

### Bước 3 — Bảng chất lượng cột

Với mỗi cột (đã có sẵn trong `profiling/column_quality.py`, bổ sung nếu thiếu):

| Chỉ số | Công thức / Ý nghĩa |
|---|---|
| **Null / Actual** | Số ô rỗng; Actual = Rows − Null |
| **Completeness** | Actual / Rows |
| **Cardinality** | Số giá trị phân biệt |
| **Uniqueness** | Cardinality / Rows — cột khoá phải = 100% |
| **Distinctness** | Cardinality / Actual |
| **Validity** | % khớp quy tắc (id `^[0-9a-f]{32}$`, zip `^\d{5}$`, state ∈ 27 bang) |
| **Min/Max/Mean/Median/Mode** | Cột số và cột thời gian |
| **Top patterns** | chữ → `s`, số → `d` (vd zip `01003` → `ddddd`); pattern hiếm thường là lỗi |
| **Outliers (IQR)** | Ngưỡng = Q1 − 1.5·IQR / Q3 + 1.5·IQR; với `price` nên tính **theo danh mục** |

**Đọc bảng**: Completeness < 100% → Bước 5; khoá có Uniqueness < 100% → trùng (review_id,
geolocation zip); cardinality cao bất thường ở cột phân loại → chưa chuẩn hoá (city);
Mean ≫ Median → lệch phải (price, freight, weight) → báo cáo median bên cạnh mean.

### Bước 4 — Chẩn đoán theo 6 chiều chất lượng (DAMA)

| Chiều | Câu hỏi | Ví dụ trong Olist |
|---|---|---|
| **Completeness** | Đủ dữ liệu bắt buộc? | 610 sản phẩm thiếu danh mục; 2,965 đơn thiếu `order_delivered_customer_date` |
| **Uniqueness** | Có trùng? | 1,603 dòng `review_id` trùng; 261,831 dòng geolocation trùng hoàn toàn |
| **Timeliness** | Đúng thời điểm? | `shipping_limit_date` tới 2020; tháng đầu/cuối kỳ rất ít đơn (2016-09, 2018-09/10) |
| **Validity** | Đúng quy tắc? | 42 toạ độ ngoài Brazil; `payment_installments = 0`; `payment_type = not_defined`; city là email/số |
| **Accuracy** | Đúng thực tế? | Kích thước mặc định 16×2×11 cm (588 sp); mật độ > 5 g/cm³; seller_state ghi nhầm `SP` |
| **Consistency** | Nhất quán? | `são paulo`/`sao paulo`; đơn `delivered` không có ngày giao; tổng payment ≠ price + freight |

Kết quả ghi vào `output/Bang_Van_De_Du_Lieu.csv` (hiện có 28 vấn đề — **thêm check vào `profiling/issues.py`, đừng tạo bảng song song**).

### Bước 5 — Dữ liệu khuyết: phân loại rồi mới xử lý

| Loại | Ý nghĩa | Ví dụ Olist → xử lý |
|---|---|---|
| **MCAR** | Khuyết ngẫu nhiên toàn bộ | 2 sản phẩm thiếu cân nặng/kích thước → giữ NULL (ảnh hưởng không đáng kể) |
| **MAR** | Khuyết phụ thuộc cột quan sát được | `order_delivered_customer_date` NULL tập trung ở `order_status ≠ delivered` → **không điền**; chỉ tính KPI giao hàng cho đơn `delivered` có đủ ngày |
| **MNAR** | Khuyết do chính bản chất giá trị | `review_comment_message` (58.7%) / `title` (88.3%) trống vì khách không viết → giữ NULL + cờ `has_comment` |
| **Cấu trúc** | Khuyết theo khối cột | 609 sản phẩm thiếu cùng lúc category + name/description/photos → 1 nguyên nhân (thiếu metadata) → category = `'unknown'`, số giữ NULL |

Kiểm tra nhanh: tạo cờ `is_missing`, `groupby` theo cột phân loại (status, category, state) xem tỷ lệ
khuyết có khác nhau không; dùng "missing pattern" (tổ hợp cột cùng NULL) bằng `null_pattern()` trong
`profiling/reports/markdown.py`.

**Với dữ liệu giao dịch cho BI, mặc định là KHÔNG impute** giá trị đo lường (mean/median/KNN sẽ
bịa ra doanh thu, ngày giao, điểm review). Chỉ điền **nhãn** cho thuộc tính dimension
(`'unknown'`, `'not_defined'`) để không mất dòng khi group by trên Power BI.

### Bước 6 — Quyết định tầng xử lý & hiện thực

| Tầng | Làm gì | Ví dụ |
|---|---|---|
| **Staging (Mage → SQL Server)** | Nạp nguyên trạng, chỉ ép kiểu an toàn; ghi log số dòng/lỗi mỗi lần chạy | zip `VARCHAR(5)`; id `CHAR(32)`/`VARCHAR(32)`; city `NVARCHAR` (có dấu); timestamp `DATETIME2`; khoá staging reviews = `review_id + order_id` |
| **dbt – staging models (`stg_*`)** | Đổi tên, ép kiểu, chuẩn hoá chuỗi, khử trùng, gắn cờ | `*_lenght → *_length`; chuẩn hoá city (bỏ dấu, lower, trim, gộp khoảng trắng); review mới nhất / đơn; geolocation lọc ngoài Brazil + gom 1 dòng / zip |
| **dbt – intermediate/marts (`int_*`, `dim_*`, `fct_*`)** | Tích hợp, tính cột dẫn xuất, áp quy tắc nghiệp vụ | `customer_unique_id` làm khoá Dim_Customer; `revenue = price + freight_value`; `delivery_days`, `is_late`, `is_invalid_timeline`; bổ sung bản dịch 2 danh mục thiếu |
| **Power BI** | Phạm vi phân tích, cảnh báo hiển thị | Lọc 2017-01 → 2018-08 cho so sánh theo tháng/YoY; hiển thị median cạnh mean |

Thứ tự trong dbt (để bước sau không làm hỏng bước trước): trim/chuẩn hoá chuỗi → ép kiểu
(`TRY_CAST`, lỗi → NULL + cờ) → chuẩn hoá giá trị phân loại bằng mapping → khử trùng
(`ROW_NUMBER()`) → đánh dấu giá trị không hợp lệ → gắn cờ ngoại lai → điền nhãn missing cho
dimension → kiểm tra quan hệ → cột dẫn xuất.

**Trùng lặp**: dòng giống hệt (geolocation) → bỏ; trùng khoá nhưng khác nội dung (review_id dùng
cho nhiều đơn, đơn có nhiều review) → **không xoá mù**, chọn bản ghi theo quy tắc nghiệp vụ và ghi lý do.

**Ngoại lai**: IQR để phát hiện, quyết định theo ngữ nghĩa — giữ (giá cao thật), gắn cờ, hoặc
NULL nếu chắc chắn sai (toạ độ, mốc thời gian ngược). Ngoại lai thường chính là insight cho dashboard.

### Bước 7 — Validate bằng dbt tests + re-profile

- Mỗi vấn đề trong bảng vấn đề ↔ ít nhất một test:
  `unique`, `not_null`, `relationships`, `accepted_values` (generic) hoặc singular test
  (`tests/*.sql` trả về dòng vi phạm). Dùng `severity: warn` cho vấn đề đã biết và chấp nhận
  (vd đơn `delivered` thiếu ngày giao) thay vì để pipeline fail.
- Đối chiếu số dòng: staging ↔ `stg_*` ↔ fact (vd số đơn từ orders vs order_items lệch 775 —
  phải giải thích được).
- Chạy lại script profiling (hoặc truy vấn tương đương trên `stg_*`) và đặt **trước/sau** cạnh nhau
  trong báo cáo.
- `dbt docs generate` để mô tả model/cột — đề bài yêu cầu tài liệu dbt.

### Bước 8 — Chuyển sang thiết kế Data Warehouse & báo cáo

Từ kết quả profiling, xác định:
- **Quy trình nghiệp vụ & grain**: Fact bán hàng = 1 dòng `order_items` (order_id + order_item_id);
  có thể thêm Fact thanh toán (order_id + payment_sequential), Fact đánh giá (1 review / đơn).
- **Dimension**: Date (sinh theo min/max thực tế của mọi cột ngày, tới 2020), Customer
  (`customer_unique_id`), Product (+ category tiếng Anh), Seller, Geography (zip → city → state, đã gom),
  Order Status, Payment Type.
- **Measures**: doanh thu, phí ship, số đơn, AOV, số ngày giao, % giao trễ, điểm review TB...
- **Hierarchy**: Date: Day → Month → Quarter → Year; Geography: City → State → Region.

Bảng thuộc tính (dùng trong phần "Mô tả dataset" của báo cáo), mã số/zip là **C** dù viết bằng số:

| Attribute | Type (C/O/Q) | Vai trò DW | Hierarchical | Semantic |
|---|---|---|---|---|
| order_id | C | Degenerate dim / khoá | – | Mã đơn hàng |
| price | Q | Measure | – | Giá sản phẩm (BRL) |
| order_purchase_timestamp | O/Q (thời gian) | FK → Dim_Date | Day–Month–Year | Thời điểm mua |
| customer_state | C | Thuộc tính Dim_Geography | City → State | Bang của khách |
| review_score | O | Measure / thuộc tính | – | Điểm 1–5 |

---

## Mẫu báo cáo profiling (`output/dataProfiling/<Tên>.md`)

```markdown
# Data Profiling – <bảng hoặc nhóm bảng>
## 1. Tổng quan (số dòng/cột, mỗi dòng là gì, khoá, phạm vi thời gian)
## 2. Thống kê theo cột (Null, Distinct, Top, Min/P25/Median/Mean/P75/Max, IQR)
## 3. Missing pattern & phân loại MCAR/MAR/MNAR
## 4. Kiểm tra hợp lệ & nhất quán (quy tắc nghiệp vụ, có số dòng vi phạm)
## 5. Toàn vẹn tham chiếu (khoá ngoại, quan hệ 1–1/1–n/n–n)
## 6. Tổng hợp vấn đề → hướng xử lý → tầng xử lý → dbt test tương ứng
```

---

## Code mẫu

### pandas — profiling (theo quy ước project)

Thêm một check vấn đề mới vào `profiling/issues.py` (rồi thêm tên hàm vào cuối `ISSUE_CHECKS`):

```python
def check_missing_delivery_by_status(t: Tables) -> dict[str, str] | None:
    orders = t["orders"]
    # MCAR hay MAR: tỷ lệ khuyết của cột theo từng nhóm của một cột phân loại.
    by_status = orders["order_delivered_customer_date"].isna().groupby(orders["order_status"]).mean()
    if by_status.max() == by_status.min():
        return None
    return issue(
        "Ngày giao thiếu theo trạng thái đơn (MAR)",
        "; ".join(f"{status}: {ratio:.1%}" for status, ratio in by_status.sort_values().items()),
        "Điền ngày giao giả sẽ làm sai KPI giao hàng",
        "Giữ NULL; KPI giao hàng chỉ tính đơn delivered có đủ ngày",
        "dbt",
    )
```

Phân tích nhanh trong một script/notebook riêng (dùng chung cách đọc dữ liệu của project):

```python
from profiling.common import iqr_bounds, read_table, save_csv, setup_console

setup_console()
items = read_table("order_items")  # tên ngắn trong TABLE_FILES; mã/zip là chuỗi, ngày đã parse
low, high = iqr_bounds(items["price"])
outliers = items[items["price"] > high]
save_csv(outliers.describe().reset_index(), "Bang_Ngoai_Lai_Price.csv")  # → output/
```

### dbt (SQL Server) — staging model

```sql
-- models/staging/stg_order_reviews.sql : giữ đánh giá mới nhất cho mỗi đơn
with src as (
    select *,
           row_number() over (
               partition by order_id
               order by try_cast(review_answer_timestamp as datetime2) desc
           ) as rn
    from {{ source('staging', 'olist_order_reviews') }}
)
select
    review_id,
    order_id,
    try_cast(review_score as tinyint)                   as review_score,
    nullif(ltrim(rtrim(review_comment_message)), '')    as review_comment_message,
    case when nullif(ltrim(rtrim(review_comment_message)), '') is null
         then 0 else 1 end                              as has_comment,
    try_cast(review_creation_date as datetime2)         as review_creation_date,
    try_cast(review_answer_timestamp as datetime2)      as review_answer_timestamp
from src
where rn = 1
```

### dbt — tests

```yaml
# models/staging/_stg__models.yml
models:
  - name: stg_order_reviews
    columns:
      - name: order_id
        tests: [unique, not_null,
                {relationships: {to: ref('stg_orders'), field: order_id}}]
      - name: review_score
        tests: [{accepted_values: {values: [1, 2, 3, 4, 5], quote: false}}]
  - name: stg_orders
    columns:
      - name: order_status
        tests:
          - accepted_values:
              values: [delivered, shipped, canceled, unavailable, invoiced,
                       processing, created, approved]
```

```sql
-- tests/assert_delivered_orders_have_delivery_date.sql (severity warn trong config)
{{ config(severity='warn') }}
select order_id
from {{ ref('stg_orders') }}
where order_status = 'delivered' and order_delivered_customer_date is null
```

---

## Ghi chú riêng cho Olist (đã xác nhận bằng profiling)

- **Khách hàng**: 99,441 `customer_id` nhưng 96,096 `customer_unique_id` → đếm khách, tỷ lệ quay
  lại phải dùng `customer_unique_id`.
- **Reviews**: `review_id` trùng 1,603 dòng; 547 đơn có > 1 review → nối thẳng vào order_items sẽ
  nhân bản doanh thu.
- **Orders ↔ items/payments**: 775 đơn không có item (phần lớn `unavailable`/`canceled`); 1 đơn
  không có payment. Fact bán hàng lấy từ order_items.
- **Thời gian**: 166 đơn giao cho vận chuyển trước khi mua; 23 đơn khách nhận trước khi giao vận
  chuyển → `is_invalid_timeline`. `shipping_limit_date` max 2020-04-09.
- **Danh mục**: 610 NULL; `pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos` thiếu bản
  dịch → seed dbt bổ sung bản dịch.
- **Payments**: 9 dòng `payment_value = 0`, 2 dòng `installments = 0`, 3 dòng `not_defined`;
  249 đơn lệch > 1 BRL giữa tổng payment và price + freight → doanh thu thống nhất lấy từ order_items.
- **Geolocation**: 52.6 dòng / zip trung bình, 42 toạ độ ngoài Brazil → lọc theo khung toạ độ rồi
  gom 1 dòng / zip trước khi nối; 278 customer và 7 seller có zip không có trong geolocation.
- **Địa lý**: city không nhất quán (dấu, khoảng trắng, `'lages - sc'`, email/số trong `seller_city`);
  35 seller có state khác state suy ra từ zip → ưu tiên phân tích theo **state**.
- **Products**: 588 sản phẩm kích thước mặc định 16×2×11 cm; 4 sản phẩm nặng 0 g; 64 sản phẩm mật độ
  > 5 g/cm³ → gắn cờ, không dùng cho phân tích logistics theo kích thước.
- **Seller tập trung**: SP chiếm 59.7% seller; top 10% seller chiếm 68.4% số đơn → nên dùng
  thang log/top-N trên dashboard.

## Lỗi hay mắc

- Đọc zip/id dạng số → mất số 0 đầu, nối với geolocation thất bại.
- Join reviews/payments/geolocation trực tiếp vào order_items → nhân bản dòng, sai doanh thu.
- Đếm khách theo `customer_id`.
- Impute ngày giao, điểm review hay giá bằng mean/median → bịa ra số liệu trên dashboard.
- Tính thời gian giao trung bình trên cả đơn chưa giao / timeline ngược.
- So sánh theo tháng bao gồm các tháng gần như không có dữ liệu (2016, 2018-09/10).
- Làm sạch trong pandas rồi nạp file sạch vào DW → sai kiến trúc đề bài (làm sạch phải ở dbt và có test).
- Tạo bảng vấn đề mới thay vì thêm check vào `profiling/issues.py`; không có bằng chứng số liệu trong báo cáo.
