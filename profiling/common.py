"""Đường dẫn, danh mục bảng, hằng số nghiệp vụ và các hàm dùng chung."""
from functools import cache
from pathlib import Path
import sys
import unicodedata

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "rawData"
OUTPUT_DIR = BASE_DIR / "output"
REPORT_DIR = OUTPUT_DIR / "dataProfiling"

# Tên ngắn của bảng (dùng trong code và báo cáo) -> file nguồn.
TABLE_FILES = {
    "customers": "olist_customers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

# Khóa nghiệp vụ dự kiến của từng bảng.
EXPECTED_KEYS = {
    "customers": ["customer_id"],
    "geolocation": ["geolocation_zip_code_prefix"],
    "order_items": ["order_id", "order_item_id"],
    "order_payments": ["order_id", "payment_sequential"],
    "order_reviews": ["review_id"],
    "orders": ["order_id"],
    "products": ["product_id"],
    "sellers": ["seller_id"],
    "category_translation": ["product_category_name"],
}

ORDER_TIME_COLUMNS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]

# Cột tên *_id nhưng là số thứ tự trong khóa ghép, không phải mã định danh.
SEQUENCE_COLUMNS = {"order_item_id"}

ID_PATTERN = r"[0-9a-f]{32}"

# Khung tọa độ lãnh thổ Brazil, dùng để phát hiện tọa độ nằm ngoài nước.
BRAZIL_LAT = (-33.75, 5.27)
BRAZIL_LNG = (-73.99, -34.79)

# Dải mã bưu chính (5 số đầu CEP) của từng bang, theo quy định của Correios.
CEP_RANGES = {
    "SP": [(1000, 19999)],
    "RJ": [(20000, 28999)],
    "ES": [(29000, 29999)],
    "MG": [(30000, 39999)],
    "BA": [(40000, 48999)],
    "SE": [(49000, 49999)],
    "PE": [(50000, 56999)],
    "AL": [(57000, 57999)],
    "PB": [(58000, 58999)],
    "RN": [(59000, 59999)],
    "CE": [(60000, 63999)],
    "PI": [(64000, 64999)],
    "MA": [(65000, 65999)],
    "PA": [(66000, 68899)],
    "AP": [(68900, 68999)],
    "AM": [(69000, 69299), (69400, 69899)],
    "RR": [(69300, 69399)],
    "AC": [(69900, 69999)],
    "DF": [(70000, 72799), (73000, 73699)],
    "GO": [(72800, 72999), (73700, 76799)],
    "RO": [(76800, 76999)],
    "TO": [(77000, 77999)],
    "MT": [(78000, 78899)],
    "MS": [(79000, 79999)],
    "PR": [(80000, 87999)],
    "SC": [(88000, 89999)],
    "RS": [(90000, 99999)],
}
BRAZIL_STATES = set(CEP_RANGES)

# Kích thước 16 x 2 x 11 cm là kích thước tối thiểu của Correios,
# thường được người bán nhập làm giá trị mặc định thay cho kích thước thật.
DEFAULT_DIMENSIONS = (16, 2, 11)

# Điểm trong cùng zip cách điểm trung vị quá ngưỡng này (km) thì coi là tọa độ lệch.
FAR_POINT_KM = 50

# Trạng thái đơn không tạo ra doanh thu thực.
NON_REVENUE_STATUSES = ["canceled", "unavailable"]


# ---------------------------------------------------------------------------
# Đọc / ghi dữ liệu
# ---------------------------------------------------------------------------
def is_identifier_column(column: str) -> bool:
    """Cột mã luôn là chuỗi: *_id (trừ số thứ tự) và mã bưu chính (giữ số 0 ở đầu)."""
    return (column.endswith("_id") and column not in SEQUENCE_COLUMNS) or "zip_code_prefix" in column


def is_time_column(column: str) -> bool:
    return column.endswith(("_date", "_timestamp", "_at"))


@cache
def _load(table: str) -> pd.DataFrame:
    path = DATA_DIR / TABLE_FILES[table]
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file: {path} (chạy download_data.py để tải dữ liệu)")
    header = pd.read_csv(path, nrows=0, encoding="utf-8-sig").columns
    as_text = {c: str for c in header if is_identifier_column(c) or is_time_column(c)}
    # File dịch danh mục có BOM UTF-8 → đọc bằng utf-8-sig để tên cột không dính BOM.
    df = pd.read_csv(path, dtype=as_text, encoding="utf-8-sig", low_memory=False)

    # Số giá trị có dữ liệu nhưng không parse được ngày (lỗi định dạng, khác với NULL).
    parse_errors = {}
    for column in filter(is_time_column, df.columns):
        parsed = pd.to_datetime(df[column], format="%Y-%m-%d %H:%M:%S", errors="coerce")
        parse_errors[column] = int((df[column].notna() & parsed.isna()).sum())
        df[column] = parsed
    df.attrs["parse_errors"] = parse_errors
    return df


