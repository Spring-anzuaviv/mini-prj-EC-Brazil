# Data profiling: products, sellers, category translation

## 1. olist_products_dataset

- Số dòng: **32,951**, số cột: **9**
- Dòng trùng hoàn toàn: 0; product_id trùng: 0; product_id đúng định dạng 32 ký tự hex: 32,951/32,951
- Các cột số được đọc là float64 chỉ vì có NULL; số giá trị lẻ (không nguyên): 0 → nên lưu INT ở Data Warehouse

### 1.1 Thống kê theo cột

| Cột | Kiểu | Null | Distinct | Top 3 | Min | P25 | Median | Mean | P75 | P99 | Max | Skew | Ngoại lai IQR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| product_id | str | 0 (0.00%) | 32,951 | 1e9e8ef04dbcff4541ed26657ea517e5 (0.00%); 3aa071139cb16b67ca9e5dea641aaa2f (0.00%); 96bd76ec8810374ed1b65e291975717f (0.00%) |  |  |  |  |  |  |  |  |  |
| product_category_name | str | 610 (1.85%) | 73 | cama_mesa_banho (9.19%); esporte_lazer (8.70%); moveis_decoracao (8.06%) |  |  |  |  |  |  |  |  |  |
| product_name_lenght | float64 | 610 (1.85%) | 66 |  | 5 | 42 | 51 | 48.48 | 57 | 63 | 76 | -0.90 | 290 (0.88%) |
| product_description_lenght | float64 | 610 (1.85%) | 2,960 |  | 4 | 339 | 595 | 771.50 | 972 | 3,286.20 | 3,992 | 1.96 | 2,078 (6.31%) |
| product_photos_qty | float64 | 610 (1.85%) | 19 |  | 1 | 1 | 1 | 2.19 | 3 | 8 | 20 | 2.19 | 849 (2.58%) |
| product_weight_g | float64 | 2 (0.01%) | 2,204 |  | 0 | 300 | 700 | 2,276.47 | 1,900 | 22,538.00 | 40,425 | 3.60 | 4,551 (13.81%) |
| product_length_cm | float64 | 2 (0.01%) | 99 |  | 7 | 18 | 25 | 30.82 | 38 | 100 | 105 | 1.75 | 1,380 (4.19%) |
| product_height_cm | float64 | 2 (0.01%) | 102 |  | 2 | 8 | 13 | 16.94 | 21 | 69 | 105 | 2.14 | 1,892 (5.74%) |
| product_width_cm | float64 | 2 (0.01%) | 95 |  | 6 | 15 | 20 | 23.20 | 30 | 63 | 118 | 1.67 | 912 (2.77%) |

### 1.2 Mẫu giá trị thiếu (missing pattern)

| Các cột cùng NULL | Số dòng |
|---|---|
| (không thiếu) | 32340 |
| product_category_name, product_name_lenght, product_description_lenght, product_photos_qty | 609 |
| product_weight_g, product_length_cm, product_height_cm, product_width_cm | 1 |
| product_category_name, product_name_lenght, product_description_lenght, product_photos_qty, product_weight_g, product_length_cm, product_height_cm, product_width_cm | 1 |

### 1.3 Kiểm tra hợp lệ của cân nặng & kích thước

| Kiểm tra | Số dòng | Ghi chú |
|---|---|---|
| product_weight_g = 0 | 4 | Toàn bộ thuộc cama_mesa_banho |
| Kích thước đúng 16x2x11 cm (mặc định Correios) | 588 | Nhiều khả năng là kích thước nhập mặc định, không phải thật |
| Nặng > 10 kg nhưng thể tích < 1.000 cm³ | 11 | Mâu thuẫn cân nặng – kích thước |
| Mật độ > 5 g/cm³ (gấp 5 lần nước, gần bằng sắt ~7.8) | 64 | Nghi sai đơn vị/nhập liệu |
| Dài + cao + rộng > 200 cm | 1 | Vượt giới hạn gửi hàng Correios |
| product_name_lenght < 10 ký tự | 15 | Tên sản phẩm quá ngắn |
| product_description_lenght < 20 ký tự | 7 | Mô tả quá ngắn |

### 1.4 Phân bố danh mục

