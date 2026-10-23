from pathlib import Path
import sys
import unicodedata

import pandas as pd


# Tên ngắn của bảng (dùng trong báo cáo) -> file nguồn.
TABLE_FILES = {
    "customers": "olist_customers_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

# Mã bưu chính phải đọc dạng chuỗi để giữ số 0 ở đầu (01003, không phải 1003).
ZIP_COLUMNS = [
    "customer_zip_code_prefix",
    "seller_zip_code_prefix",
    "geolocation_zip_code_prefix",
]

# Các cặp quan hệ cần kiểm tra theo Bảng 2.3:
# (bảng con, cột ở bảng con, bảng cha, cột ở bảng cha).
RELATIONSHIPS = [
    ("orders", "customer_id", "customers", "customer_id"),
    ("order_items", "order_id", "orders", "order_id"),
    ("order_items", "product_id", "products", "product_id"),
    ("order_items", "seller_id", "sellers", "seller_id"),
    ("order_payments", "order_id", "orders", "order_id"),
    ("order_reviews", "order_id", "orders", "order_id"),
    ("products", "product_category_name", "category_translation", "product_category_name"),
    ("customers", "customer_zip_code_prefix", "geolocation", "geolocation_zip_code_prefix"),
    ("sellers", "seller_zip_code_prefix", "geolocation", "geolocation_zip_code_prefix"),
]

ORDER_TIME_COLUMNS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]

# Khung tọa độ lãnh thổ Brazil.
BRAZIL_LAT = (-33.75, 5.27)
BRAZIL_LNG = (-73.99, -34.79)


def load_tables(data_dir: Path) -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}
    for name, file_name in TABLE_FILES.items():
        file_path = data_dir / file_name
        if not file_path.is_file():
            raise FileNotFoundError(f"Không tìm thấy file: {file_path}")
        tables[name] = pd.read_csv(
            file_path,
            low_memory=False,
            dtype={column: str for column in ZIP_COLUMNS},
        )
        print(f"[OK] {file_name}")

    orders = tables["orders"]
    for column in ORDER_TIME_COLUMNS:
        orders[column] = pd.to_datetime(orders[column], errors="coerce")
    tables["order_items"]["shipping_limit_date"] = pd.to_datetime(
        tables["order_items"]["shipping_limit_date"], errors="coerce"
    )
    return tables


def percent(part: int, whole: int) -> str:
    return f"{part / whole * 100:.2f}%" if whole else "0%"


def normalize_text(value: str) -> str:
    without_accents = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        char for char in without_accents if not unicodedata.combining(char)
    )
    return " ".join(without_accents.lower().split())


# ---------------------------------------------------------------------------
# 2.4. Quan hệ giữa các bảng
# ---------------------------------------------------------------------------


