# Data profiling: order_items, order_reviews

## 1. olist_order_items_dataset

- Số dòng: **112,650**, số cột: **7**
- Dòng trùng hoàn toàn: 0; trùng khóa (order_id + order_item_id): 0
- Định dạng 32 ký tự hex: order_id 112,650/112,650; product_id 112,650/112,650; seller_id 112,650/112,650
- Mỗi dòng = 1 đơn vị sản phẩm trong 1 đơn; mua 2 cái cùng sản phẩm → 2 dòng (không có cột quantity) → **grain của Fact bán hàng**

### 1.1 Thống kê theo cột

| Cột | Kiểu | Null | Distinct | Top 3 | Min | P25 | Median | Mean | P75 | P99 | Max | Skew | Ngoại lai IQR | Ghi chú |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| order_id | str | 0 (0.00%) | 98,666 | 8272b63d03f5f79c56e9e4120aec44ef (0.02%); 1b15974a0141d54e36626dca3fdc731a (0.02%); ab14fdcfbe524636d65ee38360e22ce8 (0.02%) |  |  |  |  |  |  |  |  |  |  |
| order_item_id | int64 | 0 (0.00%) | 21 |  | 1 | 1 | 1 | 1.20 | 1 | 4 | 21 | 7.58 | 13,984 (12.41%) |  |
| product_id | str | 0 (0.00%) | 32,951 | aca2eb7d00ea1a7b8ebd4e68314663af (0.47%); 99a4788cb24856965c36a24e339b6058 (0.43%); 422879e10f46682990de24d770e7f83d (0.43%) |  |  |  |  |  |  |  |  |  |  |
| seller_id | str | 0 (0.00%) | 3,095 | 6560211a19b47992c3666cc44a7e94c0 (1.80%); 4a3ca9315b744ce9f8e9374361493884 (1.76%); 1f50f920176fa81dab994f9023523100 (1.71%) |  |  |  |  |  |  |  |  |  |  |
| shipping_limit_date | datetime64[us] | 0 (0.00%) | 93,318 |  | 2016-09-19 00:15:34 |  |  |  |  |  | 2020-04-09 22:35:08 |  |  |  |
| price | float64 | 0 (0.00%) | 5,968 |  | 0.85 | 39.90 | 74.99 | 120.65 | 134.90 | 890 | 6,735 | 7.92 | 8,427 (7.48%) |  |
| freight_value | float64 | 0 (0.00%) | 6,999 |  | 0 | 13.08 | 16.26 | 19.99 | 21.15 | 84.52 | 409.68 | 5.64 | 12,134 (10.77%) |  |

### 1.2 Cấu trúc đơn hàng

- 98,666 đơn; số dòng/đơn: median 1, max 21; 9,803 đơn có > 1 dòng
- order_item_id liên tục 1..n trong mọi đơn: Có
- 7,088 cặp (đơn, sản phẩm) lặp > 1 dòng (tối đa 20) → số lượng = COUNT(*) theo order_id + product_id
- 1,278 đơn có hàng của > 1 seller → freight_value tính theo từng dòng, không phải theo đơn

### 1.3 price & freight_value

| Cột | Median | Mean | Max | Ngưỡng trên IQR | Vượt ngưỡng | = 0 | < 0 |
|---|---|---|---|---|---|---|---|
| price | 74.99 | 120.65 | 6,735.00 | 277.40 | 8,427 (7.48%) | 0 | 0 |
| freight_value | 16.26 | 19.99 | 409.68 | 33.25 | 11,613 (10.31%) | 383 | 0 |

- 4,124 dòng (3.66%) có phí ship > giá sản phẩm (hàng rẻ, nặng)
- Ngoại lai price theo IQR **trong từng danh mục**: 9,259 dòng (so với 8,427 (7.48%) khi tính trên toàn bảng)
- 5 dòng giá cao nhất: 6,735.00 (utilidades_domesticas); 6,729.00 (pcs); 6,499.00 (artes); 4,799.00 (eletroportateis); 4,690.00 (eletroportateis)

### 1.4 shipping_limit_date

- Từ 2016-09-19 00:15:34 đến 2020-04-09 22:35:08; số ngày sau khi mua: median 6, max 1,056
- 0 dòng có hạn giao trước ngày mua
- 12 dòng hạn giao > 60 ngày sau khi mua: 2020-02-05 03:30:51 (canceled); 2017-04-13 10:56:48 (processing); 2017-04-13 10:56:48 (processing); 2018-05-29 03:36:33 (canceled); 2018-01-10 22:49:21 (delivered)

### 1.5 Trạng thái đơn của các dòng bán hàng

| order_status | Số dòng | Tỷ lệ |
|---|---|---|
| delivered | 110197 | 97.82% |
| shipped | 1185 | 1.05% |
| canceled | 542 | 0.48% |
| invoiced | 359 | 0.32% |
| processing | 357 | 0.32% |
| unavailable | 7 | 0.01% |
| approved | 3 | 0.00% |

- 549 dòng thuộc đơn canceled/unavailable, giá trị 97,242.96 BRL (0.72% tổng price)

### 1.6 Toàn vẹn tham chiếu

| Kiểm tra | Số dòng |
|---|---|
| order_id không có trong orders | 0 |
| product_id không có trong products | 0 |
| seller_id không có trong sellers | 0 |
| Sản phẩm thiếu danh mục (dòng) | 1603 |

## 2. olist_order_reviews_dataset

