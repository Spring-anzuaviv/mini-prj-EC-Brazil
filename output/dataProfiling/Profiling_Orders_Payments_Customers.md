# Data profiling: orders, order_payments, customers

## 1. olist_orders_dataset

- Số dòng: **99,441**, số cột: **8**
- Dòng trùng hoàn toàn: 0; trùng khóa (order_id): 0
- Định dạng 32 ký tự hex: order_id 99,441/99,441; customer_id 99,441/99,441
- Mỗi dòng = 1 đơn hàng; 5 cột thời gian đều đúng định dạng `YYYY-MM-DD HH:MM:SS`

### 1.1 Thống kê theo cột

| Cột | Kiểu | Null | Distinct | Top 3 | Min | Max | Ghi chú |
|---|---|---|---|---|---|---|---|
| order_id | str | 0 (0.00%) | 99,441 | e481f51cbdc54678b7cc49136f2d6af7 (0.00%); 53cdb2fc8bc7dce0b6741e2150273451 (0.00%); 47770eb9100c2d0c44946d9cf07ec65d (0.00%) |  |  |  |
| customer_id | str | 0 (0.00%) | 99,441 | 9ef432eb6251297304e76186b10a928d (0.00%); b0830fb4747a6c6d20dea0b8c802d7ef (0.00%); 41ce2a54c0b03bf3443c3d931a367089 (0.00%) |  |  |  |
| order_status | str | 0 (0.00%) | 8 | delivered (97.02%); shipped (1.11%); canceled (0.63%) |  |  |  |
| order_purchase_timestamp | datetime64[us] | 0 (0.00%) | 98,875 |  | 2016-09-04 21:15:19 | 2018-10-17 17:30:18 |  |
| order_approved_at | datetime64[us] | 160 (0.16%) | 90,733 |  | 2016-09-15 12:16:38 | 2018-09-03 17:40:06 |  |
| order_delivered_carrier_date | datetime64[us] | 1,783 (1.79%) | 81,018 |  | 2016-10-08 10:34:01 | 2018-09-11 19:48:28 |  |
| order_delivered_customer_date | datetime64[us] | 2,965 (2.98%) | 95,664 |  | 2016-10-11 13:46:32 | 2018-10-17 13:22:46 |  |
| order_estimated_delivery_date | datetime64[us] | 0 (0.00%) | 459 |  | 2016-09-30 00:00:00 | 2018-11-12 00:00:00 |  |

### 1.2 Phân bố order_status

| order_status | Số dòng | Tỷ lệ |
|---|---|---|
| delivered | 96478 | 97.02% |
| shipped | 1107 | 1.11% |
| canceled | 625 | 0.63% |
| unavailable | 609 | 0.61% |
| invoiced | 314 | 0.32% |
| processing | 301 | 0.30% |
| created | 5 | 0.01% |
| approved | 2 | 0.00% |

### 1.3 Giá trị thiếu theo trạng thái đơn (kiểm tra MAR)

| Các cột cùng NULL | Số dòng |
|---|---|
| (không thiếu) | 96461 |
| order_delivered_carrier_date, order_delivered_customer_date | 1636 |
| order_delivered_customer_date | 1183 |
| order_approved_at, order_delivered_carrier_date, order_delivered_customer_date | 146 |
| order_approved_at | 14 |
| order_delivered_carrier_date | 1 |

Số dòng NULL theo từng trạng thái:

| order_status | order_approved_at | order_delivered_carrier_date | order_delivered_customer_date | Số đơn |
|---|---|---|---|---|
| delivered | 14 | 2 | 8 | 96478 |
| shipped | 0 | 0 | 1107 | 1107 |
| canceled | 141 | 550 | 619 | 625 |
| unavailable | 0 | 609 | 609 | 609 |
| invoiced | 0 | 314 | 314 | 314 |
| processing | 0 | 301 | 301 | 301 |
| created | 5 | 5 | 5 | 5 |
| approved | 0 | 2 | 2 | 2 |

- NULL tập trung ở các trạng thái chưa giao (canceled, unavailable, shipped, invoiced...) → **MAR**, đúng nghiệp vụ, **không điền giá trị**

### 1.4 Mâu thuẫn giữa trạng thái và ngày giao

| Kiểm tra | Số đơn |
|---|---|
| delivered nhưng thiếu order_delivered_customer_date | 8 |
| delivered nhưng thiếu order_delivered_carrier_date | 2 |
| delivered nhưng thiếu order_approved_at | 14 |
| Chưa delivered nhưng có order_delivered_customer_date | 6 |
| canceled nhưng đã giao tới khách | 6 |

