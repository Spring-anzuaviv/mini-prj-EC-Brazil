# Data profiling: olist_geolocation

## 1. Tổng quan

- Số dòng: **1,000,163**, số cột: **5**
- Dòng trùng hoàn toàn: 261,831; trùng khóa (geolocation_zip_code_prefix): 981,148
- Mỗi dòng = 1 điểm tọa độ của 1 zip prefix (không phải 1 địa chỉ); zip đúng 5 chữ số: 1,000,163/1,000,163; zip bắt đầu bằng 0: 245,733

### 1.1 Thống kê theo cột

| Cột | Kiểu | Null | Distinct | Top 3 | Min | P25 | Median | Mean | P75 | P99 | Max | Skew | Ngoại lai IQR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| geolocation_zip_code_prefix | str | 0 (0.00%) | 19,015 | 24220 (0.11%); 24230 (0.11%); 38400 (0.10%) |  |  |  |  |  |  |  |  |  |
| geolocation_lat | float64 | 0 (0.00%) | 717,360 |  | -36.61 | -23.60 | -22.92 | -21.18 | -19.98 | -2.50 | 45.07 | 1.57 | 168,240 (16.82%) |
| geolocation_lng | float64 | 0 (0.00%) | 717,613 |  | -101.47 | -48.57 | -46.64 | -46.39 | -43.77 | -34.94 | 121.11 | -0.10 | 42,348 (4.23%) |
| geolocation_city | str | 0 (0.00%) | 8,011 | sao paulo (13.58%); rio de janeiro (6.21%); belo horizonte (2.78%) |  |  |  |  |  |  |  |  |  |
| geolocation_state | str | 0 (0.00%) | 27 | SP (40.42%); MG (12.63%); RJ (12.11%) |  |  |  |  |  |  |  |  |  |

### 1.2 Trùng lặp & số điểm trên mỗi zip

- 261,831 dòng trùng hoàn toàn (26.18%)
- 19,015 zip prefix; số dòng/zip: median 29, mean 52.6, max 1,146 (zip 24220); 1,043 zip chỉ có 1 dòng
- Sau khi bỏ dòng trùng: 738,332 dòng → vẫn phải gom về 1 dòng/zip trước khi nối với customers/sellers, nếu không sẽ nhân bản dòng

### 1.3 Kiểm tra tọa độ

- 42 dòng (21 zip) có tọa độ ngoài khung lãnh thổ Brazil (lat (-33.75, 5.27), lng (-73.99, -34.79))

| geolocation_zip_code_prefix | geolocation_lat | geolocation_lng | geolocation_city | geolocation_state |
|---|---|---|---|---|
| 18243 | 28.009 | -15.5369 | bom retiro da esperanca | SP |
| 28165 | 41.6141 | -8.4117 | vila nova de campos | RJ |
| 28155 | -34.5864 | -58.7321 | santa maria | RJ |
| 28155 | 42.4393 | 13.8202 | santa maria | RJ |
| 28333 | 38.3817 | -6.3282 | raposo | RJ |
| 28595 | 43.685 | -7.4111 | portela | RJ |
| 29654 | 29.4093 | -98.4841 | santo antônio do canaã | ES |
| 29654 | 21.6575 | -101.4668 | santo antonio do canaa | ES |
| 35179 | 25.9952 | -98.0785 | santana do paraíso | MG |
| 35179 | 25.9952 | -98.0785 | santana do paraiso | MG |

- Độ phân tán trong 1 zip (khoảng cách xa nhất tới điểm trung vị): median 1.49 km, P99 231.3 km, max 3,361 km
- 430 zip có điểm cách trung vị > 50 km (1155 dòng) → dùng trung vị (không dùng trung bình) khi gom để không bị điểm lệch kéo đi
- Zip lệch nhiều nhất: 68985 (3,361 km); 98780 (3,014 km); 29925 (2,783 km); 88868 (2,758 km); 35263 (2,689 km)

### 1.4 Kiểm tra bang (geolocation_state)

- 27 mã bang; mã không hợp lệ: không có
- 8 zip gắn với > 1 bang: 02116 (RN/SP), 04011 (AC/SP), 21550 (AC/RJ), 23056 (AC/RJ), 72915 (DF/GO), 78557 (MT/RO), 79750 (MS/RS), 80630 (PR/SC)
- 9 cặp (zip, bang) có bang khác với dải CEP của Correios (VD 01000–19999 là SP, 20000–28999 là RJ)

