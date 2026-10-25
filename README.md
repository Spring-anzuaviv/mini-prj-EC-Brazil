# mini-prj-EC-Brazil

Mini project BI trên bộ dữ liệu [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).

## Data profiling

```bash
pip install pandas numpy kagglehub
python download_data.py      # tải 9 file CSV vào rawData/
python run_profiling.py      # chạy toàn bộ profiling
```

Chỉ chạy một số bước: `python run_profiling.py issues reports` (các bước: `overview`, `column_quality`,
`relationships`, `issues`, `reports`).

| Thư mục / file | Nội dung |
|---|---|
| `profiling/common.py` | Đường dẫn, danh mục bảng, hằng số nghiệp vụ, đọc/ghi dữ liệu, helper dùng chung |
| `profiling/overview.py` | Bảng 2.1 – tổng quan các bảng |
| `profiling/column_quality.py` | Bảng 2.2 – chất lượng dữ liệu theo cột |
| `profiling/relationships.py` | Bảng 2.4 – quan hệ giữa các bảng |
| `profiling/issues.py` | Bảng 2.5 – các vấn đề dữ liệu và hướng xử lý |
| `profiling/reports/` | Báo cáo profiling chi tiết theo nhóm bảng |
| `output/` | Kết quả dạng CSV (`Bang_*.csv`) |
| `output/dataProfiling/` | Báo cáo chi tiết dạng Markdown |
