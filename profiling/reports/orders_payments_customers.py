"""Báo cáo chi tiết: olist_orders, olist_order_payments, olist_customers.

Kết quả: output/dataProfiling/Profiling_Orders_Payments_Customers.md
"""
import pandas as pd

from profiling.common import (
    BRAZIL_STATES,
    ORDER_TIME_COLUMNS,
    cep_state,
    invalid_timeline,
    load_tables,
    normalize_text,
    pct,
    setup_console,
    zip_state_mode,
)
from profiling.reports.markdown import basic_facts, column_overview, count_table, md_table, null_pattern, run_report


# Tháng có số đơn < tỷ lệ này so với trung vị thì coi là tháng thiếu dữ liệu.
SPARSE_MONTH_RATIO = 0.1

# Chênh lệch (BRL) giữa tổng thanh toán và price + freight được coi là làm tròn.
PAYMENT_TOLERANCE = 1


def profile_orders(data: dict[str, pd.DataFrame]) -> tuple[list[str], list[str]]:
    orders = data["orders"]
    total = len(orders)
    lines, issues = [], []

    lines.append("## 1. olist_orders_dataset\n")
    lines.extend(basic_facts(orders, ["order_id"]))
    lines.append("- Mỗi dòng = 1 đơn hàng; 5 cột thời gian đều đúng định dạng `YYYY-MM-DD HH:MM:SS`\n")
    lines.append("### 1.1 Thống kê theo cột\n")
    lines.append(md_table(column_overview(orders)) + "\n")

    lines.append("### 1.2 Phân bố order_status\n")
    lines.append(count_table(orders["order_status"], "order_status") + "\n")

    # Missing: NULL ở các cột thời gian phụ thuộc vào trạng thái đơn (MAR).
    lines.append("### 1.3 Giá trị thiếu theo trạng thái đơn (kiểm tra MAR)\n")
    lines.append(md_table(null_pattern(orders, ORDER_TIME_COLUMNS)) + "\n")
    by_status = (
        orders[ORDER_TIME_COLUMNS[1:4]].isna().groupby(orders["order_status"]).sum()
        .join(orders["order_status"].value_counts().rename("Số đơn"))
        .reset_index()
        .sort_values("Số đơn", ascending=False)
    )
    lines.append("Số dòng NULL theo từng trạng thái:\n")
    lines.append(md_table(by_status) + "\n")
    lines.append(
        "- NULL tập trung ở các trạng thái chưa giao (canceled, unavailable, shipped, invoiced...) "
        "→ **MAR**, đúng nghiệp vụ, **không điền giá trị**\n"
    )

    # Mâu thuẫn trạng thái ↔ ngày.
    lines.append("### 1.4 Mâu thuẫn giữa trạng thái và ngày giao\n")
    delivered = orders["order_status"] == "delivered"
    has_delivery = orders["order_delivered_customer_date"].notna()
    checks = [
        ["delivered nhưng thiếu order_delivered_customer_date", int((delivered & ~has_delivery).sum())],
        ["delivered nhưng thiếu order_delivered_carrier_date",
         int((delivered & orders["order_delivered_carrier_date"].isna()).sum())],
        ["delivered nhưng thiếu order_approved_at", int((delivered & orders["order_approved_at"].isna()).sum())],
        ["Chưa delivered nhưng có order_delivered_customer_date", int((~delivered & has_delivery).sum())],
        ["canceled nhưng đã giao tới khách",
         int(((orders["order_status"] == "canceled") & has_delivery).sum())],
    ]
    lines.append(md_table(pd.DataFrame(checks, columns=["Kiểm tra", "Số đơn"])) + "\n")
    issues.append(
        f"orders: {checks[0][1]} đơn 'delivered' thiếu ngày giao, {checks[3][1]} đơn chưa 'delivered' "
        "nhưng có ngày giao → gắn cờ is_status_conflict; KPI giao hàng chỉ tính đơn delivered có đủ ngày"
    )

    # Thứ tự các mốc thời gian.
    lines.append("### 1.5 Thứ tự các mốc thời gian\n")
    purchase, approved, carrier, customer, estimated = (orders[c] for c in ORDER_TIME_COLUMNS)
    sequence = [
        ["order_approved_at < order_purchase_timestamp", approved < purchase],
        ["order_delivered_carrier_date < order_purchase_timestamp", carrier < purchase],
        ["order_delivered_carrier_date < order_approved_at", carrier < approved],
        ["order_delivered_customer_date < order_delivered_carrier_date", customer < carrier],
        ["order_delivered_customer_date < order_purchase_timestamp", customer < purchase],
        ["order_estimated_delivery_date < order_purchase_timestamp", estimated < purchase],
    ]
    lines.append(
        md_table(pd.DataFrame([[name, int(mask.sum())] for name, mask in sequence], columns=["Vi phạm", "Số đơn"]))
        + "\n"
    )
    # Giao vận chuyển trước khi duyệt thường chỉ lệch vài giờ (ghi nhận duyệt trễ) nên tách riêng,
    # không coi là timeline sai.
    bad_timeline = invalid_timeline(orders)
    approval_gap = (approved - carrier).dt.total_seconds()[sequence[2][1]] / 3600
    lines.append(
        f"- Giao vận chuyển trước khi duyệt: lệch median {approval_gap.median():.0f} giờ, "
        f"{int((approval_gap < 24).sum()):,}/{len(approval_gap):,} đơn lệch < 24 giờ → nhiều khả năng ghi nhận duyệt trễ, "
        "chỉ gắn cờ, vẫn dùng được để tính thời gian giao (mua → khách nhận)"
    )
    lines.append(
        f"- Timeline sai thật (giao vận chuyển trước khi mua, khách nhận trước khi giao vận chuyển/mua): "
        f"{int(bad_timeline.sum())} đơn\n"
    )
    issues.append(
        f"orders: {int(bad_timeline.sum())} đơn có mốc thời gian ngược (giao vận chuyển trước khi mua, "
        "khách nhận trước khi giao vận chuyển) → gắn cờ is_invalid_timeline, loại khỏi phép tính thời gian giao"
    )
    issues.append(
        f"orders: {len(approval_gap):,} đơn giao vận chuyển trước khi duyệt (median lệch {approval_gap.median():.0f} giờ) → "
        "gắn cờ is_approved_after_carrier, không loại khỏi KPI giao hàng"
    )

    # Chỉ số giao hàng trên các đơn hợp lệ.
    lines.append("### 1.6 Thời gian xử lý & giao hàng (đơn delivered, đủ ngày, timeline hợp lệ)\n")
    valid = delivered & has_delivery & ~bad_timeline
    delivery_days = (customer - purchase).dt.total_seconds()[valid] / 86400
    approval_hours = (approved - purchase).dt.total_seconds()[valid] / 3600
    late = (customer.dt.normalize() > estimated)[valid]
    estimated_has_time = int((estimated.dt.time.astype(str) != "00:00:00").sum())
    lines.append(f"- Số đơn dùng để tính: {int(valid.sum()):,}/{total:,}")
    lines.append(
        f"- Số ngày giao (mua → khách nhận): median {delivery_days.median():.1f}, mean {delivery_days.mean():.1f}, "
        f"P99 {delivery_days.quantile(0.99):.0f}, max {delivery_days.max():.0f}; "
        f"{int((delivery_days > 60).sum())} đơn > 60 ngày"
    )
    lines.append(
        f"- Thời gian duyệt (mua → duyệt): median {approval_hours.median():.2f} giờ, "
        f"P99 {approval_hours.quantile(0.99):.0f} giờ, max {approval_hours.max() / 24:.0f} ngày"
    )
    lines.append(f"- Giao trễ so với ngày dự kiến: {int(late.sum()):,} đơn ({pct(int(late.sum()), int(valid.sum()))})")
    lines.append(
        f"- order_estimated_delivery_date luôn là 00:00:00 ({estimated_has_time} giá trị có giờ khác 0) → "
        "chỉ là ngày, so sánh trễ hạn phải theo ngày (không theo giờ)\n"
    )
    issues.append(
        f"orders: thời gian giao lệch phải (median {delivery_days.median():.0f} ngày, max {delivery_days.max():.0f}) → "
        "dùng median trên dashboard; is_late so theo ngày vì order_estimated_delivery_date không có giờ"
    )

    # Độ đầy đủ theo tháng.
    lines.append("### 1.7 Số đơn theo tháng\n")
    per_month = purchase.dt.to_period("M").value_counts().sort_index()
    sparse = per_month[per_month < per_month.median() * SPARSE_MONTH_RATIO]
    lines.append(
        f"- Từ {purchase.min()} đến {purchase.max()}; {per_month.size} tháng; "
        f"trung vị {per_month.median():,.0f} đơn/tháng"
    )
    lines.append(
        f"- Tháng có < {SPARSE_MONTH_RATIO:.0%} trung vị: "
        + ", ".join(f"{month}: {count}" for month, count in sparse.items())
    )
    missing_months = pd.period_range(per_month.index.min(), per_month.index.max(), freq="M").difference(per_month.index)
    lines.append(f"- Tháng không có đơn nào: {', '.join(map(str, missing_months)) or 'không có'}\n")
    lines.append(md_table(per_month.rename_axis("Tháng").reset_index(name="Số đơn")) + "\n")
    issues.append(
        f"orders: {sparse.size} tháng đầu/cuối kỳ gần như không có dữ liệu ({', '.join(map(str, sparse.index))}) → "
        "giới hạn phạm vi so sánh theo tháng/YoY (VD 2017-01 → 2018-08)"
    )

    # Toàn vẹn tham chiếu.
    lines.append("### 1.8 Toàn vẹn tham chiếu\n")
    customers = data["customers"]
    orders_per_customer = orders["customer_id"].value_counts()
    rows = []
    for name, child in (("order_items", data["order_items"]), ("payments", data["order_payments"]), ("reviews", data["order_reviews"])):
        absent = orders[~orders["order_id"].isin(child["order_id"])]
        rows.append([
            name, len(absent),
            "; ".join(f"{status}: {count}" for status, count in absent["order_status"].value_counts().items()),
        ])
    lines.append(
        f"- customer_id trong orders không có trong customers: "
        f"{int((~orders['customer_id'].isin(customers['customer_id'])).sum())}; "
        f"tối đa {orders_per_customer.max()} đơn / customer_id → quan hệ 1–1"
    )
    lines.append("- Đơn hàng không có dòng ở bảng con:\n")
    lines.append(md_table(pd.DataFrame(rows, columns=["Bảng con", "Số đơn", "Theo trạng thái"])) + "\n")
    issues.append(
        f"orders: {rows[0][1]} đơn không có order_items, {rows[1][1]} đơn không có payments, "
        f"{rows[2][1]} đơn không có review → Fact bán hàng lấy grain từ order_items; giải thích chênh lệch số đơn"
    )
    return lines, issues