def check_relationship(
    tables: dict[str, pd.DataFrame],
    child: str,
    child_column: str,
    parent: str,
    parent_column: str,
) -> dict[str, object]:
    child_keys = tables[child][child_column]
    parent_keys = tables[parent][parent_column].dropna()
    parent_set = set(parent_keys)

    # Bản ghi con không khớp: có giá trị khóa nhưng không tìm thấy ở bảng cha.
    has_key = child_keys.notna()
    orphan_mask = has_key & ~child_keys.isin(parent_set)
    orphan_rows = int(orphan_mask.sum())
    orphan_values = int(child_keys[orphan_mask].nunique())
    null_rows = int((~has_key).sum())

    # Bản ghi cha không có bản ghi con nào tham chiếu tới.
    childless = len(parent_set - set(child_keys.dropna()))

    # Kiểu quan hệ: bảng cha có khóa duy nhất không, mỗi khóa cha có bao nhiêu con.
    parent_unique = parent_keys.is_unique
    children_per_key = child_keys.dropna().value_counts()
    max_children = int(children_per_key.max()) if not children_per_key.empty else 0

    if not parent_unique:
        relation_type = "n – n"
    elif max_children <= 1:
        relation_type = "1 – 1"
    else:
        relation_type = "1 – n"

    notes = [
        f"{orphan_rows:,} dòng con ({percent(orphan_rows, len(child_keys))}, "
        f"{orphan_values:,} giá trị khóa) không có ở {parent}"
    ]
    if null_rows:
        notes.append(f"{null_rows:,} dòng con có khóa NULL")
    notes.append(
        f"{childless:,}/{len(parent_set):,} khóa ở {parent} không xuất hiện ở {child}"
    )
    notes.append(f"Tối đa {max_children:,} dòng {child} / 1 khóa")
    if not parent_unique:
        duplicated = len(parent_keys) - parent_keys.nunique()
        notes.append(
            f"Khóa ở {parent} không duy nhất ({duplicated:,} dòng trùng) → cần gom nhóm trước khi nối"
        )
    if orphan_values and orphan_values <= 5:
        sample = ", ".join(sorted(child_keys[orphan_mask].astype(str).unique()))
        notes.append(f"Giá trị không khớp: {sample}")

    return {
        "Quan hệ": f"{child} → {parent}",
        "Khóa nối": child_column
        if child_column == parent_column
        else f"{child_column} = {parent_column}",
        "Kiểu quan hệ": relation_type,
        "Số bản ghi không khớp": orphan_rows,
        "Nhận xét": "; ".join(notes),
    }


# ---------------------------------------------------------------------------
# 2.5. Các vấn đề dữ liệu: mỗi hàm kiểm tra trả về None nếu không phát hiện vấn đề,
# ngược lại trả về một dòng cho Bảng 2.4 với bằng chứng được tính từ dữ liệu thật.
# ---------------------------------------------------------------------------


def issue(
    problem: str, evidence: str, impact: str, solution: str, layer: str
) -> dict[str, str]:
    return {
        "Vấn đề phát hiện": problem,
        "Bằng chứng (số liệu)": evidence,
        "Ảnh hưởng đến phân tích": impact,
        "Hướng xử lý": solution,
        "Tầng xử lý": layer,
    }


def check_customer_identity(t: dict[str, pd.DataFrame]) -> dict[str, str] | None:
    customers = t["customers"]
    ids = customers["customer_id"].nunique()
    unique_ids = customers["customer_unique_id"].nunique()
    if unique_ids == ids:
        return None
    repeat = int((customers["customer_unique_id"].value_counts() > 1).sum())
    return issue(
        "customer_id được sinh mới cho mỗi đơn hàng, không đại diện cho một khách hàng",
        f"{ids:,} customer_id nhưng chỉ {unique_ids:,} customer_unique_id; "
        f"{repeat:,} khách có từ 2 customer_id trở lên",
        "Đếm khách hàng, tỷ lệ khách quay lại theo customer_id sẽ bị thổi phồng",
        "Dùng customer_unique_id làm khóa tự nhiên của Dim_Customer; giữ customer_id để nối với orders",
        "dbt",
    )


def check_duplicate_reviews(t: dict[str, pd.DataFrame]) -> dict[str, str] | None:
    reviews = t["order_reviews"]
    duplicate_ids = int(reviews["review_id"].duplicated(keep=False).sum())
    multi_review_orders = int((reviews["order_id"].value_counts() > 1).sum())
    if not duplicate_ids and not multi_review_orders:
        return None
    return issue(
        "review_id bị trùng và một đơn hàng có nhiều đánh giá",
        f"{duplicate_ids:,} dòng có review_id trùng; {multi_review_orders:,} đơn có > 1 đánh giá",
        "Nối reviews với orders/order_items làm nhân bản dòng, sai điểm trung bình và doanh thu",
        "Khóa Staging dùng review_id + order_id; ở dbt giữ đánh giá mới nhất (review_answer_timestamp) cho mỗi đơn",
        "Staging (ghi nhận) / dbt (xử lý)",
    )


