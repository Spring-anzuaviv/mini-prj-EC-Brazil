# MINI PROJECT: XÂY DỰNG HỆ THỐNG BUSINESS INTELLIGENCE TÍCH HỢP AI

## 1. Mục tiêu

Sinh viên thực hiện một mini project nhằm xây dựng hệ thống Business Intelligence (BI) hoàn chỉnh, từ tích hợp dữ liệu, xây dựng kho dữ liệu, phân tích và trực quan hóa đến ứng dụng Generative AI để hỗ trợ tạo và giải thích kết quả phân tích.

## 2. Lựa chọn dữ liệu và bài toán

Sinh viên được tự do lựa chọn một bộ dữ liệu (dataset) bất kỳ trên Kaggle để thực hiện project.

Dataset được lựa chọn cần đáp ứng các yêu cầu:

- Có ý nghĩa thực tiễn và phù hợp để xây dựng một ứng dụng BI.
- Có đủ dữ liệu và thuộc tính để thiết kế mô hình dữ liệu đa chiều (Dimensional Model).
- Cho phép thực hiện phân tích theo nhiều chiều, chẳng hạn thời gian, địa điểm, đối tượng, danh mục hoặc các thuộc tính phân loại khác.
- Có khả năng xây dựng các chỉ số phân tích (KPIs/Measures) và khám phá các xu hướng, biến động hoặc vấn đề có ý nghĩa.
- Có nguồn dữ liệu và mô tả rõ ràng; sinh viên phải cung cấp đường dẫn Kaggle.

Sinh viên cần tự xác định bối cảnh ứng dụng, mục tiêu phân tích, đối tượng sử dụng và các câu hỏi nghiệp vụ mà hệ thống BI sẽ giải quyết (du lịch, sale, khí hậu…)

Thông qua project, sinh viên cần vận dụng các công nghệ:

- **Mage.ai:** Xây dựng và điều phối quy trình thu thập, nạp dữ liệu (Data Ingestion).
- **dbt:** Chuyển đổi dữ liệu, kiểm tra chất lượng dữ liệu và xây dựng các mô hình dữ liệu.
- **SQL Server/postgres/DuckDB:** Xây dựng và quản lý Data Warehouse.
- **Power BI:** Xây dựng Semantic Model, các measures và dashboard phục vụ phân tích.
- **Generative AI:** Hỗ trợ tạo insight, tóm tắt và giải thích kết quả phân tích.

## 3. Yêu cầu thực hiện

### 3.1. Data Ingestion – Mage.ai

Sử dụng Mage.ai để xây dựng pipeline thu thập và nạp dữ liệu từ dataset đã chọn vào vùng Staging trên SQL Server.

Yêu cầu:

- Xây dựng pipeline đọc dữ liệu nguồn và nạp vào Staging.
- Thực hiện các bước kiểm tra cấu trúc và chất lượng dữ liệu cơ bản.
- Triển khai cơ chế nạp dữ liệu Full Load và Incremental Load (có thể mô phỏng các batch dữ liệu nếu dataset là dữ liệu tĩnh).
- Có cơ chế ghi nhận trạng thái thực thi, số lượng bản ghi được xử lý và lỗi phát sinh.
- Cho phép chạy lại pipeline và kiểm tra kết quả.

### 3.2. Data Transformation – dbt

Sử dụng dbt để xây dựng các mô hình chuyển đổi dữ liệu từ Staging sang Data Warehouse.

Yêu cầu:

- Xây dựng các mô hình dbt để làm sạch, chuẩn hóa và tích hợp dữ liệu.
- Thực hiện các phép biến đổi cần thiết để đáp ứng yêu cầu phân tích.
- Xây dựng các quy tắc kiểm tra chất lượng dữ liệu bằng dbt tests.
- Tổ chức các mô hình có quan hệ phụ thuộc rõ ràng.
- Tạo tài liệu mô tả các mô hình dữ liệu bằng dbt.

### 3.3. Data Warehouse – SQL Server

Thiết kế và triển khai Data Warehouse theo mô hình dữ liệu đa chiều.

Yêu cầu:

- Xác định các quy trình nghiệp vụ cần phân tích.
- Xác định grain của bảng Fact.
- Thiết kế các bảng Fact, Dimension và các measures phù hợp.
- Xây dựng lược đồ Star Schema hoặc Snowflake Schema.
- Triển khai Data Warehouse trên SQL Server.
- Nạp dữ liệu từ Staging vào các bảng của Data Warehouse thông qua các mô hình dbt.

### 3.4. Business Intelligence – Power BI

Sử dụng Power BI để xây dựng ứng dụng BI trên Data Warehouse.

#### A. Semantic Model

- Xây dựng các relationships giữa Fact và Dimension.
- Định nghĩa các measures bằng DAX.
- Xây dựng các hierarchies phù hợp để hỗ trợ phân tích đa chiều.

#### B. Dashboard

Xây dựng tối thiểu 02 trang dashboard:

**Dashboard 1 – Overview (Descriptive Analytics)**

- Trình bày các KPIs quan trọng.
- Phân tích xu hướng và phân bố dữ liệu.
- Hỗ trợ lọc và phân tích theo nhiều chiều.
- Giúp người dùng nhận diện những biến động hoặc vấn đề đáng chú ý.

**Dashboard 2 – Detailed/Diagnostic Analytics**

- Cho phép đi sâu phân tích từ các kết quả trên dashboard tổng quan.
- Sử dụng các chức năng như drill-down, drill-through, filtering hoặc các biểu đồ phân tích phù hợp.
- Phân tích những yếu tố đóng góp vào các biến động hoặc vấn đề đã phát hiện.
- Cung cấp bằng chứng định lượng để hỗ trợ giải thích kết quả.

### 3.5. Generative AI – AI-Assisted Analytics

Tích hợp Generative AI để hỗ trợ người dùng khai thác và diễn giải kết quả phân tích.

Yêu cầu tối thiểu:

- Sử dụng một mô hình ngôn ngữ lớn (LLM) hoặc dịch vụ Generative AI phù hợp.
- Xây dựng chức năng tự động tạo bản tóm tắt (AI-generated Summary) từ các KPIs và kết quả phân tích.
- Xây dựng chức năng giải thích các xu hướng, biến động hoặc vấn đề được phát hiện trên dashboard.
- Kết quả do AI tạo ra phải dựa trên dữ liệu hoặc các chỉ số đã được tính toán, có khả năng kiểm chứng và hạn chế suy diễn không có căn cứ.

Sinh viên được tự lựa chọn cách tích hợp AI, chẳng hạn thông qua API, ứng dụng Python hoặc các công cụ AI được hỗ trợ trong nền tảng BI.

**Khuyến khích:** Cho phép người dùng đặt câu hỏi bằng ngôn ngữ tự nhiên để truy vấn hoặc giải thích kết quả phân tích.

## 4. Sản phẩm cần nộp

1. **Báo cáo project (PDF):** Mô tả dataset, bài toán, yêu cầu phân tích, kiến trúc hệ thống, thiết kế Data Warehouse, các pipeline và kết quả thực hiện.
2. **Source code:** Mã nguồn Mage.ai, dbt, SQL scripts và thành phần tích hợp AI.
3. **Power BI (.pbix):** Semantic Model và các dashboard đã xây dựng.
4. **Dữ liệu và tài liệu triển khai:** Đường dẫn Kaggle, hướng dẫn cấu hình và chạy hệ thống.
5. **Video demo:** Minh họa quy trình từ nạp dữ liệu, chuyển đổi, cập nhật Data Warehouse đến phân tích trên Power BI và tạo giải thích bằng AI.