### 1.5 Thứ tự các mốc thời gian

| Vi phạm | Số đơn |
|---|---|
| order_approved_at < order_purchase_timestamp | 0 |
| order_delivered_carrier_date < order_purchase_timestamp | 166 |
| order_delivered_carrier_date < order_approved_at | 1359 |
| order_delivered_customer_date < order_delivered_carrier_date | 23 |
| order_delivered_customer_date < order_purchase_timestamp | 0 |
| order_estimated_delivery_date < order_purchase_timestamp | 0 |

- Giao vận chuyển trước khi duyệt: lệch median 17 giờ, 901/1,359 đơn lệch < 24 giờ → nhiều khả năng ghi nhận duyệt trễ, chỉ gắn cờ, vẫn dùng được để tính thời gian giao (mua → khách nhận)
- Timeline sai thật (giao vận chuyển trước khi mua, khách nhận trước khi giao vận chuyển/mua): 189 đơn

### 1.6 Thời gian xử lý & giao hàng (đơn delivered, đủ ngày, timeline hợp lệ)

- Số đơn dùng để tính: 96,282/99,441
- Số ngày giao (mua → khách nhận): median 10.2, mean 12.6, P99 46, max 210; 306 đơn > 60 ngày
- Thời gian duyệt (mua → duyệt): median 0.34 giờ, P99 90 giờ, max 31 ngày
- Giao trễ so với ngày dự kiến: 6,532 đơn (6.78%)
- order_estimated_delivery_date luôn là 00:00:00 (0 giá trị có giờ khác 0) → chỉ là ngày, so sánh trễ hạn phải theo ngày (không theo giờ)

### 1.7 Số đơn theo tháng

- Từ 2016-09-04 21:15:19 đến 2018-10-17 17:30:18; 25 tháng; trung vị 4,285 đơn/tháng
- Tháng có < 10% trung vị: 2016-09: 4, 2016-10: 324, 2016-12: 1, 2018-09: 16, 2018-10: 4
- Tháng không có đơn nào: 2016-11

| Tháng | Số đơn |
|---|---|
| 2016-09 | 4 |
| 2016-10 | 324 |
| 2016-12 | 1 |
| 2017-01 | 800 |
| 2017-02 | 1780 |
| 2017-03 | 2682 |
| 2017-04 | 2404 |
| 2017-05 | 3700 |
| 2017-06 | 3245 |
| 2017-07 | 4026 |
| 2017-08 | 4331 |
| 2017-09 | 4285 |
| 2017-10 | 4631 |
| 2017-11 | 7544 |
| 2017-12 | 5673 |
| 2018-01 | 7269 |
| 2018-02 | 6728 |
| 2018-03 | 7211 |
| 2018-04 | 6939 |
| 2018-05 | 6873 |
| 2018-06 | 6167 |
| 2018-07 | 6292 |
| 2018-08 | 6512 |
| 2018-09 | 16 |
| 2018-10 | 4 |

### 1.8 Toàn vẹn tham chiếu

- customer_id trong orders không có trong customers: 0; tối đa 1 đơn / customer_id → quan hệ 1–1
- Đơn hàng không có dòng ở bảng con:

| Bảng con | Số đơn | Theo trạng thái |
|---|---|---|
| order_items | 775 | unavailable: 603; canceled: 164; created: 5; invoiced: 2; shipped: 1 |
| payments | 1 | delivered: 1 |
| reviews | 768 | delivered: 646; shipped: 75; canceled: 20; unavailable: 14; processing: 6; invoiced: 5; created: 2 |

## 2. olist_order_payments_dataset

- Số dòng: **103,886**, số cột: **5**
- Dòng trùng hoàn toàn: 0; trùng khóa (order_id + payment_sequential): 0
- Định dạng 32 ký tự hex: order_id 103,886/103,886
- Mỗi dòng = 1 lần thanh toán của 1 đơn (1 đơn có thể trả bằng nhiều phương thức/voucher)

### 2.1 Thống kê theo cột