def check_geolocation(t: dict[str, pd.DataFrame]) -> dict[str, str] | None:
    geo = t["geolocation"]
    zip_count = geo["geolocation_zip_code_prefix"].nunique()
    exact_duplicates = int(geo.duplicated().sum())
    outside = int(
        (~geo["geolocation_lat"].between(*BRAZIL_LAT)
         | ~geo["geolocation_lng"].between(*BRAZIL_LNG)).sum()
    )
    return issue(
        "geolocation có nhiều tọa độ cho cùng một zip prefix, có dòng trùng hoàn toàn và tọa độ ngoài Brazil",
        f"{len(geo):,} dòng / {zip_count:,} zip prefix (TB {len(geo) / zip_count:.1f} dòng/zip); "
        f"{exact_duplicates:,} dòng trùng hoàn toàn; {outside:,} dòng ngoài lãnh thổ Brazil",
        "Nối trực tiếp với customers/sellers sẽ nhân bản dòng; bản đồ hiển thị điểm sai vị trí",
        "Loại tọa độ ngoài Brazil, gom nhóm theo zip prefix (trung vị lat/lng) để mỗi zip còn 1 dòng",
        "dbt",
    )


def check_city_names(t: dict[str, pd.DataFrame]) -> dict[str, str] | None:
    details: list[str] = []
    total = 0
    for table, column in [
        ("customers", "customer_city"),
        ("sellers", "seller_city"),
        ("geolocation", "geolocation_city"),
    ]:
        values = t[table][column].dropna().astype(str)
        raw = values.nunique()
        normalized = values.map(normalize_text).nunique()
        if raw > normalized:
            details.append(f"{column}: {raw:,} → {normalized:,} sau chuẩn hóa")
            total += raw - normalized
    if not total:
        return None
    return issue(
        "Tên thành phố không nhất quán (hoa/thường, dấu, khoảng trắng)",
        "; ".join(details) + " (VD: 'são paulo' và 'sao paulo')",
        "Cùng một thành phố bị tách thành nhiều giá trị khi thống kê theo địa lý",
        "Chuẩn hóa: bỏ dấu, chữ thường, cắt khoảng trắng; ưu tiên phân tích theo bang (state)",
        "dbt",
    )


def check_zip_leading_zero(t: dict[str, pd.DataFrame]) -> dict[str, str] | None:
    leading_zero = int(t["customers"]["customer_zip_code_prefix"].str.startswith("0").sum())
    if not leading_zero:
        return None
    return issue(
        "Mã bưu chính có số 0 ở đầu, dễ bị mất khi đọc dạng số",
        f"{leading_zero:,} customer_zip_code_prefix bắt đầu bằng '0'; "
        "pandas/SQL đọc mặc định dạng số sẽ đổi '01003' thành 1003",
        "Không nối được customers/sellers với geolocation nếu hai bên khác kiểu",
        "Khai báo cột zip là VARCHAR(5) trong bảng Staging; đọc CSV với dtype=str",
        "Staging",
    )


def check_order_status_dates(t: dict[str, pd.DataFrame]) -> dict[str, str] | None:
    orders = t["orders"]
    delivered = orders["order_status"] == "delivered"
    delivered_no_date = int((delivered & orders["order_delivered_customer_date"].isna()).sum())
    not_delivered_with_date = int(
        (~delivered & orders["order_delivered_customer_date"].notna()).sum()
    )
    missing = orders[ORDER_TIME_COLUMNS[1:4]].isna().sum()
    return issue(
        "Thiếu mốc thời gian đơn hàng và trạng thái mâu thuẫn với ngày giao",
        f"NULL: order_approved_at {missing['order_approved_at']:,}, "
        f"order_delivered_carrier_date {missing['order_delivered_carrier_date']:,}, "
        f"order_delivered_customer_date {missing['order_delivered_customer_date']:,}; "
        f"{delivered_no_date:,} đơn 'delivered' không có ngày giao; "
        f"{not_delivered_with_date:,} đơn chưa 'delivered' nhưng có ngày giao",
        "Sai số ngày giao hàng, tỷ lệ giao trễ nếu không lọc theo trạng thái",
        "Chỉ tính chỉ số giao hàng cho đơn 'delivered' có đủ ngày; giữ NULL (không điền giá trị giả), gắn cờ đơn mâu thuẫn",
        "dbt",
    )


