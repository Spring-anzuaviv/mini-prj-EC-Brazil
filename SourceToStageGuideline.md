# Olist Mini Project — SSIS Staging

Nạp 9 CSV Olist vào SQL Server bằng SSIS. Năm bảng được full load; orders, order items, payments và reviews được nạp theo từng tháng mua hàng.

## Cấu trúc repo

| Đường dẫn | Nội dung |
|---|---|
| `rawData/` | 9 CSV nguồn |
| `sqlScript/Olist_Staging_Script.sql` | Tạo database staging và 9 bảng rỗng |
| `sqlScript/Olist_Metadata.sql` | Tạo database metadata, bảng và mốc ban đầu |
| `ssis/Integration Services Project1/Integration Services Project1.slnx` | Solution SSIS |
| `ssis/Integration Services Project1/Integration Services Project1/` | Project.params, project và 5 package nguồn |

## Môi trường

- Windows, SQL Server 2022 và SSMS.
- Visual Studio hỗ trợ mở solution `.slnx`, cùng extension SQL Server Integration Services Projects tương thích.
- OLE DB provider trùng với provider được chọn trong Connection Manager. Kiểm tra provider trong cửa sổ sửa kết nối; phiên bản cụ thể chưa được ghi nhận trong tài liệu này.
- Tài khoản chạy script có quyền tạo database; tài khoản chạy SSIS có quyền đọc/ghi các database liên quan. Nếu dùng Windows Authentication, dùng tài khoản Windows của máy người chạy.

## Setup lần đầu

1. Clone hoặc pull repo, bảo đảm `rawData` có đủ 9 CSV.
2. Trong SSMS, kết nối SQL Server cục bộ của bạn.
3. Mở và Execute toàn bộ `sqlScript/Olist_Staging_Script.sql`.
4. Mở và Execute toàn bộ `sqlScript/Olist_Metadata.sql`.

Hai script dành cho lần setup đầu. Chạy lại toàn bộ khi bảng đã tồn tại sẽ báo lỗi tạo đối tượng. Không cần chạy setup lại sau mỗi lần pull. Script không phải công cụ reset hay cập nhật cấu trúc database hiện có.

Script metadata khởi tạo bốn tên luồng: `orders`, `order_items`, `order_payments`, `order_reviews`; LSET = `2016-09-01`, CET = `2016-10-01`. Tên luồng phải khớp SQL trong package. Lịch sử `etl_batch` ban đầu rỗng.

## Cấu hình trên từng máy

Mở solution trong Visual Studio rồi mở `Project.params`:

| Parameter | Giá trị trên máy người chạy |
|---|---|
| `RawDataFolder` | Đường dẫn tuyệt đối tới thư mục `rawData`, không thêm tên CSV và không thêm dấu `\` cuối |
| `SqlServerName` | Tên server/instance dùng để đăng nhập SSMS |

Ví dụ: `RawDataFolder = C:\Projects\mini-project\rawData`; `SqlServerName = TENMAY\SQLEXPRESS`.

Connection FF lấy ConnectionString từ expression ghép RawDataFolder với tên CSV. Connection OLE DB lấy ServerName từ `@[$Project::SqlServerName]`; database vẫn là `Olist_Staging` hoặc `Olist_Metadata`.

Lưu cấu hình, Preview từng CSV và Test Connection các kết nối SQL trước khi chạy package. Không dùng Execute Package chỉ để kiểm tra kết nối vì package có thể thay đổi dữ liệu và watermark. Các giá trị mặc định trong Project.params là cấu hình mẫu; khi commit, kiểm tra để không vô tình ghi đè cấu hình máy người khác.

## Thứ tự chạy

Chuột phải đúng package trong SSIS Packages rồi chọn Execute Package. Kết thúc chế độ debug trước lần chạy tiếp theo.

| Thứ tự | Package | Cách chạy |
|---|---|---|
| 1 | `FullLoad.dtsx` | Chạy một lần, nạp customers, geolocation, products, sellers, category translation |
| 2 | `IncrementalLoadOrders.dtsx` | Chạy đủ các tháng trước khi chạy ba package dưới |
| 3 | `IncrementalLoadOrderItem.dtsx` | Chạy đủ các tháng |
| 4 | `IncrementalLoadOrderPayments.dtsx` | Chạy đủ các tháng |
| 5 | `IncrementalLoadOrderReviews.dtsx` | Chạy đủ các tháng |

Mỗi lần chạy package incremental xử lý một tháng: `LSET <= ngày mua < CET`. Items, payments và reviews Lookup ngày mua từ `stg_orders`, nên orders phải được nạp đầy đủ trước.

Từ mốc ban đầu, mỗi luồng cần 26 lần chạy thành công để xử lý từ tháng 09/2016 đến hết tháng 10/2018. Dừng khi LSET = CET = `2018-11-01`. Tháng không có dòng vẫn có thể hoàn tất và tăng mốc. Theo dõi ngày, không dựa vào batch_id vì mã được dùng chung và có thể nhảy số.

FullLoad hiện có bước truncate/nạp lại: chạy lại sẽ thay dữ liệu ở các bảng full load.

## Kiểm tra tiến độ

```sql
SELECT name, LSET, CET
FROM Olist_Metadata.dbo.data_flow
ORDER BY name;

SELECT batch_id, flow_name, LSET, CET, started_at
FROM Olist_Metadata.dbo.etl_batch
ORDER BY batch_id;
```

Đối chiếu số dòng staging với CSV/profiling và kiểm tra metadata sau khi nạp. Chỉ có đủ tổng số dòng chưa chứng minh dữ liệu hoàn toàn chính xác.

## Khi package lỗi

Dừng và xem lỗi trong Progress/Output trước khi chạy lại. Package có thể đã ghi một phần dữ liệu nhưng chưa tăng LSET; chạy lại ngay có thể nạp trùng. Cơ chế hiện tại chưa bảo đảm chạy lại an toàn sau lỗi giữa chừng. Không tự xóa database hoặc đổi watermark để bỏ qua lỗi.

## Làm việc nhóm và Git

- Mỗi thành viên dùng database cục bộ riêng. Pull repo không mang theo dữ liệu SQL Server hay tiến độ batch của thành viên khác.
- Commit package nguồn `.dtsx`, `.dtproj`, solution, `Project.params`, SQL, README và dữ liệu nguồn theo quy ước nhóm.
- Bỏ qua `.vs/`, `*.dtproj.user`, `*.suo`, `**/bin/`, `**/obj/`. File build tự sinh lại từ project.
- Nếu dùng chung một database, không chạy đồng thời cùng luồng với thiết kế hiện tại.
- Không có script reset trong bộ setup này. Muốn demo lại từ đầu cần chuẩn bị quy trình reset riêng cho database của người chạy.

## Trạng thái kiểm chứng

Cấu hình và script đã được rà soát theo nội dung chia sẻ. Chưa xác nhận setup và chạy toàn bộ trên một máy thứ hai. Trước khi coi việc bàn giao hoàn tất, cần thử setup, Preview/Test Connection và chạy các package trên máy thành viên khác; ghi lại phiên bản Visual Studio, extension và OLE DB provider thực tế đã chạy thành công.
