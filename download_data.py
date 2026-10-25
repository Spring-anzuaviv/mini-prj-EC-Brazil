from pathlib import Path

import kagglehub

# Luôn tải vào thư mục "rawData" nằm cạnh file download_data.py.
# Cách này vẫn đúng kể cả khi chạy script từ một thư mục khác.
data_dir = Path(__file__).resolve().parent / "rawData"

path = kagglehub.dataset_download(
    "olistbr/brazilian-ecommerce",
    output_dir=str(data_dir),
)

print("Path to dataset files:", path)