| Cột | Kiểu | Null | Distinct | Top 3 | Min | P25 | Median | Mean | P75 | P99 | Max | Skew | Ngoại lai IQR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| order_id | str | 0 (0.00%) | 99,440 | fa65dad1b0e818e3ccc5cb0e39231352 (0.03%); ccf804e764ed5650cd8759557269dc13 (0.03%); 285c2e15bebd4ac83635ccc563dc71f4 (0.02%) |  |  |  |  |  |  |  |  |  |
| payment_sequential | int64 | 0 (0.00%) | 29 |  | 1 | 1 | 1 | 1.09 | 1 | 3 | 29 | 16.18 | 4,526 (4.36%) |
| payment_type | str | 0 (0.00%) | 5 | credit_card (73.92%); boleto (19.04%); voucher (5.56%) |  |  |  |  |  |  |  |  |  |
| payment_installments | int64 | 0 (0.00%) | 24 |  | 0 | 1 | 1 | 2.85 | 4 | 10 | 24 | 1.66 | 6,313 (6.08%) |
| payment_value | float64 | 0 (0.00%) | 29,077 |  | 0 | 56.79 | 100 | 154.10 | 171.84 | 1,039.92 | 13,664.08 | 9.25 | 7,981 (7.68%) |

### 2.2 Phương thức thanh toán

| payment_type | Số dòng | Giá trị TB | Trả góp > 1 kỳ | Số kỳ max | payment_value = 0 |
|---|---|---|---|---|---|
| credit_card | 76795 | 163.32 | 51338 | 24 | 0 |
| boleto | 19784 | 145.03 | 0 | 1 | 0 |
| voucher | 5775 | 65.7 | 0 | 1 | 6 |
| debit_card | 1529 | 142.57 | 0 | 1 | 0 |
| not_defined | 3 | 0.0 | 0 | 1 | 3 |

- 3 dòng payment_type = 'not_defined', đều thuộc đơn: canceled (3)
- Chỉ credit_card có trả góp > 1 kỳ → hợp lý về nghiệp vụ

### 2.3 Giá trị bất thường

- payment_installments = 0: 2 dòng (loại: credit_card) → tối thiểu phải là 1
- payment_value = 0: 9 dòng (loại: voucher 6, not_defined 3)
- payment_value: median 100.00, P99 1,039.92, max 13,664.08 → lệch phải (skew 9.3)

### 2.4 Cấu trúc nhiều lần thanh toán

- 2,961 đơn có > 1 dòng thanh toán (tối đa 29); 2,246 đơn dùng > 1 phương thức
- 80 đơn có payment_sequential không liên tục (số lớn nhất ≠ số dòng) → thiếu dòng thanh toán
- Tổ hợp phương thức: credit_card + voucher: 2245; credit_card + debit_card: 1

### 2.5 Đối chiếu với giá trị đơn hàng (order_items)

- 249/98,665 đơn lệch > 1 BRL giữa tổng thanh toán và price + freight (232 trả nhiều hơn, 17 trả ít hơn); lệch lớn nhất 182.81 BRL
- 775 đơn có thanh toán nhưng không có order_items
- 1 đơn không có thanh toán: bfbd0f9bdef84302105ad712db648a6c (delivered)

## 3. olist_customers_dataset

- Số dòng: **99,441**, số cột: **5**
- Dòng trùng hoàn toàn: 0; trùng khóa (customer_id): 0
- Định dạng 32 ký tự hex: customer_id 99,441/99,441; customer_unique_id 99,441/99,441
- Mỗi dòng = 1 customer_id gắn với **1 đơn hàng**; zip đúng 5 chữ số: 99,441/99,441; zip bắt đầu bằng 0: 23,995

### 3.1 Thống kê theo cột

| Cột | Kiểu | Null | Distinct | Top 3 |
|---|---|---|---|---|
| customer_id | str | 0 (0.00%) | 99,441 | 06b8999e2fba1a1fbc88172c00ba8bc7 (0.00%); 18955e83d337fd6b2def6b18a428ac77 (0.00%); 4e7b3e00288586ebd08712fdd0374a03 (0.00%) |
| customer_unique_id | str | 0 (0.00%) | 96,096 | 8d50f5eadf50201ccdcedfb9e2ac8455 (0.02%); 3e43e6105506432c953e165fb2acf44c (0.01%); 1b6c7548a2a1f9037c1fd3ddfed95f33 (0.01%) |
| customer_zip_code_prefix | str | 0 (0.00%) | 14,994 | 22790 (0.14%); 24220 (0.12%); 22793 (0.12%) |
| customer_city | str | 0 (0.00%) | 4,119 | sao paulo (15.63%); rio de janeiro (6.92%); belo horizonte (2.79%) |
| customer_state | str | 0 (0.00%) | 27 | SP (41.98%); RJ (12.92%); MG (11.70%) |

### 3.2 customer_id và customer_unique_id

- 99,441 customer_id nhưng chỉ 96,096 customer_unique_id → customer_id được sinh mới cho mỗi đơn
- 2,997 khách (3.12%) mua > 1 lần, tối đa 17 đơn → tỷ lệ khách quay lại rất thấp
- 252 khách có > 1 địa chỉ (zip/city/state) giữa các đơn → Dim_Customer cần chọn địa chỉ (VD địa chỉ của đơn gần nhất) hoặc để địa chỉ ở cấp đơn hàng