def check_order_time_sequence(t: dict[str, pd.DataFrame]) -> dict[str, str] | None:
    orders = t["orders"]
    purchase = orders["order_purchase_timestamp"]
    approved_before = int((orders["order_approved_at"] < purchase).sum())
    carrier_before = int((orders["order_delivered_carrier_date"] < purchase).sum())
    customer_before_carrier = int(
        (orders["order_delivered_customer_date"] < orders["order_delivered_carrier_date"]).sum()
    )
    total = approved_before + carrier_before + customer_before_carrier
    if not total:
        return None
    return issue(
        "Thứ tự các mốc thời gian đơn hàng không hợp lý",
        f"{approved_before:,} đơn duyệt trước khi mua; {carrier_before:,} đơn giao cho vận chuyển trước khi mua; "
        f"{customer_before_carrier:,} đơn khách nhận trước khi giao cho vận chuyển",
        "Thời gian xử lý / vận chuyển bị âm, làm lệch các chỉ số trung bình",
        "Gắn cờ is_invalid_timeline; loại khỏi phép tính thời gian giao hàng",
        "dbt",
    )


def check_shipping_limit_date(t: dict[str, pd.DataFrame]) -> dict[str, str] | None:
    items = t["order_items"]
    last_purchase = t["orders"]["order_purchase_timestamp"].max()
    late = items["shipping_limit_date"] > last_purchase + pd.Timedelta(days=60)
    count = int(late.sum())
    if not count:
        return None
    return issue(
        "shipping_limit_date vượt xa phạm vi thời gian của đơn hàng",
        f"{count:,} dòng có shipping_limit_date sau {last_purchase:%Y-%m-%d} + 60 ngày; "
        f"lớn nhất {items['shipping_limit_date'].max():%Y-%m-%d}",
        "Dim_Date phải mở rộng tới năm 2020; chỉ số hạn giao bị lệch",
        "Gắn cờ ngày bất thường; Dim_Date sinh theo min/max thực tế của mọi cột ngày",
        "dbt",
    )


def check_sparse_months(t: dict[str, pd.DataFrame]) -> dict[str, str] | None:
    monthly = (
        t["orders"]["order_purchase_timestamp"].dt.to_period("M").value_counts().sort_index()
    )
    threshold = monthly.median() * 0.1
    sparse = monthly[monthly < threshold]
    if sparse.empty:
        return None
    detail = ", ".join(f"{period}: {count:,}" for period, count in sparse.items())
    return issue(
        "Một số tháng ở đầu/cuối kỳ có rất ít đơn hàng",
        f"Trung vị {monthly.median():,.0f} đơn/tháng; các tháng < 10% trung vị: {detail}",
        "So sánh theo tháng/năm (tăng trưởng, YoY) bị sai lệch do dữ liệu không đầy đủ",
        "Giới hạn phạm vi phân tích (VD: 2017-01 → 2018-08) hoặc ghi chú rõ trên dashboard",
        "dbt / Power BI",
    )


