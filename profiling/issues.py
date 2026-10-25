"""Bảng 2.5 — Các vấn đề dữ liệu, bằng chứng và hướng xử lý.

Mỗi hàm check_* trả về None nếu không phát hiện vấn đề, ngược lại trả về một dòng của bảng
với bằng chứng tính từ dữ liệu thật. Thêm check mới: viết hàm rồi thêm vào cuối ISSUE_CHECKS
(giữ nguyên thứ tự để STT của các vấn đề cũ không đổi).

Kết quả: output/Bang_Van_De_Du_Lieu.csv
"""
import pandas as pd

from profiling.common import (
    DATA_DIR,
    DEFAULT_DIMENSIONS,
    FAR_POINT_KM,
    NON_REVENUE_STATUSES,
    ORDER_TIME_COLUMNS,
    TABLE_FILES,
    cep_state,
    load_tables,
    normalize_text,
    outside_brazil,
    pct,
    save_csv,
    setup_console,
    zip_spread_km,
    zip_state_mode,
)

Tables = dict[str, pd.DataFrame]


def issue(problem: str, evidence: str, impact: str, solution: str, layer: str) -> dict[str, str]:
    return {
        "Vấn đề phát hiện": problem,
        "Bằng chứng (số liệu)": evidence,
        "Ảnh hưởng đến phân tích": impact,
        "Hướng xử lý": solution,
        "Tầng xử lý": layer,
    }


def check_customer_identity(t: Tables) -> dict[str, str] | None:
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


def check_duplicate_reviews(t: Tables) -> dict[str, str] | None:
    reviews = t["order_reviews"]
    shared = reviews[reviews["review_id"].duplicated(keep=False)]
    multi_review_orders = int((reviews["order_id"].value_counts() > 1).sum())
    if shared.empty and not multi_review_orders:
        return None
    # review_id dùng chung cho nhiều đơn: kiểm tra nội dung có giống hệt nhau không.
    same_content = (
        shared.groupby("review_id")[["review_score", "review_comment_message", "review_creation_date"]]
        .nunique(dropna=False).max(axis=1).eq(1)
    )
    return issue(
        "review_id bị trùng và một đơn hàng có nhiều đánh giá",
        f"{len(shared):,} dòng có review_id trùng ({shared['review_id'].nunique():,} review_id, "
        f"{int(same_content.sum()):,} có nội dung giống hệt nhau giữa các đơn); "
        f"{multi_review_orders:,} đơn có > 1 đánh giá",
        "Nối reviews với orders/order_items làm nhân bản dòng, sai điểm trung bình và doanh thu",
        "Khóa Staging dùng review_id + order_id; ở dbt giữ đánh giá mới nhất (review_answer_timestamp) cho mỗi đơn",
        "Staging (ghi nhận) / dbt (xử lý)",
    )


def check_orders_without_children(t: Tables) -> dict[str, str] | None:
    orders = t["orders"]
    no_items = ~orders["order_id"].isin(t["order_items"]["order_id"])
    no_payment = ~orders["order_id"].isin(t["order_payments"]["order_id"])
    status = orders.loc[no_items, "order_status"].value_counts().head(3)
    return issue(
        "Đơn hàng không có dòng sản phẩm hoặc không có thanh toán",
        f"{int(no_items.sum()):,} đơn không có trong order_items "
        f"({', '.join(f'{name}: {count:,}' for name, count in status.items())}); "
        f"{int(no_payment.sum()):,} đơn không có trong order_payments",
        "Số đơn hàng đếm từ orders và từ order_items không khớp nhau",
        "Fact bán hàng lấy từ order_items; đối chiếu số đơn giữa các Fact và giải thích chênh lệch",
        "Staging (ghi nhận) / dbt (xử lý)",
    )