def profile_payments(data: dict[str, pd.DataFrame]) -> tuple[list[str], list[str]]:
    payments = data["order_payments"]
    orders = data["orders"]
    total = len(payments)
    lines, issues = [], []

    lines.append("## 2. olist_order_payments_dataset\n")
    lines.extend(basic_facts(payments, ["order_id", "payment_sequential"]))
    lines.append("- Mỗi dòng = 1 lần thanh toán của 1 đơn (1 đơn có thể trả bằng nhiều phương thức/voucher)\n")
    lines.append("### 2.1 Thống kê theo cột\n")
    lines.append(md_table(column_overview(payments)) + "\n")

    lines.append("### 2.2 Phương thức thanh toán\n")
    by_type = payments.groupby("payment_type").agg(
        **{
            "Số dòng": ("order_id", "size"),
            "Giá trị TB": ("payment_value", "mean"),
            "Trả góp > 1 kỳ": ("payment_installments", lambda s: int((s > 1).sum())),
            "Số kỳ max": ("payment_installments", "max"),
            "payment_value = 0": ("payment_value", lambda s: int((s == 0).sum())),
        }
    ).sort_values("Số dòng", ascending=False)
    by_type["Giá trị TB"] = by_type["Giá trị TB"].round(2)
    lines.append(md_table(by_type.reset_index()) + "\n")
    not_defined = payments[payments["payment_type"] == "not_defined"]
    not_defined_status = orders.loc[orders["order_id"].isin(not_defined["order_id"]), "order_status"].value_counts()
    lines.append(
        f"- {len(not_defined)} dòng payment_type = 'not_defined', đều thuộc đơn: "
        + ", ".join(f"{status} ({count})" for status, count in not_defined_status.items())
    )
    lines.append("- Chỉ credit_card có trả góp > 1 kỳ → hợp lý về nghiệp vụ\n")

    lines.append("### 2.3 Giá trị bất thường\n")
    zero_installments = payments[payments["payment_installments"] == 0]
    zero_value = payments[payments["payment_value"] == 0]
    lines.append(
        f"- payment_installments = 0: {len(zero_installments)} dòng (loại: "
        f"{', '.join(zero_installments['payment_type'].unique())}) → tối thiểu phải là 1"
    )
    lines.append(
        f"- payment_value = 0: {len(zero_value)} dòng (loại: "
        + ", ".join(f"{t} {c}" for t, c in zero_value["payment_type"].value_counts().items())
        + ")"
    )
    lines.append(
        f"- payment_value: median {payments['payment_value'].median():.2f}, "
        f"P99 {payments['payment_value'].quantile(0.99):,.2f}, max {payments['payment_value'].max():,.2f} "
        f"→ lệch phải (skew {payments['payment_value'].skew():.1f})\n"
    )
    issues.append(
        f"payments: {len(zero_installments)} dòng installments = 0, {len(zero_value)} dòng payment_value = 0, "
        f"{len(not_defined)} dòng 'not_defined' (đơn canceled) → installments 0 → 1; gắn cờ, giữ nguyên dòng"
    )

    lines.append("### 2.4 Cấu trúc nhiều lần thanh toán\n")
    per_order = payments.groupby("order_id").agg(
        count=("payment_sequential", "size"),
        max_seq=("payment_sequential", "max"),
        types=("payment_type", "nunique"),
    )
    gap = per_order[per_order["max_seq"] != per_order["count"]]
    combos = (
        payments.groupby("order_id")["payment_type"]
        .agg(lambda s: " + ".join(sorted(s.unique())))
        .loc[lambda s: s.str.contains(r"\+")]
        .value_counts()
    )
    lines.append(
        f"- {int((per_order['count'] > 1).sum()):,} đơn có > 1 dòng thanh toán (tối đa {per_order['count'].max()}); "
        f"{int((per_order['types'] > 1).sum()):,} đơn dùng > 1 phương thức"
    )
    lines.append(
        f"- {len(gap)} đơn có payment_sequential không liên tục (số lớn nhất ≠ số dòng) → thiếu dòng thanh toán"
    )
    lines.append("- Tổ hợp phương thức: " + "; ".join(f"{combo}: {count}" for combo, count in combos.items()) + "\n")

    lines.append("### 2.5 Đối chiếu với giá trị đơn hàng (order_items)\n")
    items = data["order_items"]
    item_total = items.assign(total=items["price"] + items["freight_value"]).groupby("order_id")["total"].sum()
    paid = payments.groupby("order_id")["payment_value"].sum()
    compare = pd.concat([paid.rename("paid"), item_total.rename("items")], axis=1, join="inner")
    compare["diff"] = compare["paid"] - compare["items"]
    mismatch = compare[compare["diff"].abs() > PAYMENT_TOLERANCE]
    no_items = paid.index.difference(item_total.index)
    no_payment = orders.loc[~orders["order_id"].isin(payments["order_id"]), ["order_id", "order_status"]]
    lines.append(
        f"- {len(mismatch):,}/{len(compare):,} đơn lệch > {PAYMENT_TOLERANCE} BRL giữa tổng thanh toán và "
        f"price + freight ({int((mismatch['diff'] > 0).sum())} trả nhiều hơn, {int((mismatch['diff'] < 0).sum())} trả ít hơn); "
        f"lệch lớn nhất {mismatch['diff'].abs().max():,.2f} BRL"
    )
    lines.append(f"- {len(no_items)} đơn có thanh toán nhưng không có order_items")
    lines.append(
        f"- {len(no_payment)} đơn không có thanh toán: "
        + ", ".join(f"{row.order_id} ({row.order_status})" for row in no_payment.itertuples())
        + "\n"
    )
    issues.append(
        f"payments: {len(mismatch)} đơn có tổng thanh toán lệch price + freight (có thể do lãi trả góp, voucher) → "
        "doanh thu lấy từ order_items; payments chỉ dùng cho phân tích phương thức thanh toán"
    )
    issues.append(
        f"payments: {len(gap)} đơn có payment_sequential bị đứt quãng → chỉ ghi nhận, không dùng sequential làm số lần trả"
    )
    return lines, issues