def check_product_category(t: dict[str, pd.DataFrame]) -> dict[str, str] | None:
    products = t["products"]
    missing = int(products["product_category_name"].isna().sum())
    translated = set(t["category_translation"]["product_category_name"])
    untranslated = (
        products["product_category_name"].dropna().loc[lambda s: ~s.isin(translated)]
    )
    return issue(
        "Sản phẩm thiếu danh mục hoặc danh mục chưa có bản dịch tiếng Anh",
        f"{missing:,} sản phẩm NULL danh mục ({percent(missing, len(products))}); "
        f"{len(untranslated):,} sản phẩm thuộc {untranslated.nunique()} danh mục không có trong bảng dịch "
        f"({', '.join(sorted(untranslated.unique()))})",
        "Doanh thu theo danh mục bị thiếu hoặc hiển thị tên tiếng Bồ Đào Nha",
        "Gán 'unknown' cho danh mục NULL; bổ sung bản dịch thủ công cho danh mục còn thiếu",
        "dbt",
    )


def check_column_name_typo(t: dict[str, pd.DataFrame]) -> dict[str, str] | None:
    typo = [column for column in t["products"].columns if "lenght" in column]
    if not typo:
        return None
    return issue(
        "Tên cột viết sai chính tả",
        f"products có các cột: {', '.join(typo)} ('lenght' thay vì 'length')",
        "Dễ nhầm khi viết truy vấn, tên cột thiếu chuyên nghiệp trên báo cáo",
        "Giữ nguyên tên gốc ở Staging để truy vết; đổi tên thành *_length ở dbt",
        "dbt",
    )


def check_orders_without_children(t: dict[str, pd.DataFrame]) -> dict[str, str] | None:
    orders = t["orders"]
    no_items = ~orders["order_id"].isin(t["order_items"]["order_id"])
    no_payment = ~orders["order_id"].isin(t["order_payments"]["order_id"])
    status = orders.loc[no_items, "order_status"].value_counts().head(3)
    status_text = ", ".join(f"{name}: {count:,}" for name, count in status.items())
    return issue(
        "Đơn hàng không có dòng sản phẩm hoặc không có thanh toán",
        f"{int(no_items.sum()):,} đơn không có trong order_items ({status_text}); "
        f"{int(no_payment.sum()):,} đơn không có trong order_payments",
        "Số đơn hàng đếm từ orders và từ order_items không khớp nhau",
        "Fact bán hàng lấy từ order_items; đối chiếu số đơn giữa các Fact và giải thích chênh lệch",
        "Staging (ghi nhận) / dbt (xử lý)",
    )


def check_payment_values(t: dict[str, pd.DataFrame]) -> dict[str, str] | None:
    payments = t["order_payments"]
    zero_value = int((payments["payment_value"] == 0).sum())
    zero_installments = int((payments["payment_installments"] == 0).sum())
    not_defined = int((payments["payment_type"] == "not_defined").sum())

    # Tổng thanh toán của đơn so với tổng (giá + phí vận chuyển) của các dòng sản phẩm.
    item_total = t["order_items"].assign(
        total=lambda d: d["price"] + d["freight_value"]
    ).groupby("order_id")["total"].sum()
    paid_total = payments.groupby("order_id")["payment_value"].sum()
    compared = pd.concat([item_total, paid_total], axis=1, join="inner").dropna()
    mismatched = int(((compared["total"] - compared["payment_value"]).abs() > 1).sum())

    return issue(
        "Giá trị thanh toán bất thường và lệch so với giá trị đơn hàng",
        f"{zero_value:,} dòng payment_value = 0; {zero_installments:,} dòng payment_installments = 0; "
        f"{not_defined:,} dòng payment_type = 'not_defined'; "
        f"{mismatched:,}/{len(compared):,} đơn có tổng thanh toán lệch > 1 BRL so với price + freight",
        "Doanh thu tính từ payments và từ order_items cho kết quả khác nhau",
        "Thống nhất doanh thu = price + freight_value từ order_items; payments dùng cho phân tích thanh toán; gắn cờ dòng bất thường",
        "dbt",
    )