def check_order_status_dates(t: Tables) -> dict[str, str] | None:
    orders = t["orders"]
    delivered = orders["order_status"] == "delivered"
    has_delivery = orders["order_delivered_customer_date"].notna()
    missing = orders[ORDER_TIME_COLUMNS[1:4]].isna().sum()
    return issue(
        "Thiếu mốc thời gian đơn hàng và trạng thái mâu thuẫn với ngày giao",
        f"NULL: order_approved_at {missing['order_approved_at']:,}, "
        f"order_delivered_carrier_date {missing['order_delivered_carrier_date']:,}, "
        f"order_delivered_customer_date {missing['order_delivered_customer_date']:,}; "
        f"{int((delivered & ~has_delivery).sum()):,} đơn 'delivered' không có ngày giao; "
        f"{int((~delivered & has_delivery).sum()):,} đơn chưa 'delivered' nhưng có ngày giao",
        "Sai số ngày giao hàng, tỷ lệ giao trễ nếu không lọc theo trạng thái",
        "Chỉ tính chỉ số giao hàng cho đơn 'delivered' có đủ ngày; giữ NULL (không điền giá trị giả); "
        "đơn chưa 'delivered' nhưng có ngày giao: không xóa ngày giao, giữ giá trị gốc, gắn cờ is_status_conflict "
        "và loại khỏi KPI giao hàng",
        "dbt",
    )


def check_order_time_sequence(t: Tables) -> dict[str, str] | None:
    orders = t["orders"]
    purchase = orders["order_purchase_timestamp"]
    approved_before = int((orders["order_approved_at"] < purchase).sum())
    carrier_before = int((orders["order_delivered_carrier_date"] < purchase).sum())
    customer_before_carrier = int(
        (orders["order_delivered_customer_date"] < orders["order_delivered_carrier_date"]).sum()
    )
    if not (approved_before or carrier_before or customer_before_carrier):
        return None
    return issue(
        "Thứ tự các mốc thời gian đơn hàng không hợp lý",
        f"{approved_before:,} đơn duyệt trước khi mua; {carrier_before:,} đơn giao cho vận chuyển trước khi mua; "
        f"{customer_before_carrier:,} đơn khách nhận trước khi giao cho vận chuyển",
        "Thời gian xử lý / vận chuyển bị âm, làm lệch các chỉ số trung bình",
        "Gắn cờ is_invalid_timeline; loại khỏi phép tính thời gian giao hàng",
        "dbt",
    )


def check_shipping_limit_date(t: Tables) -> dict[str, str] | None:
    items = t["order_items"]
    last_purchase = t["orders"]["order_purchase_timestamp"].max()
    count = int((items["shipping_limit_date"] > last_purchase + pd.Timedelta(days=60)).sum())
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


def check_sparse_months(t: Tables) -> dict[str, str] | None:
    monthly = t["orders"]["order_purchase_timestamp"].dt.to_period("M").value_counts().sort_index()
    sparse = monthly[monthly < monthly.median() * 0.1]
    if sparse.empty:
        return None
    empty = pd.period_range(monthly.index.min(), monthly.index.max(), freq="M").difference(monthly.index)
    empty_text = f"; tháng không có đơn nào: {', '.join(map(str, empty))}" if len(empty) else ""
    return issue(
        "Một số tháng ở đầu/cuối kỳ có rất ít đơn hàng",
        f"Trung vị {monthly.median():,.0f} đơn/tháng; các tháng < 10% trung vị: "
        f"{', '.join(f'{period}: {count:,}' for period, count in sparse.items())}{empty_text}",
        "So sánh theo tháng/năm (tăng trưởng, YoY) bị sai lệch do dữ liệu không đầy đủ",
        "Giới hạn phạm vi phân tích (VD: 2017-01 → 2018-08) hoặc ghi chú rõ trên dashboard",
        "dbt / Power BI",
    )


def check_product_category(t: Tables) -> dict[str, str] | None:
    products = t["products"]
    missing = int(products["product_category_name"].isna().sum())
    translated = set(t["category_translation"]["product_category_name"])
    untranslated = products["product_category_name"].dropna().loc[lambda s: ~s.isin(translated)]
    return issue(
        "Sản phẩm thiếu danh mục hoặc danh mục chưa có bản dịch tiếng Anh",
        f"{missing:,} sản phẩm NULL danh mục ({pct(missing, len(products))}); "
        f"{len(untranslated):,} sản phẩm thuộc {untranslated.nunique()} danh mục không có trong bảng dịch "
        f"({', '.join(sorted(untranslated.unique()))})",
        "Doanh thu theo danh mục bị thiếu hoặc hiển thị tên tiếng Bồ Đào Nha",
        "Gán 'unknown' cho danh mục NULL; bổ sung bản dịch thủ công cho danh mục còn thiếu",
        "dbt",
    )


