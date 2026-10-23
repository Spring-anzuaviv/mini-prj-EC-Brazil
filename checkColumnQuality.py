from pathlib import Path
import sys
import unicodedata

import pandas as pd


# Khung tọa độ lãnh thổ Brazil, dùng để phát hiện tọa độ nằm ngoài nước.
BRAZIL_BOUNDS = {
    "geolocation_lat": (-33.75, 5.27),
    "geolocation_lng": (-73.99, -34.79),
}

# Số giá trị mẫu hiển thị cho cột chuỗi, và độ dài tối đa của mỗi giá trị mẫu.
SAMPLE_SIZE = 3
SAMPLE_MAX_LENGTH = 40

# Các cột quan trọng cần đưa vào Bảng 2.2, phân theo vai trò trong mô hình:
# key = khóa, seq = số thứ tự trong khóa ghép, time = cột thời gian,
# measure = cột số làm measure, category = cột phân loại làm thuộc tính dimension.
IMPORTANT_COLUMNS = {
    "olist_customers_dataset.csv": {
        "customer_id": "key",
        "customer_unique_id": "key",
        "customer_zip_code_prefix": "category",
        "customer_city": "category",
        "customer_state": "category",
    },
    "olist_orders_dataset.csv": {
        "order_id": "key",
        "customer_id": "key",
        "order_status": "category",
        "order_purchase_timestamp": "time",
        "order_approved_at": "time",
        "order_delivered_carrier_date": "time",
        "order_delivered_customer_date": "time",
        "order_estimated_delivery_date": "time",
    },
    "olist_order_items_dataset.csv": {
        "order_id": "key",
        "order_item_id": "seq",
        "product_id": "key",
        "seller_id": "key",
        "shipping_limit_date": "time",
        "price": "measure",
        "freight_value": "measure",
    },
    "olist_order_payments_dataset.csv": {
        "order_id": "key",
        "payment_sequential": "seq",
        "payment_type": "category",
        "payment_installments": "measure",
        "payment_value": "measure",
    },
    "olist_order_reviews_dataset.csv": {
        "review_id": "key",
        "order_id": "key",
        "review_score": "measure",
        "review_comment_title": "category",
        "review_comment_message": "category",
        "review_creation_date": "time",
        "review_answer_timestamp": "time",
    },
    "olist_products_dataset.csv": {
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
    "olist_sellers_dataset.csv": {
        "seller_id": "key",
        "seller_zip_code_prefix": "category",
        "seller_city": "category",
        "seller_state": "category",
    },
    "olist_geolocation_dataset.csv": {
        "geolocation_zip_code_prefix": "key",
        "geolocation_lat": "measure",
        "geolocation_lng": "measure",
        "geolocation_city": "category",
        "geolocation_state": "category",
    },
    "product_category_name_translation.csv": {
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


def is_identifier_column(column: str) -> bool:
    """Cột định danh (mã) luôn là chuỗi: *_id và mã bưu chính (giữ số 0 ở đầu)."""
    name = column.lower()
    return name.endswith("_id") or "zip_code_prefix" in name


def is_time_column(column: str) -> bool:
    """Giữ cùng quy tắc nhận diện cột thời gian với checkDataFile.py."""
    name = column.lower()
    return "date" in name or "timestamp" in name or name.endswith("_at")


def read_csv(file_path: Path) -> pd.DataFrame:
    """Đọc CSV, ép mọi cột định danh về chuỗi để không bị coi là số."""
    header = pd.read_csv(file_path, nrows=0).columns
    id_types = {column: str for column in header if is_identifier_column(column)}
    return pd.read_csv(file_path, low_memory=False, dtype=id_types)


def guess_role(df: pd.DataFrame, column: str) -> str:
    """Đoán vai trò cho cột không được khai báo trong IMPORTANT_COLUMNS."""
    if column.lower().endswith("_id"):
        return "key"
    if is_time_column(column):
        return "time"
    if pd.api.types.is_numeric_dtype(df[column]):
        return "measure"
    if df[column].nunique(dropna=True) <= 100:
        return "category"
    return "other"


def format_number(value: float) -> str:
    if pd.isna(value):
        return ""
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}"


def shorten(text: str) -> str:
    return text if len(text) <= SAMPLE_MAX_LENGTH else text[: SAMPLE_MAX_LENGTH - 3] + "..."


def normalize_text(value: str) -> str:
    without_accents = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        char for char in without_accents if not unicodedata.combining(char)
    )
    return " ".join(without_accents.lower().split())


# ---------------------------------------------------------------------------
# Mỗi kiểu dữ liệu một hàm thống kê riêng. Mỗi hàm trả về
# (dtype, stats, notes): stats là dict các cột thống kê, notes là danh sách nhận xét.
# ---------------------------------------------------------------------------


def profile_numeric(series: pd.Series) -> tuple[dict[str, str], list[str]]:
    """Cột số (int/float): có ý nghĩa để tính min, max, mode, trung bình, trung vị."""
    values = series.dropna()
    stats = {"Min": "", "Max": "", "Mode": "", "Trung bình": "", "Trung vị": "", "Độ lệch chuẩn": ""}
    notes: list[str] = []
    if values.empty:
        return stats, notes

    mode_value = values.mode().iloc[0]
    mode_share = (values == mode_value).mean() * 100
    stats = {
        "Min": format_number(values.min()),
        "Max": format_number(values.max()),
        "Mode": f"{format_number(mode_value)} ({mode_share:.1f}%)",
        "Trung bình": format_number(values.mean()),
        "Trung vị": format_number(values.median()),
        "Độ lệch chuẩn": format_number(values.std()),
    }

    # Tọa độ: giá trị âm là bình thường, chỉ cần kiểm tra có nằm trong Brazil không.
    if series.name in BRAZIL_BOUNDS:
        lower, upper = BRAZIL_BOUNDS[series.name]
        outside = int(((values < lower) | (values > upper)).sum())
        if outside:
            notes.append(f"{outside:,} tọa độ nằm ngoài lãnh thổ Brazil")
        return stats, notes

    # Cột ít giá trị (thang điểm, số thứ tự): phân bố có ý nghĩa hơn ngoại lai IQR.
    if values.nunique() <= 10:
        distribution = values.value_counts(normalize=True).sort_index()
        notes.append(
            "Phân bố: "
            + ", ".join(
                f"{format_number(value)}={share * 100:.1f}%"
                for value, share in distribution.items()
            )
        )
        return stats, notes

    negatives = int((values < 0).sum())
    zeros = int((values == 0).sum())
    if negatives:
        notes.append(f"{negatives:,} giá trị âm")
    if zeros:
        notes.append(f"{zeros:,} giá trị bằng 0")

    # Ngoại lai theo IQR: nằm ngoài [Q1 - 1.5*IQR, Q3 + 1.5*IQR].
    q1, q3 = values.quantile([0.25, 0.75])
    iqr = q3 - q1
    if iqr > 0:
        upper = q3 + 1.5 * iqr
        lower = q1 - 1.5 * iqr
        outliers = int(((values < lower) | (values > upper)).sum())
        if outliers:
            percent = outliers / len(values) * 100
            notes.append(
                f"{outliers:,} ngoại lai IQR ({percent:.2f}%), ngưỡng trên {format_number(upper)}"
            )
    return stats, notes


def profile_time(series: pd.Series) -> tuple[dict[str, str], list[str]]:
    """Cột thời gian: min/max cho biết phạm vi dữ liệu."""
    parsed = pd.to_datetime(series, errors="coerce")
    notes: list[str] = []

    # Giá trị có trong file nhưng không chuyển được sang ngày giờ.
    unparsable = int(series.notna().sum() - parsed.notna().sum())
    if unparsable:
        notes.append(f"{unparsable:,} giá trị sai định dạng ngày")
    notes.append("Đọc dạng chuỗi, cần ép kiểu datetime khi nạp")

    stats = {"Min": "", "Max": ""}
    if parsed.notna().any():
        stats = {
            "Min": f"{parsed.min():%Y-%m-%d %H:%M:%S}",
            "Max": f"{parsed.max():%Y-%m-%d %H:%M:%S}",
        }
    return stats, notes


def profile_string(
    series: pd.Series, column: str, role: str
) -> tuple[dict[str, str], list[str]]:
    """Cột chuỗi: không tính min/max/mode, chỉ lấy giá trị mẫu."""
    values = series.dropna().astype(str)
    notes: list[str] = []
    if values.empty:
        return {"Giá trị mẫu": ""}, notes

    if is_identifier_column(column) or role == "key":
        # Mã định danh: giá trị mẫu là vài mã bất kỳ, tần suất không có ý nghĩa.
        sample = "; ".join(shorten(value) for value in values.drop_duplicates().head(SAMPLE_SIZE))
    else:
        # Cột phân loại: giá trị mẫu là các giá trị xuất hiện nhiều nhất.
        top = values.value_counts().head(SAMPLE_SIZE)
        sample = "; ".join(
            f"{shorten(value)} ({count / len(values) * 100:.1f}%)"
            for value, count in top.items()
        )

    # Mã bưu chính phải lưu chuỗi 5 ký tự để không mất số 0 ở đầu.
    if "zip_code_prefix" in column.lower():
        with_leading_zero = int(values.str.startswith("0").sum())
        wrong_length = int((values.str.len() != 5).sum())
        notes.append(f"{with_leading_zero:,} mã bắt đầu bằng 0, phải lưu dạng chuỗi")
        if wrong_length:
            notes.append(f"{wrong_length:,} mã không đủ 5 ký tự")

    # Cùng giá trị nhưng khác hoa/thường, dấu tiếng Bồ Đào Nha hoặc khoảng trắng thừa,
    # ví dụ "são paulo" và "sao paulo".
    if not is_identifier_column(column):
        distinct = values.nunique()
        normalized = values.map(normalize_text).nunique()
        if normalized < distinct:
            notes.append(
                f"{distinct - normalized:,} giá trị chỉ khác hoa/thường, dấu hoặc khoảng trắng"
            )
    return {"Giá trị mẫu": sample}, notes


def profile_key(series: pd.Series, row_count: int) -> list[str]:
    distinct = series.nunique(dropna=True)
    if distinct == row_count and series.notna().all():
        return ["Duy nhất, không NULL"]
    if series.isna().any():
        return [f"Khóa có {int(series.isna().sum()):,} giá trị NULL"]
    duplicated = row_count - distinct
    return [
        f"Không duy nhất: {duplicated:,} dòng trùng giá trị "
        f"(TB {row_count / distinct:.2f} dòng/giá trị)"
    ]


def profile_column(
    df: pd.DataFrame, table: str, column: str, role: str
) -> dict[str, object]:
    series = df[column]
    row_count = len(series)
    null_count = int(series.isna().sum())
    notes: list[str] = []

    if role == "key":
        notes.extend(profile_key(series, row_count))
    if role == "seq":
        notes.append("Chỉ duy nhất khi ghép với order_id")
        # Số thứ tự là mã định danh (chuỗi) nên đổi tạm sang số để thống kê.
        sequence = pd.to_numeric(series, errors="coerce")
        notes.append(
            f"Số thứ tự lớn nhất {format_number(sequence.max())}; "
            f"{(sequence == 1).mean() * 100:.1f}% dòng có giá trị 1"
        )

    # Chọn cách thống kê theo kiểu dữ liệu: thời gian, số hay chuỗi.
    if is_time_column(column):
        dtype = "datetime (đọc dạng chuỗi)"
        stats, extra = profile_time(series)
    elif pd.api.types.is_numeric_dtype(series):
        dtype = str(series.dtype)
        stats, extra = profile_numeric(series)
    else:
        dtype = "string"
        stats, extra = profile_string(series, column, role)
    notes.extend(extra)

    if null_count:
        notes.insert(0, f"Thiếu {null_count:,} dòng")

    row: dict[str, object] = {
        "Bảng": table,
        "Cột": column,
        "Vai trò": ROLE_LABELS[role],
        "Kiểu dữ liệu": dtype,
        "% Null": round(null_count / row_count * 100, 2) if row_count else 0,
        "Số giá trị phân biệt": int(series.nunique(dropna=True)),
    }
    for name in ("Min", "Max", "Mode", "Trung bình", "Trung vị", "Độ lệch chuẩn", "Giá trị mẫu"):
        row[name] = stats.get(name, "")
    row["Nhận xét"] = "; ".join(notes)
    return row


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


def profile_csv(file_path: Path) -> list[dict[str, object]]:
    df = read_csv(file_path)
    declared = IMPORTANT_COLUMNS.get(file_path.name, {})
    rows: list[dict[str, object]] = []

    for column in df.columns:
        role = declared.get(column) or guess_role(df, column)
        row = profile_column(df, file_path.stem, column, role)
        row["Quan trọng"] = "Có" if column in declared else "Không"
        rows.append(row)

    return rows


def save_csv(df: pd.DataFrame, path: Path) -> Path:
    """Lưu CSV; nếu file đang mở trong Excel thì lưu sang tên mới thay vì báo lỗi."""
    try:
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return path
    except PermissionError:
        fallback = path.with_name(f"{path.stem}_moi{path.suffix}")
        df.to_csv(fallback, index=False, encoding="utf-8-sig")
        print(f"Cảnh báo: {path.name} đang được mở, đã lưu sang {fallback.name}")
        return fallback


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

    profile_data: list[dict[str, object]] = []
    errors: list[str] = []

    for file_path in csv_files:
        try:
            profile_data.extend(profile_csv(file_path))
            print(f"[OK] {file_path.name}")
        except Exception as error:
            message = f"[LOI] {file_path.name}: {error}"
            errors.append(message)
            print(message)

    if not profile_data:
        raise RuntimeError("Không đọc được file CSV nào.")

    full = pd.DataFrame(profile_data)

    # File đầy đủ: mọi cột của mọi bảng, mỗi thống kê một cột riêng (dùng cho phụ lục).
    full_path = save_csv(full, project_dir / "Bang_Chat_Luong_Cot_DayDu.csv")

    # File rút gọn: chỉ các cột quan trọng, đúng cấu trúc Bảng 2.2 trong báo cáo.
    report = full[full["Quan trọng"] == "Có"].copy()
    report["Min / Max hoặc giá trị mẫu"] = [
        describe_for_report(row) for row in report.to_dict("records")
    ]
    report_columns = [
        "Bảng",
        "Cột",
        "Kiểu dữ liệu",
        "% Null",
        "Số giá trị phân biệt",
        "Min / Max hoặc giá trị mẫu",
        "Nhận xét",
    ]
    output_path = save_csv(report[report_columns], project_dir / "Bang_Chat_Luong_Cot.csv")

    print("\nKET QUA CAC COT QUAN TRONG")
    print(report[report_columns].to_string(index=False, max_colwidth=70))
    print(f"\nĐã lưu bảng rút gọn tại: {output_path}")
    print(f"Đã lưu bảng đầy đủ tại: {full_path}")

    if errors:
        print(f"Cảnh báo: có {len(errors)} file bị lỗi.")


if __name__ == "__main__":
    main()
