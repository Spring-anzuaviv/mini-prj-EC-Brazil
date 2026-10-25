"""Bảng 2.2 — Chất lượng dữ liệu theo cột.

Kết quả:
- output/Bang_Chat_Luong_Cot_DayDu.csv: mọi cột của mọi bảng, mỗi thống kê một cột (phụ lục).
- output/Bang_Chat_Luong_Cot.csv: chỉ các cột quan trọng, đúng cấu trúc Bảng 2.2 trong báo cáo.
"""
import pandas as pd

from profiling.common import (
    BRAZIL_LAT,
    BRAZIL_LNG,
    TABLE_FILES,
    fmt,
    iqr_bounds,
    is_identifier_column,
    is_time_column,
    normalize_text,
    read_table,
    save_csv,
    setup_console,
)


SAMPLE_SIZE = 3
SAMPLE_MAX_LENGTH = 40
COORDINATE_BOUNDS = {"geolocation_lat": BRAZIL_LAT, "geolocation_lng": BRAZIL_LNG}

# Các cột quan trọng cần đưa vào Bảng 2.2, phân theo vai trò trong mô hình:
# key = khóa, seq = số thứ tự trong khóa ghép, time = cột thời gian,
# measure = cột số làm measure, category = cột phân loại làm thuộc tính dimension.
IMPORTANT_COLUMNS = {
    "customers": {
        "customer_id": "key",
        "customer_unique_id": "key",
        "customer_zip_code_prefix": "category",
        "customer_city": "category",
        "customer_state": "category",
    },
    "orders": {
        "order_id": "key",
        "customer_id": "key",
        "order_status": "category",
        "order_purchase_timestamp": "time",
        "order_approved_at": "time",
        "order_delivered_carrier_date": "time",
        "order_delivered_customer_date": "time",
        "order_estimated_delivery_date": "time",
    },
    "order_items": {
        "order_id": "key",
        "order_item_id": "seq",
        "product_id": "key",
        "seller_id": "key",
        "shipping_limit_date": "time",
        "price": "measure",
        "freight_value": "measure",
    },
    "order_payments": {
        "order_id": "key",
        "payment_sequential": "seq",
        "payment_type": "category",
        "payment_installments": "measure",
        "payment_value": "measure",
    },
    "order_reviews": {
        "review_id": "key",
        "order_id": "key",
        "review_score": "measure",
        "review_comment_title": "category",
        "review_comment_message": "category",
        "review_creation_date": "time",
        "review_answer_timestamp": "time",
    },
    "products": {
        "product_id": "key",
        "product_category_name": "category",
        "product_name_lenght": "measure",
        "product_description_lenght": "measure",
        "product_photos_qty": "measure",
        "product_weight_g": "measure",
        "product_length_cm": "measure",
        "product_height_cm": "measure",
        "product_width_cm": "measure",
    },
    "sellers": {
        "seller_id": "key",
        "seller_zip_code_prefix": "category",
        "seller_city": "category",
        "seller_state": "category",
    },
    "geolocation": {
        "geolocation_zip_code_prefix": "key",
        "geolocation_lat": "measure",
        "geolocation_lng": "measure",
        "geolocation_city": "category",
        "geolocation_state": "category",
    },
    "category_translation": {
        "product_category_name": "key",
        "product_category_name_english": "category",
    },
}

ROLE_LABELS = {
    "key": "Khóa",
    "seq": "Số thứ tự (khóa ghép)",
    "time": "Thời gian",
    "measure": "Số (measure)",
    "category": "Phân loại",
    "other": "Khác",
}
STAT_COLUMNS = ["Min", "Max", "Mode", "Trung bình", "Trung vị", "Độ lệch chuẩn", "Giá trị mẫu"]


def guess_role(series: pd.Series) -> str:
    """Đoán vai trò cho cột không được khai báo trong IMPORTANT_COLUMNS."""
    if is_identifier_column(series.name):
        return "key"
    if is_time_column(series.name):
        return "time"
    if pd.api.types.is_numeric_dtype(series):
        return "measure"
    return "category" if series.nunique() <= 100 else "other"


def shorten(text: str) -> str:
    return text if len(text) <= SAMPLE_MAX_LENGTH else text[: SAMPLE_MAX_LENGTH - 3] + "..."


# Mỗi kiểu dữ liệu một hàm thống kê, trả về (stats, notes).
def profile_numeric(series: pd.Series) -> tuple[dict[str, str], list[str]]:
    values = series.dropna()
    if values.empty:
        return {}, []
    mode = values.mode().iloc[0]
    stats = {
        "Min": fmt(values.min()),
        "Max": fmt(values.max()),
        "Mode": f"{fmt(mode)} ({(values == mode).mean() * 100:.1f}%)",
        "Trung bình": fmt(round(values.mean(), 2)),
        "Trung vị": fmt(values.median()),
        "Độ lệch chuẩn": fmt(round(values.std(), 2)),
    }

    # Tọa độ: giá trị âm là bình thường, chỉ cần kiểm tra có nằm trong Brazil không.
    if series.name in COORDINATE_BOUNDS:
        outside = int((~values.between(*COORDINATE_BOUNDS[series.name])).sum())
        return stats, [f"{outside:,} tọa độ nằm ngoài lãnh thổ Brazil"] if outside else []

    # Cột ít giá trị (thang điểm, số thứ tự): phân bố có ý nghĩa hơn ngoại lai IQR.
    if values.nunique() <= 10:
        distribution = values.value_counts(normalize=True).sort_index()
        return stats, ["Phân bố: " + ", ".join(f"{fmt(v)}={share * 100:.1f}%" for v, share in distribution.items())]

    notes = []
    if (negatives := int((values < 0).sum())):
        notes.append(f"{negatives:,} giá trị âm")
    if (zeros := int((values == 0).sum())):
        notes.append(f"{zeros:,} giá trị bằng 0")
    low, high = iqr_bounds(values)
    if high > low and (outliers := int(((values < low) | (values > high)).sum())):
        notes.append(f"{outliers:,} ngoại lai IQR ({outliers / len(values) * 100:.2f}%), ngưỡng trên {fmt(high)}")
    return stats, notes