def check_payment_values(t: Tables) -> dict[str, str] | None:
    payments = t["order_payments"]
    # Tổng thanh toán của đơn so với tổng (giá + phí vận chuyển) của các dòng sản phẩm.
    items = t["order_items"]
    item_total = (items["price"] + items["freight_value"]).groupby(items["order_id"]).sum()
    paid_total = payments.groupby("order_id")["payment_value"].sum()
    compared = pd.concat([item_total.rename("total"), paid_total], axis=1, join="inner").dropna()
    mismatched = int(((compared["total"] - compared["payment_value"]).abs() > 1).sum())
    return issue(
        "Giá trị thanh toán bất thường và lệch so với giá trị đơn hàng",
        f"{int((payments['payment_value'] == 0).sum()):,} dòng payment_value = 0; "
        f"{int((payments['payment_installments'] == 0).sum()):,} dòng payment_installments = 0; "
        f"{int((payments['payment_type'] == 'not_defined').sum()):,} dòng payment_type = 'not_defined'; "
        f"{mismatched:,}/{len(compared):,} đơn có tổng thanh toán lệch > 1 BRL so với price + freight",
        "Doanh thu tính từ payments và từ order_items cho kết quả khác nhau",
        "Thống nhất doanh thu = price + freight_value từ order_items; payments dùng cho phân tích thanh toán; "
        "gắn cờ dòng bất thường",
        "dbt",
    )


def check_price_outliers(t: Tables) -> dict[str, str] | None:
    items = t["order_items"]
    q1, q3 = items["price"].quantile([0.25, 0.75])
    upper = q3 + 1.5 * (q3 - q1)
    return issue(
        "price và freight_value lệch phải mạnh, có giá trị rất lớn và phí vận chuyển bằng 0",
        f"price: trung vị {items['price'].median():,.2f}, max {items['price'].max():,.2f}, "
        f"{int((items['price'] > upper).sum()):,} dòng > {upper:,.2f} (IQR); "
        f"{int((items['freight_value'] == 0).sum()):,} dòng freight_value = 0",
        "Giá trị trung bình bị kéo lệch; biểu đồ phân phối khó đọc",
        "Giữ lại (giao dịch hợp lệ), dùng trung vị bên cạnh trung bình; phân nhóm khoảng giá",
        "dbt / Power BI",
    )


def check_geolocation(t: Tables) -> dict[str, str] | None:
    geo = t["geolocation"]
    zip_count = geo["geolocation_zip_code_prefix"].nunique()
    return issue(
        "geolocation có nhiều tọa độ cho cùng một zip prefix, có dòng trùng hoàn toàn và tọa độ ngoài Brazil",
        f"{len(geo):,} dòng / {zip_count:,} zip prefix (TB {len(geo) / zip_count:.1f} dòng/zip); "
        f"{int(geo.duplicated().sum()):,} dòng trùng hoàn toàn; {int(outside_brazil(geo).sum()):,} dòng ngoài lãnh thổ Brazil",
        "Nối trực tiếp với customers/sellers sẽ nhân bản dòng; bản đồ hiển thị điểm sai vị trí",
        "Loại tọa độ ngoài Brazil, gom nhóm theo zip prefix (trung vị lat/lng) để mỗi zip còn 1 dòng",
        "dbt",
    )