- 73 danh mục; top 10 danh mục chiếm 62.96% số sản phẩm; 6 danh mục có < 10 sản phẩm

| product_category_name | Số sản phẩm | Tỷ lệ |
|---|---|---|
| cama_mesa_banho | 3029 | 9.19% |
| esporte_lazer | 2867 | 8.70% |
| moveis_decoracao | 2657 | 8.06% |
| beleza_saude | 2444 | 7.42% |
| utilidades_domesticas | 2335 | 7.09% |
| fashion_roupa_infanto_juvenil | 5 | 0.02% |
| casa_conforto_2 | 5 | 0.02% |
| pc_gamer | 3 | 0.01% |
| seguros_e_servicos | 2 | 0.01% |
| cds_dvds_musicais | 1 | 0.00% |

### 1.5 Toàn vẹn tham chiếu

- Danh mục trong products **không có bản dịch**: pc_gamer, portateis_cozinha_e_preparadores_de_alimentos (13 sản phẩm)
- Sản phẩm chưa từng bán (không có trong order_items): 0
- product_id trong order_items không có trong products: 0
- Sản phẩm thiếu category xuất hiện ở 1,603 order item (1.42%), chiếm 1.32% doanh thu
- 18,117 sản phẩm (54.98%) chỉ bán đúng 1 lần (long tail)
- 1,225 sản phẩm được bán bởi > 1 seller (tối đa 8) → product không thuộc riêng seller nào

## 2. olist_sellers_dataset

- Số dòng: **3,095**, số cột: **4**
- Dòng trùng hoàn toàn: 0; seller_id trùng: 0; zip đúng 5 chữ số: 3,095/3,095; zip bắt đầu bằng 0: 1,027

### 2.1 Thống kê theo cột

| Cột | Kiểu | Null | Distinct | Top 3 |
|---|---|---|---|---|
| seller_id | str | 0 (0.00%) | 3,095 | 3442f8959a84dea7ee197c632cb2df15 (0.03%); d1b65fc7debc3361ea86b5f14c68d2e2 (0.03%); ce3ad9de960102d0677a81f5d0bb7b2d (0.03%) |
| seller_zip_code_prefix | str | 0 (0.00%) | 2,246 | 14940 (1.58%); 13660 (0.32%); 16200 (0.29%) |
| seller_city | str | 0 (0.00%) | 611 | sao paulo (22.42%); curitiba (4.10%); rio de janeiro (3.10%) |
| seller_state | str | 0 (0.00%) | 23 | SP (59.74%); PR (11.28%); MG (7.88%) |

### 2.2 Phân bố theo bang

- 23/27 bang có seller; SP chiếm 59.74%; 10 bang có ≤ 5 seller → phân tích theo bang cần gom nhóm vùng

| seller_state | Số seller | Tỷ lệ |
|---|---|---|
| SP | 1849 | 59.74% |
| PR | 349 | 11.28% |
| MG | 244 | 7.88% |
| SC | 190 | 6.14% |
| RJ | 171 | 5.53% |
| RS | 129 | 4.17% |
| GO | 40 | 1.29% |
| DF | 30 | 0.97% |
| ES | 23 | 0.74% |
| BA | 19 | 0.61% |
| CE | 13 | 0.42% |
| PE | 9 | 0.29% |
| PB | 6 | 0.19% |
| RN | 5 | 0.16% |
| MS | 5 | 0.16% |
| MT | 4 | 0.13% |
| RO | 2 | 0.06% |
| SE | 2 | 0.06% |
| AC | 1 | 0.03% |
| PI | 1 | 0.03% |
| MA | 1 | 0.03% |
| AM | 1 | 0.03% |
| PA | 1 | 0.03% |

### 2.3 Chất lượng seller_city

- 611 giá trị gốc → 606 sau khi bỏ dấu/khoảng trắng
- 34 dòng chứa ký tự ngoài [a-z ] (dấu, '/', '-', ',', số, email)
- 23 dòng gộp cả tên bang vào city, VD: 'lages - sc'; 'auriflama/sp'; 'sao paulo / sao paulo'; 'novo hamburgo, rio grande do sul, brasil'; 'cariacica / es'
- Giá trị rác (không phải tên thành phố): ['04482255', 'vendas@creditparts.com.br']
- Biến thể cùng 1 thành phố: ferraz de vasconcelos: ['ferraz de vasconcelos', 'ferraz de  vasconcelos']; santa barbara d oeste: ['santa barbara d´oeste', 'santa barbara d oeste']; sao jose dos pinhais: ['sao jose dos pinhais', 'sao  jose dos pinhais']; sao paulo: ['sao paulo', 'são paulo', 'sao  paulo']