def profile_customers(data: dict[str, pd.DataFrame]) -> tuple[list[str], list[str]]:
    customers = data["customers"]
    orders = data["orders"]
    geo = data["geolocation"]
    total = len(customers)
    lines, issues = [], []

    lines.append("## 3. olist_customers_dataset\n")
    lines.extend(basic_facts(customers, ["customer_id"]))
    valid_zip = int(customers["customer_zip_code_prefix"].str.fullmatch(r"\d{5}").sum())
    lines.append(
        f"- Mỗi dòng = 1 customer_id gắn với **1 đơn hàng**; zip đúng 5 chữ số: {valid_zip:,}/{total:,}; "
        f"zip bắt đầu bằng 0: {customers['customer_zip_code_prefix'].str.startswith('0').sum():,}\n"
    )
    lines.append("### 3.1 Thống kê theo cột\n")
    lines.append(md_table(column_overview(customers)) + "\n")

    lines.append("### 3.2 customer_id và customer_unique_id\n")
    ids_per_person = customers.groupby("customer_unique_id")["customer_id"].nunique()
    repeat = ids_per_person[ids_per_person > 1]
    profile_columns = ["customer_zip_code_prefix", "customer_city", "customer_state"]
    changed = customers.groupby("customer_unique_id")[profile_columns].nunique()
    changed = changed[changed.gt(1).any(axis=1)]
    lines.append(
        f"- {total:,} customer_id nhưng chỉ {ids_per_person.size:,} customer_unique_id → "
        "customer_id được sinh mới cho mỗi đơn"
    )
    lines.append(
        f"- {repeat.size:,} khách ({pct(repeat.size, ids_per_person.size)}) mua > 1 lần, tối đa {repeat.max()} đơn → "
        "tỷ lệ khách quay lại rất thấp"
    )
    lines.append(
        f"- {len(changed):,} khách có > 1 địa chỉ (zip/city/state) giữa các đơn → "
        "Dim_Customer cần chọn địa chỉ (VD địa chỉ của đơn gần nhất) hoặc để địa chỉ ở cấp đơn hàng\n"
    )
    issues.append(
        f"customers: {total:,} customer_id / {ids_per_person.size:,} customer_unique_id; {repeat.size:,} khách mua > 1 lần → "
        "khóa tự nhiên Dim_Customer = customer_unique_id; đếm khách bằng DISTINCT customer_unique_id"
    )
    issues.append(
        f"customers: {len(changed):,} khách đổi địa chỉ giữa các đơn → lấy địa chỉ của đơn gần nhất cho Dim_Customer, "
        "phân tích địa lý theo địa chỉ ở từng đơn"
    )

    lines.append("### 3.3 Chất lượng địa chỉ\n")
    customers["city_normalized"] = customers["customer_city"].map(normalize_text)
    odd_city = customers.loc[~customers["customer_city"].str.fullmatch(r"[a-z' -]+"), "customer_city"]
    invalid_state = sorted(set(customers["customer_state"]) - BRAZIL_STATES)
    customers["cep_state"] = cep_state(customers["customer_zip_code_prefix"])
    cep_mismatch = customers[customers["cep_state"] != customers["customer_state"]]
    customers["geo_state"] = customers["customer_zip_code_prefix"].map(zip_state_mode(geo))
    geo_mismatch = customers[customers["geo_state"].notna() & (customers["geo_state"] != customers["customer_state"])]
    no_geo = customers[customers["geo_state"].isna()]
    lines.append(
        f"- customer_city: {customers['customer_city'].nunique():,} giá trị gốc → "
        f"{customers['city_normalized'].nunique():,} sau chuẩn hóa; {len(odd_city)} dòng có ký tự ngoài [a-z' -]"
        + (f", VD: {', '.join(repr(c) for c in odd_city.drop_duplicates().head(5))}" if len(odd_city) else "")
    )
    lines.append(f"- customer_state: {customers['customer_state'].nunique()} bang; mã không hợp lệ: {invalid_state or 'không có'}")
    lines.append(f"- {len(cep_mismatch)} khách có customer_state khác bang suy ra từ dải CEP")
    lines.append(f"- {len(geo_mismatch)} khách có customer_state khác bang của zip trong geolocation")
    lines.append(
        f"- {len(no_geo)} khách ({no_geo['customer_zip_code_prefix'].nunique()} zip) không có zip trong geolocation "
        "→ không có tọa độ\n"
    )
    issues.append(
        f"customers: {len(no_geo)} khách có zip không có tọa độ, {len(cep_mismatch)} khách có bang trái dải CEP → "
        "LEFT JOIN geolocation; phân tích địa lý ưu tiên theo customer_state"
    )

    lines.append("### 3.4 Phân bố theo bang\n")
    lines.append(count_table(customers["customer_state"], "customer_state") + "\n")
    state_counts = customers["customer_state"].value_counts()
    lines.append(
        f"- Top 3 bang (SP, RJ, MG) chiếm {pct(int(state_counts.head(3).sum()), total)}; "
        f"{int((state_counts < 500).sum())} bang có < 500 khách\n"
    )
    lines.append(
        f"- Liên kết: {int(orders['customer_id'].isin(customers['customer_id']).sum()):,}/{len(orders):,} đơn "
        f"nối được với customers; {int((~customers['customer_id'].isin(orders['customer_id'])).sum())} customer không có đơn\n"
    )
    return lines, issues


def main() -> None:
    setup_console()
    run_report(
        "Profiling_Orders_Payments_Customers.md",
        "Data profiling: orders, order_payments, customers",
        [profile_orders, profile_payments, profile_customers],
        load_tables("orders", "order_payments", "customers", "order_items", "order_reviews", "geolocation"),
    )


if __name__ == "__main__":
    main()