def check_city_names(t: Tables) -> dict[str, str] | None:
    details = []
    for table, column in [("customers", "customer_city"), ("sellers", "seller_city"), ("geolocation", "geolocation_city")]:
        values = t[table][column].dropna().astype(str)
        raw, normalized = values.nunique(), values.map(normalize_text).nunique()
        if raw > normalized:
            details.append(f"{column}: {raw:,} → {normalized:,} sau chuẩn hóa")
    if not details:
        return None
    return issue(
        "Tên thành phố không nhất quán (hoa/thường, dấu, khoảng trắng)",
        "; ".join(details) + " (VD: 'são paulo' và 'sao paulo')",
        "Cùng một thành phố bị tách thành nhiều giá trị khi thống kê theo địa lý",
        "Chuẩn hóa: bỏ dấu, chữ thường, cắt khoảng trắng; ưu tiên phân tích theo bang (state)",
        "dbt",
    )


def check_zip_leading_zero(t: Tables) -> dict[str, str] | None:
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


def check_review_comments(t: Tables) -> dict[str, str] | None:
    reviews = t["order_reviews"]
    message = reviews["review_comment_message"]
    # Khách chấm điểm thấp viết bình luận nhiều hơn → khuyết không ngẫu nhiên (MNAR).
    by_score = message.notna().groupby(reviews["review_score"]).mean()
    return issue(
        "Phần lớn đánh giá không có tiêu đề / nội dung bình luận",
        f"review_comment_title NULL {reviews['review_comment_title'].isna().mean() * 100:.2f}%; "
        f"review_comment_message NULL {message.isna().mean() * 100:.2f}%; "
        f"{int((message.str.strip() == '').sum()):,} bình luận chỉ có khoảng trắng; "
        f"tỷ lệ có bình luận: 1★ {by_score[1]:.1%}, 5★ {by_score[5]:.1%} (MNAR)",
        "Phân tích văn bản (GenAI, sentiment) chỉ dùng được trên một phần nhỏ đánh giá",
        "Giữ NULL (không điền); bình luận chỉ có khoảng trắng → NULL; tạo cờ has_comment; "
        "phân tích chính dựa trên review_score",
        "dbt",
    )


def check_column_name_typo(t: Tables) -> dict[str, str] | None:
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


def check_product_dimensions(t: Tables) -> dict[str, str] | None:
    products = t["products"]
    weight = products["product_weight_g"]
    length, height, width = DEFAULT_DIMENSIONS
    default_size = int(
        ((products["product_length_cm"] == length)
         & (products["product_height_cm"] == height)
         & (products["product_width_cm"] == width)).sum()
    )
    volume = products["product_length_cm"] * products["product_height_cm"] * products["product_width_cm"]
    too_dense = int((weight / volume > 5).sum())  # g/cm³; nước = 1, sắt ~7.8
    heavy_tiny = int(((weight > 10_000) & (volume < 1_000)).sum())
    zero_weight = int((weight == 0).sum())
    if not (zero_weight or default_size or too_dense or heavy_tiny):
        return None
    return issue(
        "Cân nặng và kích thước sản phẩm không hợp lý",
        f"{zero_weight:,} sản phẩm nặng 0 g; {default_size:,} sản phẩm có đúng kích thước mặc định "
        f"{length}x{height}x{width} cm; {too_dense:,} sản phẩm mật độ > 5 g/cm³; "
        f"{heavy_tiny:,} sản phẩm nặng > 10 kg nhưng thể tích < 1 lít; "
        f"{int(weight.isna().sum()):,} sản phẩm thiếu cân nặng/kích thước",
        "Phân tích phí vận chuyển theo cân nặng/kích thước bị sai; cân nặng 0 kéo giá trị trung bình xuống",
        "Cân nặng 0 → NULL; gắn cờ is_default_dimensions, is_suspicious_weight; giữ NULL cho sản phẩm thiếu số đo",
        "dbt",
    )


