from itertools import combinations
from pathlib import Path
import sys

import pandas as pd


# Khóa nghiệp vụ dự kiến của bộ dữ liệu Olist.
# Việc khai báo trước giúp tránh chọn nhầm một cột chỉ tình cờ duy nhất.
EXPECTED_KEYS = {
    "olist_customers_dataset.csv": ["customer_id"],
    "olist_orders_dataset.csv": ["order_id"],
    "olist_order_items_dataset.csv": ["order_id", "order_item_id"],
    "olist_order_payments_dataset.csv": ["order_id", "payment_sequential"],
    "olist_order_reviews_dataset.csv": ["review_id"],
    "olist_products_dataset.csv": ["product_id"],
    "olist_sellers_dataset.csv": ["seller_id"],
    "olist_geolocation_dataset.csv": ["geolocation_zip_code_prefix"],
    "product_category_name_translation.csv": ["product_category_name"],
}


def is_unique_key(df: pd.DataFrame, columns: list[str]) -> bool:
    """Khóa hợp lệ khi đủ cột, không NULL và không có bản ghi trùng."""
    if df.empty or not columns or not set(columns).issubset(df.columns):
        return False

    return not df[columns].isna().any().any() and not df.duplicated(
        subset=columns
    ).any()


def infer_key(df: pd.DataFrame) -> list[str]:
    """Dự đoán khóa cho file lạ, ưu tiên các cột có hậu tố _id."""
    id_columns = [column for column in df.columns if column.lower().endswith("_id")]

    for column in id_columns:
        if is_unique_key(df, [column]):
            return [column]

    # Chỉ thử tổ hợp cột ID, không ghép tùy tiện các cột đầu tiên.
    for size in (2, 3):
        for candidate in combinations(id_columns, size):
            if is_unique_key(df, list(candidate)):
                return list(candidate)

    # File danh mục có thể dùng một cột tên làm khóa thay vì cột ID.
    for column in df.columns:
        if is_unique_key(df, [column]):
            return [column]

    return []


def is_time_column(column: str) -> bool:
    """Nhận diện cột thời gian mà không nhầm 'state/category/latitude'."""
    name = column.lower()
    return "date" in name or "timestamp" in name or name.endswith("_at")


def get_time_range(df: pd.DataFrame) -> str:
    date_columns = [column for column in df.columns if is_time_column(column)]
    parsed_columns: list[str] = []
    minimum_dates: list[pd.Timestamp] = []
    maximum_dates: list[pd.Timestamp] = []

    for column in date_columns:
        parsed = pd.to_datetime(df[column], errors="coerce")
        if parsed.notna().any():
            parsed_columns.append(column)
            minimum_dates.append(parsed.min())
            maximum_dates.append(parsed.max())

    if not parsed_columns:
        return "Không có dữ liệu thời gian"

    minimum = min(minimum_dates).strftime("%Y-%m-%d %H:%M:%S")
    maximum = max(maximum_dates).strftime("%Y-%m-%d %H:%M:%S")
    return f"{minimum} -> {maximum} ({', '.join(parsed_columns)})"


def profile_csv(file_path: Path) -> dict[str, object]:
    df = pd.read_csv(file_path, low_memory=False)
    expected_key = EXPECTED_KEYS.get(file_path.name, infer_key(df))
    key_exists = bool(expected_key) and set(expected_key).issubset(df.columns)

    return {
        "Bảng": file_path.stem,
        "Số dòng": len(df),
        "Số cột": len(df.columns),
        "Khóa dự kiến": " + ".join(expected_key) if key_exists else "Không tìm thấy",
        "Khóa duy nhất?": "Có" if is_unique_key(df, expected_key) else "Không",
        "Phạm vi thời gian": get_time_range(df),
    }


def main() -> None:
    # Tránh UnicodeEncodeError khi Windows Terminal đang dùng bảng mã cp1252.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # Dùng đường dẫn tương đối với chính file này, không phụ thuộc thư mục chạy lệnh.
    project_dir = Path(__file__).resolve().parent
    data_dir = project_dir / "data"

    if not data_dir.is_dir():
        raise FileNotFoundError(f"Không tìm thấy thư mục dữ liệu: {data_dir}")

    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"Không tìm thấy file CSV nào trong: {data_dir}")

    summary_data: list[dict[str, object]] = []
    errors: list[str] = []

    for file_path in csv_files:
        try:
            summary_data.append(profile_csv(file_path))
            print(f"[OK] {file_path.name}")
        except Exception as error:
            message = f"[LOI] {file_path.name}: {error}"
            errors.append(message)
            print(message)

    if not summary_data:
        raise RuntimeError("Không đọc được file CSV nào.")

    summary = pd.DataFrame(summary_data)
    output_path = project_dir / "Bang_Tong_Quan_Du_Lieu.csv"
    summary.to_csv(output_path, index=False, encoding="utf-8-sig")

    print("\nKET QUA TONG HOP")
    print(summary.to_string(index=False))
    print(f"\nĐã lưu báo cáo tại: {output_path}")

    if errors:
        print(f"Cảnh báo: có {len(errors)} file bị lỗi.")


if __name__ == "__main__":
    main()