- Số dòng: **99,224**, số cột: **7**
- Dòng trùng hoàn toàn: 0; trùng khóa (review_id): 814
- Định dạng 32 ký tự hex: review_id 99,224/99,224; order_id 99,224/99,224
- Trùng khóa (review_id + order_id): 0 → khóa đúng của bảng là cặp này

### 2.1 Thống kê theo cột

| Cột | Kiểu | Null | Distinct | Top 3 | Min | P25 | Median | Mean | P75 | P99 | Max | Skew | Ngoại lai IQR | Ghi chú |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| review_id | str | 0 (0.00%) | 98,410 | c444278834184f72b1484dfe47de7f97 (0.00%); 308316408775d1600dad81bd3184556d (0.00%); 2d6ac45f859465b5c185274a1c929637 (0.00%) |  |  |  |  |  |  |  |  |  |  |
| order_id | str | 0 (0.00%) | 98,673 | c88b1d1b157a9999ce368f218a407141 (0.00%); df56136b8031ecd28e200bb18e6ddb2e (0.00%); 03c939fd7fd3b38f8485a0f95798f1f6 (0.00%) |  |  |  |  |  |  |  |  |  |  |
| review_score | int64 | 0 (0.00%) | 5 |  | 1 | 4 | 5 | 4.09 | 5 | 5 | 5 | -1.36 | 14,575 (14.69%) |  |
| review_comment_title | str | 87,656 (88.34%) | 4,527 | Recomendo (0.43%); recomendo (0.35%); Bom (0.30%) |  |  |  |  |  |  |  |  |  |  |
| review_comment_message | str | 58,247 (58.70%) | 36,159 | Muito bom (0.23%); Bom (0.19%); muito bom (0.12%) |  |  |  |  |  |  |  |  |  |  |
| review_creation_date | datetime64[us] | 0 (0.00%) | 636 |  | 2016-10-02 00:00:00 |  |  |  |  |  | 2018-08-31 00:00:00 |  |  |  |
| review_answer_timestamp | datetime64[us] | 0 (0.00%) | 98,248 |  | 2016-10-07 18:32:28 |  |  |  |  |  | 2018-10-29 12:27:35 |  |  |  |

### 2.2 Trùng lặp

- 1,603 dòng dùng chung 789 review_id cho nhiều đơn; 789/789 review_id có nội dung giống hệt nhau giữa các đơn → 1 lần đánh giá áp cho nhiều đơn (khách mua nhiều đơn cùng lúc)
- 547 đơn có > 1 review (tối đa 3); 202 đơn trong số đó có điểm khác nhau giữa các review

### 2.3 review_score

| review_score | Số dòng | Tỷ lệ |
|---|---|---|
| 1 | 11424 | 11.51% |
| 2 | 3151 | 3.18% |
| 3 | 8179 | 8.24% |
| 4 | 19142 | 19.29% |
| 5 | 57328 | 57.78% |

- Mean 4.09, median 5; lệch về 5 điểm (J-shape) → báo cáo thêm tỷ lệ 1–2 điểm, không chỉ điểm trung bình

### 2.4 Bình luận (MNAR)

| Các cột cùng NULL | Số dòng |
|---|---|
| review_comment_title, review_comment_message | 56518 |
| review_comment_title | 31138 |
| (không thiếu) | 9839 |
| review_comment_message | 1729 |

- Tỷ lệ có bình luận theo điểm: 1★ 76.5%; 2★ 68.1%; 3★ 43.5%; 4★ 31.2%; 5★ 35.9% → khách không hài lòng viết bình luận nhiều hơn → khuyết **MNAR**, không điền
- Độ dài bình luận: median 53 ký tự, max 208; 27 bình luận chỉ có khoảng trắng → coi là NULL

### 2.5 Mốc thời gian

- review_creation_date gần như chỉ có ngày: 85 giá trị có giờ khác 00:00:00
- Thời gian từ gửi khảo sát → trả lời: median 40 giờ, max 519 ngày; trả lời trước khi tạo: 0
- 64 review được tạo trước ngày mua
- 5,127 review tạo trước ngày khách nhận hàng, điểm TB 1.99 (so với 4.09 toàn bộ) → khảo sát gửi theo ngày giao dự kiến, khách chưa nhận hàng thì chấm thấp
- 2,865 review thuộc đơn chưa giao tới khách, điểm TB 1.76

### 2.6 Toàn vẹn tham chiếu

- order_id không có trong orders: 0; đơn không có review: 768

## Tổng hợp vấn đề & đề xuất xử lý

1. order_items: price/freight lệch phải mạnh (price median 74.99, max 6,735.00); 383 dòng freight = 0 → giữ (giao dịch thật), dùng median và phân khoảng giá; phát hiện ngoại lai theo từng danh mục
2. order_items: 12 dòng shipping_limit_date > 60 ngày sau khi mua (max 2020-04-09) → gắn cờ; Dim_Date sinh theo min/max thực tế
3. order_items: 549 dòng thuộc đơn canceled/unavailable → giữ trong Fact, mang order_status; measure doanh thu trên Power BI lọc bỏ các trạng thái này
4. reviews: review_id không duy nhất (1,603 dòng), 547 đơn có > 1 review → khóa staging = review_id + order_id; dbt giữ review mới nhất (review_answer_timestamp) cho mỗi đơn
5. reviews: review_comment_title NULL 88.34%, message NULL 58.70% (MNAR) → giữ NULL, thêm cờ has_comment; GenAI/sentiment chỉ dùng phần có bình luận
6. reviews: 64 review tạo trước ngày mua → gắn cờ; 5,127 review tạo trước khi nhận hàng (điểm TB thấp) → là insight cho dashboard (giao trễ ↔ điểm thấp), không xóa