def check_category_translation(t: Tables) -> dict[str, str] | None:
    translation = t["category_translation"]
    english = translation["product_category_name_english"]
    typo = sorted(english[english.str.contains("fashio_")])
    suffix = sorted(english[english.str.contains(r"_\d$", regex=True)])
    same = int((translation["product_category_name"] == english).sum())
    has_bom = (DATA_DIR / TABLE_FILES["category_translation"]).read_bytes()[:3] == b"\xef\xbb\xbf"
    return issue(
        "Bảng dịch danh mục có lỗi chính tả, hậu tố khó hiểu và file có BOM",
        f"Lỗi chính tả: {', '.join(typo)}; hậu tố số: {', '.join(suffix)}; "
        f"{same:,} bản dịch giữ nguyên tên gốc; file có BOM UTF-8: {'Có' if has_bom else 'Không'}",
        "Tên danh mục hiển thị sai/khó đọc trên dashboard; đọc sai encoding làm cột đầu thành '\\ufeffproduct_category_name'",
        "Đọc bằng utf-8-sig ở Mage; thay bảng dịch bằng dbt seed đã sửa chính tả, thêm tên hiển thị (Title Case) "
        "và nhóm danh mục cho các hậu tố '_2'",
        "Staging / dbt (seed)",
    )


def check_seller_state(t: Tables) -> dict[str, str] | None:
    sellers = t["sellers"]
    geo_state = sellers["seller_zip_code_prefix"].map(zip_state_mode(t["geolocation"]))
    mismatch = sellers[geo_state.notna() & (sellers["seller_state"] != geo_state)]
    if mismatch.empty:
        return None
    return issue(
        "seller_state mâu thuẫn với bang suy ra từ mã bưu chính",
        f"{len(mismatch):,} seller có seller_state khác bang của zip trong geolocation "
        f"({int((mismatch['seller_state'] == 'SP').sum()):,} trường hợp ghi nhầm thành 'SP')",
        "Số seller và doanh thu theo bang bị dồn sai về SP",
        "Lấy lại bang từ zip qua geolocation; giữ seller_state_raw và cờ is_state_corrected",
        "dbt",
    )


def check_dirty_city_values(t: Tables) -> dict[str, str] | None:
    sellers = t["sellers"]["seller_city"].astype(str)
    with_state = int(sellers.str.contains(r"[/\\,]|\s-\s|-[a-z]{2}$", regex=True).sum())
    garbage = sorted(sellers[sellers.str.contains(r"@|\d", regex=True)].unique())
    geo_city = t["geolocation"]["geolocation_city"].astype(str)
    odd = geo_city[~geo_city.map(normalize_text).str.fullmatch(r"[a-z' -]+")]
    if not (with_state or garbage or len(odd)):
        return None
    return issue(
        "Tên thành phố chứa tên bang, giá trị rác hoặc lỗi mã hóa",
        f"seller_city: {with_state:,} dòng kèm tên bang (VD 'lages - sc', 'auriflama/sp'), "
        f"giá trị rác: {', '.join(repr(value) for value in garbage)}; "
        f"geolocation_city: {len(odd):,} dòng có ký tự lạ (VD 'sa£o paulo', '%26apos%3b')",
        "Không gom được theo thành phố; tên hiển thị sai trên dashboard và bản đồ",
        "Cắt phần tên bang sau '-', '/', ','; giá trị rác → NULL rồi lấy thành phố từ geolocation theo zip; "
        "sửa lỗi mã hóa bằng bảng ánh xạ",
        "dbt",
    )


def check_geolocation_spread(t: Tables) -> dict[str, str] | None:
    distance, spread = zip_spread_km(t["geolocation"])
    far_zips = int((spread > FAR_POINT_KM).sum())
    if not far_zips:
        return None
    return issue(
        "Tọa độ trong cùng một zip prefix phân tán xa nhau",
        f"{far_zips:,} zip có điểm cách điểm trung vị > {FAR_POINT_KM} km "
        f"({int((distance > FAR_POINT_KM).sum()):,} dòng); xa nhất {spread.max():,.0f} km",
        "Lấy trung bình lat/lng khi gom sẽ kéo điểm của zip ra sai vị trí trên bản đồ",
        "Gom theo trung vị (không dùng trung bình) sau khi loại tọa độ ngoài Brazil",
        "dbt",
    )