| geolocation_zip_code_prefix | geolocation_state | cep_state |
|---|---|---|
| 02116 | RN | SP |
| 04011 | AC | SP |
| 21550 | AC | RJ |
| 23056 | AC | RJ |
| 53012 | RN | PE |
| 72915 | DF | GO |
| 78557 | RO | MT |
| 79750 | RS | MS |
| 80630 | SC | PR |

### 1.5 Chất lượng geolocation_city

- 8,011 giá trị gốc → 5,966 sau khi bỏ dấu/chữ thường/khoảng trắng
- 73,442 dòng có chữ có dấu (VD 'são paulo') trong khi phần lớn ghi không dấu
- 31 dòng chứa ký tự lạ sau chuẩn hóa, VD: 'sa£o paulo'; 'jacaré (cabreúva)'; 'jacare (cabreuva)'; 'santa bárbara d`oeste'; 'são joão do pau d%26apos%3balho'; 'rio de janeiro, rio de janeiro, brasil'; 'california da barra (barra do pirai)'; 'penedo (itatiaia)'
- 548 zip có > 1 tên thành phố sau chuẩn hóa (zip prefix 5 số có thể trải qua nhiều đô thị nhỏ)
- VD biến thể của cùng 1 tên: abadiania: ['abadiania', 'abadiânia']; abaete: ['abaete', 'abaeté']; abaira: ['abaira', 'abaíra']; abare: ['abare', 'abaré']; abatia: ['abatia', 'abatiá']

### 1.6 Độ phủ cho customers & sellers

| Bảng | Số dòng | Số zip | Dòng không có trong geo | Zip không có trong geo | Tỷ lệ dòng |
|---|---|---|---|---|---|
| customers | 99,441 | 14,994 | 278 | 157 | 0.28% |
| sellers | 3,095 | 2,246 | 7 | 7 | 0.23% |

- 4,099/19,015 zip trong geolocation không được customers hay sellers dùng tới

### 1.7 Phân bố theo bang

| Bang (theo số zip) | Số dòng | Tỷ lệ |
|---|---|---|
| SP | 6349 | 33.39% |
| MG | 1868 | 9.82% |
| RJ | 1390 | 7.31% |
| RS | 1131 | 5.95% |
| PR | 1046 | 5.50% |
| BA | 992 | 5.22% |
| GO | 773 | 4.07% |
| SC | 619 | 3.26% |
| PE | 596 | 3.13% |
| CE | 548 | 2.88% |
| DF | 515 | 2.71% |
| PB | 324 | 1.70% |
| ES | 315 | 1.66% |
| MA | 313 | 1.65% |
| PA | 309 | 1.63% |
| PI | 307 | 1.61% |
| RN | 279 | 1.47% |
| MT | 254 | 1.34% |
| MS | 242 | 1.27% |
| TO | 184 | 0.97% |
| AL | 178 | 0.94% |
| AM | 144 | 0.76% |
| SE | 135 | 0.71% |
| RO | 107 | 0.56% |
| AC | 43 | 0.23% |
| RR | 28 | 0.15% |
| AP | 26 | 0.14% |

## Tổng hợp vấn đề & đề xuất xử lý

1. geolocation: 261,831 dòng trùng hoàn toàn; 1,000,163 dòng cho 19,015 zip (TB 52.6 dòng/zip) → bỏ trùng rồi gom 1 dòng/zip (trung vị lat/lng) ở stg_geolocation
2. geolocation: 42 dòng tọa độ ngoài Brazil → loại bỏ; 430 zip có điểm lệch > 50 km → gom bằng trung vị
3. geolocation: 8 zip gắn với > 1 bang, 9 cặp zip–bang trái dải CEP → lấy bang xuất hiện nhiều nhất của zip; có thể dùng dải CEP làm quy tắc kiểm tra (dbt test)
4. geolocation: geolocation_city 8,011 → 5,966 giá trị sau chuẩn hóa → bỏ dấu, chữ thường, gộp khoảng trắng, sửa 31 dòng lỗi mã hóa/ký tự lạ (VD 'sa£o paulo', '%26apos%3b', tên kèm bang); lấy tên xuất hiện nhiều nhất của mỗi zip
5. geolocation: 278 customer và 7 seller có zip không có tọa độ → LEFT JOIN, cho phép lat/lng NULL (không vẽ được trên bản đồ)