def read_table(table: str) -> pd.DataFrame:
    """Đọc 1 bảng nguồn theo tên ngắn; mỗi file chỉ đọc 1 lần, trả về bản sao để sửa thoải mái."""
    return _load(table).copy()


def load_tables(*tables: str) -> dict[str, pd.DataFrame]:
    return {table: read_table(table) for table in (tables or TABLE_FILES)}


def save_csv(df: pd.DataFrame, file_name: str) -> Path:
    """Lưu CSV vào output/ (utf-8-sig để Excel hiển thị đúng tiếng Việt).

    Nếu file đang mở trong Excel thì lưu sang tên *_moi thay vì báo lỗi.
    """
    path = OUTPUT_DIR / file_name
    path.parent.mkdir(exist_ok=True)
    try:
        df.to_csv(path, index=False, encoding="utf-8-sig")
    except PermissionError:
        path = path.with_name(f"{path.stem}_moi{path.suffix}")
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"Cảnh báo: {file_name} đang được mở, đã lưu sang {path.name}")
    print(f"Đã lưu: {path}")
    return path


def setup_console() -> None:
    """Tránh UnicodeEncodeError khi Windows Terminal đang dùng bảng mã cp1252."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Hàm tính toán
# ---------------------------------------------------------------------------
def normalize_text(value: str) -> str:
    """Bỏ dấu, chữ thường, gộp khoảng trắng."""
    without_accents = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in without_accents if not unicodedata.combining(char))
    return " ".join(without_accents.lower().split())


def pct(part: int, total: int) -> str:
    return f"{part / total * 100:.2f}%" if total else "0%"


def fmt(value) -> str:
    """Số nguyên không có phần lẻ, số thực giữ 2 chữ số."""
    if pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return str(value)
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}"


def iqr_bounds(series: pd.Series) -> tuple[float, float]:
    q1, q3 = series.quantile([0.25, 0.75])
    iqr = q3 - q1
    return q1 - 1.5 * iqr, q3 + 1.5 * iqr


def outside_brazil(geo: pd.DataFrame) -> pd.Series:
    return ~geo["geolocation_lat"].between(*BRAZIL_LAT) | ~geo["geolocation_lng"].between(*BRAZIL_LNG)


def cep_state(zip_prefix: pd.Series) -> pd.Series:
    """Suy ra bang từ 5 số đầu CEP theo dải mã của Correios."""
    numbers = pd.to_numeric(zip_prefix, errors="coerce")
    result = pd.Series(np.nan, index=zip_prefix.index, dtype="object")
    for state, ranges in CEP_RANGES.items():
        for low, high in ranges:
            result[numbers.between(low, high)] = state
    return result


def zip_state_mode(geo: pd.DataFrame) -> pd.Series:
    """Bang xuất hiện nhiều nhất của từng zip prefix trong geolocation."""
    return geo.groupby("geolocation_zip_code_prefix")["geolocation_state"].agg(lambda s: s.mode()[0])


def haversine_km(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(np.radians, (lat1, lng1, lat2, lng2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def zip_spread_km(geo: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Khoảng cách từng điểm (trong Brazil) tới điểm trung vị của zip, và khoảng cách xa nhất mỗi zip."""
    zip_col = "geolocation_zip_code_prefix"
    inside = geo[~outside_brazil(geo)]
    center = inside.groupby(zip_col)[["geolocation_lat", "geolocation_lng"]].transform("median")
    distance = haversine_km(
        inside["geolocation_lat"], inside["geolocation_lng"],
        center["geolocation_lat"], center["geolocation_lng"],
    )
    return distance, distance.groupby(inside[zip_col]).max()


def invalid_timeline(orders: pd.DataFrame) -> pd.Series:
    """Mốc thời gian ngược thật: giao vận chuyển trước khi mua, khách nhận trước khi giao vận chuyển/mua."""
    purchase, _, carrier, customer, _ = (orders[c] for c in ORDER_TIME_COLUMNS)
    return (carrier < purchase) | (customer < carrier) | (customer < purchase)