def check_zip_state_consistency(t: Tables) -> dict[str, str] | None:
    geo = t["geolocation"]
    zip_col = "geolocation_zip_code_prefix"
    multi_state = int((geo.groupby(zip_col)["geolocation_state"].nunique() > 1).sum())
    pairs = geo[[zip_col, "geolocation_state"]].drop_duplicates()
    out_of_range = int((cep_state(pairs[zip_col]) != pairs["geolocation_state"]).sum())
    if not (multi_state or out_of_range):
        return None
    return issue(
        "Một zip prefix gắn với nhiều bang hoặc bang trái dải mã bưu chính",
        f"{multi_state:,} zip gắn với > 1 bang; {out_of_range:,} cặp (zip, bang) nằm ngoài dải CEP của Correios "
        "(VD 01000–19999 là SP)",
        "Nối customers/sellers với geolocation theo zip có thể ra 2 bang; bản đồ theo bang bị lệch",
        "Lấy bang xuất hiện nhiều nhất của mỗi zip; dùng dải CEP làm quy tắc kiểm tra (dbt test)",
        "dbt",
    )


def check_approved_after_carrier(t: Tables) -> dict[str, str] | None:
    orders = t["orders"]
    gap = orders["order_approved_at"] - orders["order_delivered_carrier_date"]
    hours = gap[gap > pd.Timedelta(0)].dt.total_seconds() / 3600
    if hours.empty:
        return None
    return issue(
        "Đơn được giao cho vận chuyển trước khi được duyệt",
        f"{len(hours):,} đơn; lệch trung vị {hours.median():.0f} giờ, {int((hours < 24).sum()):,} đơn lệch < 24 giờ",
        "Thời gian duyệt / chuẩn bị hàng bị âm nếu tính theo order_approved_at",
        "Nhiều khả năng ghi nhận duyệt trễ: gắn cờ is_approved_after_carrier, không loại khỏi KPI giao hàng "
        "(mua → khách nhận); không dùng order_approved_at để tính thời gian chuẩn bị hàng cho các đơn này",
        "dbt",
    )


def check_date_only_columns(t: Tables) -> dict[str, str] | None:
    details = []
    for table, column in [("orders", "order_estimated_delivery_date"), ("order_reviews", "review_creation_date")]:
        values = t[table][column].dropna()
        midnight = int((values == values.dt.normalize()).sum())
        details.append(f"{column}: {midnight:,}/{len(values):,} giá trị có giờ 00:00:00")
    return issue(
        "Một số cột thời gian thực chất chỉ chứa ngày",
        "; ".join(details),
        "So sánh trễ hạn theo giờ sẽ tính sai (giao lúc 10h ngày dự kiến bị coi là trễ)",
        "Ép về DATE ở dbt; is_late so sánh theo ngày: "
        "CAST(order_delivered_customer_date AS DATE) > order_estimated_delivery_date",
        "dbt",
    )


def check_payment_sequence(t: Tables) -> dict[str, str] | None:
    per_order = t["order_payments"].groupby("order_id")["payment_sequential"].agg(["max", "count"])
    gaps = int((per_order["max"] != per_order["count"]).sum())
    if not gaps:
        return None
    return issue(
        "payment_sequential không liên tục trong một đơn",
        f"{gaps:,} đơn có số thứ tự thanh toán lớn nhất khác số dòng thanh toán; "
        f"tối đa {per_order['count'].max():,} dòng thanh toán / đơn",
        "Đếm số lần thanh toán theo payment_sequential bị sai",
        "Chỉ dùng payment_sequential làm khóa ghép; đếm số lần thanh toán bằng COUNT(*)",
        "dbt",
    )


def check_customer_address_changes(t: Tables) -> dict[str, str] | None:
    columns = ["customer_zip_code_prefix", "customer_city", "customer_state"]
    changed = t["customers"].groupby("customer_unique_id")[columns].nunique().gt(1).any(axis=1)
    if not changed.any():
        return None
    return issue(
        "Cùng một khách hàng có nhiều địa chỉ giữa các đơn",
        f"{int(changed.sum()):,} customer_unique_id có > 1 zip/city/state",
        "Dim_Customer theo customer_unique_id không có một địa chỉ duy nhất; phân tích địa lý theo khách bị mơ hồ",
        "Dim_Customer lấy địa chỉ của đơn gần nhất; phân tích địa lý dùng địa chỉ gắn với từng đơn (customer_id)",
        "dbt",
    )