### 2.4 Đối chiếu zip/state với geolocation

- 7 seller có zip không tồn tại trong geolocation: 82040, 91901, 72580, 02285, 07412, 71551, 37708
- 35 seller có seller_state khác bang suy ra từ zip (33 trường hợp ghi nhầm thành 'SP')

| seller_zip_code_prefix | seller_city | seller_state | geo_state |
|---|---|---|---|
| 95076 | caxias do sul | SP | RS |
| 21210 | rio de janeiro | RN | RJ |
| 85301 | laranjeiras do sul | SP | PR |
| 87360 | goioere | SP | PR |
| 86170 | sertanopolis | SP | PR |
| 85960 | marechal candido rondon | SP | PR |
| 22783 | rio de janeiro | SP | RJ |
| 36512 | tocantins | SP | MG |
| 27277 | volta redonda | SP | RJ |
| 31570 | belo horizonte | SP | MG |

### 2.5 Hoạt động bán hàng (join order_items)

- Seller không có đơn: 0; seller_id trong order_items không có trong sellers: 0
- Số đơn/seller: median 6, mean 32.3, max 1,854; 571 seller chỉ có 1 đơn
- Top 10% seller chiếm 68.4% số đơn (phân phối rất tập trung)
- Số sản phẩm/seller: median 4, max 399

## 3. product_category_name_translation

- Số dòng: **71**, số cột: **2**
- File có BOM UTF-8: **Có**
- Null: 0; trùng tên PT: 0; trùng tên EN: 0
- Giá trị không theo định dạng snake_case: không có
- Bản dịch giống hệt tên gốc: ['consoles_games', 'audio', 'cool_stuff', 'pet_shop', 'market_place', 'la_cuisine', 'dvds_blu_ray']
- Bản dịch có lỗi/hậu tố khó hiểu: fashion_roupa_feminina → fashio_female_clothing; eletrodomesticos_2 → home_appliances_2; casa_conforto_2 → home_comfort_2
- Danh mục có bản dịch nhưng không có sản phẩm: không có

## Tổng hợp vấn đề & đề xuất xử lý

1. products: 610 sản phẩm thiếu category + name/description/photos (luôn thiếu cùng nhau) → gán 'unknown' ở dim_product
2. products: 2 sản phẩm thiếu toàn bộ cân nặng & kích thước
3. products: 4 sản phẩm cân nặng = 0 g → đặt NULL (không dùng 0 khi tính TB)
4. products: 11 sản phẩm nặng > 10 kg nhưng thể tích < 1 lít, 64 sản phẩm mật độ > 5 g/cm³ → gắn cờ nghi ngờ khi phân tích phí vận chuyển
5. products: phân phối lệch phải mạnh (weight skew 3.6) → dùng median/bin thay vì mean
6. products ↔ translation: 2 danh mục (pc_gamer, portateis_cozinha_e_preparadores_de_alimentos) không có tên tiếng Anh → bổ sung thủ công trong dbt seed
7. products: tên cột sai chính tả product_name_lenght / product_description_lenght → đổi ở dbt
8. sellers: seller_city bẩn (34 dòng: kèm bang, có dấu, email, số) → chuẩn hóa và ưu tiên phân tích theo state
9. sellers: 35 seller_state mâu thuẫn với zip (đa số ghi 'SP') → suy lại bang từ zip qua geolocation
10. sellers: 7 zip không có trong geolocation → không vẽ được bản đồ, cho phép NULL lat/lng
11. translation: file có BOM → đọc bằng utf-8-sig / cấu hình encoding ở Mage, nếu không cột đầu thành '\ufeffproduct_category_name'
12. translation: thiếu danh mục (xem mục 1.5), có lỗi chính tả 'fashio_female_clothing', hậu tố '_2' → tạo seed dbt chuẩn hóa tên hiển thị (VD: Title Case, thay '_' bằng khoảng trắng)