def check_price_outliers(t: dict[str, pd.DataFrame]) -> dict[str, str] | None:
    items = t["order_items"]
    q1, q3 = items["price"].quantile([0.25, 0.75])
    upper = q3 + 1.5 * (q3 - q1)
    outliers = int((items["price"] > upper).sum())
    zero_freight = int((items["freight_value"] == 0).sum())
    return issue(
        "price và freight_value lệch phải mạnh, có giá trị rất lớn và phí vận chuyển bằng 0",
        f"price: trung vị {items['price'].median():,.2f}, max {items['price'].max():,.2f}, "
        f"{outliers:,} dòng > {upper:,.2f} (IQR); {zero_freight:,} dòng freight_value = 0",
        "Giá trị trung bình bị kéo lệch; biểu đồ phân phối khó đọc",
        "Giữ lại (giao dịch hợp lệ), dùng trung vị bên cạnh trung bình; phân nhóm khoảng giá",
        "dbt / Power BI",
    )


def check_review_comments(t: dict[str, pd.DataFrame]) -> dict[str, str] | None:
    reviews = t["order_reviews"]
    title = reviews["review_comment_title"].isna().mean() * 100
    message = reviews["review_comment_message"].isna().mean() * 100
    return issue(
        "Phần lớn đánh giá không có tiêu đề / nội dung bình luận",
        f"review_comment_title NULL {title:.2f}%; review_comment_message NULL {message:.2f}%",
        "Phân tích văn bản (GenAI, sentiment) chỉ dùng được trên một phần nhỏ đánh giá",
        "Giữ NULL; tạo cờ has_comment; phân tích chính dựa trên review_score",
        "dbt",
    )


ISSUE_CHECKS = [
    check_customer_identity,
    check_duplicate_reviews,
    check_orders_without_children,
    check_order_status_dates,
    check_order_time_sequence,
    check_shipping_limit_date,
    check_sparse_months,
    check_product_category,
    check_payment_values,
    check_price_outliers,
    check_geolocation,
    check_city_names,
    check_zip_leading_zero,
    check_review_comments,
    check_column_name_typo,
]


def main() -> None:
    # Tránh UnicodeEncodeError khi Windows Terminal đang dùng bảng mã cp1252.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # Dùng đường dẫn tương đối với chính file này, không phụ thuộc thư mục chạy lệnh.
    project_dir = Path(__file__).resolve().parent
    data_dir = project_dir / "data"

    if not data_dir.is_dir():
        raise FileNotFoundError(f"Không tìm thấy thư mục dữ liệu: {data_dir}")

    tables = load_tables(data_dir)

    relationships = pd.DataFrame(
        [check_relationship(tables, *relationship) for relationship in RELATIONSHIPS]
    )
    relationship_path = project_dir / "Bang_Quan_He_Bang.csv"
    relationships.to_csv(relationship_path, index=False, encoding="utf-8-sig")

    issues: list[dict[str, str]] = []
    for check in ISSUE_CHECKS:
        try:
            result = check(tables)
        except Exception as error:
            print(f"[LOI] {check.__name__}: {error}")
            continue
        if result:
            issues.append(result)

    issue_table = pd.DataFrame(issues)
    issue_table.insert(0, "STT", range(1, len(issue_table) + 1))
    issue_path = project_dir / "Bang_Van_De_Du_Lieu.csv"
    issue_table.to_csv(issue_path, index=False, encoding="utf-8-sig")

    print("\nKET QUA QUAN HE GIUA CAC BANG")
    print(relationships.to_string(index=False, max_colwidth=80))
    print("\nCAC VAN DE DU LIEU PHAT HIEN")
    print(issue_table[["STT", "Vấn đề phát hiện", "Bằng chứng (số liệu)"]].to_string(
        index=False, max_colwidth=100
    ))
    print(f"\nĐã lưu bảng quan hệ tại: {relationship_path}")
    print(f"Đã lưu bảng vấn đề tại: {issue_path}")


if __name__ == "__main__":
    main()