def check_item_quantity(t: Tables) -> dict[str, str] | None:
    items = t["order_items"]
    repeated = items.groupby(["order_id", "product_id"]).size()
    if not (repeated > 1).any():
        return None
    multi_seller = int((items.groupby("order_id")["seller_id"].nunique() > 1).sum())
    return issue(
        "order_items không có cột số lượng; mỗi đơn vị sản phẩm là một dòng",
        f"{int((repeated > 1).sum()):,} cặp (đơn, sản phẩm) lặp > 1 dòng (tối đa {repeated.max():,}); "
        f"{multi_seller:,} đơn có hàng của > 1 seller",
        "Hiểu nhầm mỗi dòng là 1 loại sản phẩm sẽ đếm sai số lượng bán; freight_value không phải phí theo đơn",
        "Giữ grain Fact = 1 dòng order_items; số lượng = COUNT(*); phí ship cộng theo dòng",
        "dbt / Power BI",
    )


def check_non_revenue_items(t: Tables) -> dict[str, str] | None:
    items = t["order_items"].merge(t["orders"][["order_id", "order_status"]], on="order_id")
    non_revenue = items[items["order_status"].isin(NON_REVENUE_STATUSES)]
    if non_revenue.empty:
        return None
    return issue(
        "Dòng bán hàng thuộc đơn đã hủy / không khả dụng",
        f"{len(non_revenue):,} dòng order_items thuộc đơn canceled/unavailable, "
        f"{non_revenue['price'].sum():,.2f} BRL ({non_revenue['price'].sum() / items['price'].sum():.2%} tổng price)",
        "Doanh thu bị thổi phồng nếu cộng tất cả dòng order_items",
        "Giữ trong Fact kèm order_status; measure doanh thu lọc bỏ canceled/unavailable",
        "dbt / Power BI",
    )


def check_review_timing(t: Tables) -> dict[str, str] | None:
    merged = t["order_reviews"].merge(t["orders"], on="order_id")
    created = merged["review_creation_date"]
    before_purchase = created < merged["order_purchase_timestamp"].dt.normalize()
    before_delivery = created < merged["order_delivered_customer_date"].dt.normalize()
    if not (before_purchase.any() or before_delivery.any()):
        return None
    return issue(
        "Đánh giá được tạo trước ngày mua hoặc trước khi khách nhận hàng",
        f"{int(before_purchase.sum()):,} review tạo trước ngày mua; {int(before_delivery.sum()):,} review tạo trước "
        f"ngày nhận hàng, điểm TB {merged.loc[before_delivery, 'review_score'].mean():.2f} "
        f"(so với {merged['review_score'].mean():.2f} toàn bộ)",
        "Thời gian từ giao hàng → đánh giá bị âm; điểm thấp phản ánh giao chậm chứ không phải chất lượng sản phẩm",
        "Gắn cờ is_review_before_purchase / is_review_before_delivery; giữ lại làm bằng chứng giao trễ ↔ điểm thấp",
        "dbt / Power BI",
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
    check_product_dimensions,
    check_category_translation,
    check_seller_state,
    check_dirty_city_values,
    check_geolocation_spread,
    check_zip_state_consistency,
    check_approved_after_carrier,
    check_date_only_columns,
    check_payment_sequence,
    check_customer_address_changes,
    check_item_quantity,
    check_non_revenue_items,
    check_review_timing,
]


def build() -> pd.DataFrame:
    tables = load_tables()
    issues = [result for check in ISSUE_CHECKS if (result := check(tables))]
    table = pd.DataFrame(issues)
    table.insert(0, "STT", range(1, len(table) + 1))
    return table


def main() -> None:
    setup_console()
    issues = build()
    print(issues[["STT", "Vấn đề phát hiện"]].to_string(index=False))
    save_csv(issues, "Bang_Van_De_Du_Lieu.csv")


if __name__ == "__main__":
    main()