### 3.3 Chất lượng địa chỉ

- customer_city: 4,119 giá trị gốc → 4,119 sau chuẩn hóa; 1 dòng có ký tự ngoài [a-z' -], VD: 'quilometro 14 do mutum'
- customer_state: 27 bang; mã không hợp lệ: không có
- 0 khách có customer_state khác bang suy ra từ dải CEP
- 0 khách có customer_state khác bang của zip trong geolocation
- 278 khách (157 zip) không có zip trong geolocation → không có tọa độ

### 3.4 Phân bố theo bang

| customer_state | Số dòng | Tỷ lệ |
|---|---|---|
| SP | 41746 | 41.98% |
| RJ | 12852 | 12.92% |
| MG | 11635 | 11.70% |
| RS | 5466 | 5.50% |
| PR | 5045 | 5.07% |
| SC | 3637 | 3.66% |
| BA | 3380 | 3.40% |
| DF | 2140 | 2.15% |
| ES | 2033 | 2.04% |
| GO | 2020 | 2.03% |
| PE | 1652 | 1.66% |
| CE | 1336 | 1.34% |
| PA | 975 | 0.98% |
| MT | 907 | 0.91% |
| MA | 747 | 0.75% |
| MS | 715 | 0.72% |
| PB | 536 | 0.54% |
| PI | 495 | 0.50% |
| RN | 485 | 0.49% |
| AL | 413 | 0.42% |
| SE | 350 | 0.35% |
| TO | 280 | 0.28% |
| RO | 253 | 0.25% |
| AM | 148 | 0.15% |
| AC | 81 | 0.08% |
| AP | 68 | 0.07% |
| RR | 46 | 0.05% |

- Top 3 bang (SP, RJ, MG) chiếm 66.61%; 10 bang có < 500 khách

- Liên kết: 99,441/99,441 đơn nối được với customers; 0 customer không có đơn

## Tổng hợp vấn đề & đề xuất xử lý

1. orders: 8 đơn 'delivered' thiếu ngày giao, 6 đơn chưa 'delivered' nhưng có ngày giao → gắn cờ is_status_conflict; KPI giao hàng chỉ tính đơn delivered có đủ ngày
2. orders: 189 đơn có mốc thời gian ngược (giao vận chuyển trước khi mua, khách nhận trước khi giao vận chuyển) → gắn cờ is_invalid_timeline, loại khỏi phép tính thời gian giao
3. orders: 1,359 đơn giao vận chuyển trước khi duyệt (median lệch 17 giờ) → gắn cờ is_approved_after_carrier, không loại khỏi KPI giao hàng
4. orders: thời gian giao lệch phải (median 10 ngày, max 210) → dùng median trên dashboard; is_late so theo ngày vì order_estimated_delivery_date không có giờ
5. orders: 5 tháng đầu/cuối kỳ gần như không có dữ liệu (2016-09, 2016-10, 2016-12, 2018-09, 2018-10) → giới hạn phạm vi so sánh theo tháng/YoY (VD 2017-01 → 2018-08)
6. orders: 775 đơn không có order_items, 1 đơn không có payments, 768 đơn không có review → Fact bán hàng lấy grain từ order_items; giải thích chênh lệch số đơn
7. payments: 2 dòng installments = 0, 9 dòng payment_value = 0, 3 dòng 'not_defined' (đơn canceled) → installments 0 → 1; gắn cờ, giữ nguyên dòng
8. payments: 249 đơn có tổng thanh toán lệch price + freight (có thể do lãi trả góp, voucher) → doanh thu lấy từ order_items; payments chỉ dùng cho phân tích phương thức thanh toán
9. payments: 80 đơn có payment_sequential bị đứt quãng → chỉ ghi nhận, không dùng sequential làm số lần trả
10. customers: 99,441 customer_id / 96,096 customer_unique_id; 2,997 khách mua > 1 lần → khóa tự nhiên Dim_Customer = customer_unique_id; đếm khách bằng DISTINCT customer_unique_id
11. customers: 252 khách đổi địa chỉ giữa các đơn → lấy địa chỉ của đơn gần nhất cho Dim_Customer, phân tích địa lý theo địa chỉ ở từng đơn
12. customers: 278 khách có zip không có tọa độ, 0 khách có bang trái dải CEP → LEFT JOIN geolocation; phân tích địa lý ưu tiên theo customer_state