def profile_time(series: pd.Series, parse_errors: int) -> tuple[dict[str, str], list[str]]:
    notes = [f"{parse_errors:,} giá trị sai định dạng ngày"] if parse_errors else []
    notes.append("Đọc dạng chuỗi, cần ép kiểu datetime khi nạp")
    if series.notna().any():
        return {"Min": f"{series.min():%Y-%m-%d %H:%M:%S}", "Max": f"{series.max():%Y-%m-%d %H:%M:%S}"}, notes
    return {}, notes


def profile_string(series: pd.Series, role: str) -> tuple[dict[str, str], list[str]]:
    values = series.dropna().astype(str)
    if values.empty:
        return {}, []
    column = series.name
    if is_identifier_column(column) or role == "key":
        # Mã định danh: giá trị mẫu là vài mã bất kỳ, tần suất không có ý nghĩa.
        sample = "; ".join(shorten(v) for v in values.drop_duplicates().head(SAMPLE_SIZE))
    else:
        top = values.value_counts().head(SAMPLE_SIZE)
        sample = "; ".join(f"{shorten(v)} ({count / len(values) * 100:.1f}%)" for v, count in top.items())

    notes = []
    if "zip_code_prefix" in column:
        notes.append(f"{int(values.str.startswith('0').sum()):,} mã bắt đầu bằng 0, phải lưu dạng chuỗi")
        if (wrong_length := int((values.str.len() != 5).sum())):
            notes.append(f"{wrong_length:,} mã không đủ 5 ký tự")
    elif not is_identifier_column(column):
        # Cùng giá trị nhưng khác hoa/thường, dấu hoặc khoảng trắng, VD "são paulo" và "sao paulo".
        variants = values.nunique() - values.map(normalize_text).nunique()
        if variants:
            notes.append(f"{variants:,} giá trị chỉ khác hoa/thường, dấu hoặc khoảng trắng")
    return {"Giá trị mẫu": sample}, notes


def profile_key(series: pd.Series) -> str:
    if series.isna().any():
        return f"Khóa có {int(series.isna().sum()):,} giá trị NULL"
    distinct = series.nunique()
    if distinct == len(series):
        return "Duy nhất, không NULL"
    return (
        f"Không duy nhất: {len(series) - distinct:,} dòng trùng giá trị "
        f"(TB {len(series) / distinct:.2f} dòng/giá trị)"
    )


def profile_column(df: pd.DataFrame, table: str, column: str, role: str) -> dict[str, object]:
    series = df[column]
    notes = []
    if role == "key":
        notes.append(profile_key(series))
    if role == "seq":
        notes.append("Chỉ duy nhất khi ghép với order_id")

    if is_time_column(column):
        dtype = "datetime (đọc dạng chuỗi)"
        stats, extra = profile_time(series, df.attrs["parse_errors"][column])
    elif pd.api.types.is_numeric_dtype(series):
        dtype = str(series.dtype)
        stats, extra = profile_numeric(series)
    else:
        dtype = "string"
        stats, extra = profile_string(series, role)
    notes.extend(extra)

    null_count = int(series.isna().sum())
    if null_count:
        notes.insert(0, f"Thiếu {null_count:,} dòng")
    return {
        "Bảng": TABLE_FILES[table].removesuffix(".csv"),
        "Cột": column,
        "Vai trò": ROLE_LABELS[role],
        "Kiểu dữ liệu": dtype,
        "% Null": round(null_count / len(series) * 100, 2) if len(series) else 0,
        "Số giá trị phân biệt": int(series.nunique()),
        **{name: stats.get(name, "") for name in STAT_COLUMNS},
        "Nhận xét": "; ".join(notes),
    }


def describe_for_report(row: dict[str, object]) -> str:
    """Gộp thống kê vào cột 'Min / Max hoặc giá trị mẫu' của Bảng 2.2."""
    if row["Giá trị mẫu"]:
        return f"VD: {row['Giá trị mẫu']}"
    if row["Min"] == "" and row["Max"] == "":
        return ""
    text = f"Min = {row['Min']}; Max = {row['Max']}"
    if row["Mode"]:
        text += f"; Mode = {row['Mode']}"
    if row["Trung bình"]:
        text += f"; TB = {row['Trung bình']}"
    return text


def build() -> pd.DataFrame:
    rows = []
    for table in TABLE_FILES:
        df = read_table(table)
        declared = IMPORTANT_COLUMNS.get(table, {})
        for column in df.columns:
            row = profile_column(df, table, column, declared.get(column) or guess_role(df[column]))
            row["Quan trọng"] = "Có" if column in declared else "Không"
            rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    setup_console()
    full = build()
    save_csv(full, "Bang_Chat_Luong_Cot_DayDu.csv")

    report = full[full["Quan trọng"] == "Có"].copy()
    report["Min / Max hoặc giá trị mẫu"] = [describe_for_report(row) for row in report.to_dict("records")]
    columns = ["Bảng", "Cột", "Kiểu dữ liệu", "% Null", "Số giá trị phân biệt", "Min / Max hoặc giá trị mẫu", "Nhận xét"]
    save_csv(report[columns], "Bang_Chat_Luong_Cot.csv")


if __name__ == "__main__":
    main()
