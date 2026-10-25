"""Báo cáo chi tiết: olist_order_items, olist_order_reviews.

Kết quả: output/dataProfiling/Profiling_OrderItems_Reviews.md
"""
import pandas as pd

from profiling.common import NON_REVENUE_STATUSES, iqr_bounds, load_tables, pct, setup_console
from profiling.reports.markdown import basic_facts, column_overview, count_table, md_table, null_pattern, run_report


# shipping_limit_date cách ngày mua quá số ngày này thì coi là bất thường.
SHIPPING_LIMIT_MAX_DAYS = 60


def profile_order_items(data: dict[str, pd.DataFrame]) -> tuple[list[str], list[str]]:
    items = data["order_items"]
    orders = data["orders"]
    total = len(items)
    lines, issues = [], []

    lines.append("## 1. olist_order_items_dataset\n")
    lines.extend(basic_facts(items, ["order_id", "order_item_id"]))
    lines.append(
        "- Mỗi dòng = 1 đơn vị sản phẩm trong 1 đơn; mua 2 cái cùng sản phẩm → 2 dòng "
        "(không có cột quantity) → **grain của Fact bán hàng**\n"
    )
    lines.append("### 1.1 Thống kê theo cột\n")
    lines.append(md_table(column_overview(items)) + "\n")

    lines.append("### 1.2 Cấu trúc đơn hàng\n")
    per_order = items.groupby("order_id").agg(
        rows=("order_item_id", "size"),
        max_item=("order_item_id", "max"),
        products=("product_id", "nunique"),
        sellers=("seller_id", "nunique"),
    )
    same_product = items.groupby(["order_id", "product_id"]).size()
    lines.append(
        f"- {len(per_order):,} đơn; số dòng/đơn: median {per_order['rows'].median():.0f}, max {per_order['rows'].max()}; "
        f"{int((per_order['rows'] > 1).sum()):,} đơn có > 1 dòng"
    )
    lines.append(
        f"- order_item_id liên tục 1..n trong mọi đơn: "
        f"{'Có' if (per_order['max_item'] == per_order['rows']).all() else 'Không'}"
    )
    lines.append(
        f"- {int((same_product > 1).sum()):,} cặp (đơn, sản phẩm) lặp > 1 dòng (tối đa {same_product.max()}) → "
        "số lượng = COUNT(*) theo order_id + product_id"
    )
    lines.append(
        f"- {int((per_order['sellers'] > 1).sum()):,} đơn có hàng của > 1 seller → "
        "freight_value tính theo từng dòng, không phải theo đơn\n"
    )

    lines.append("### 1.3 price & freight_value\n")
    rows = []
    for column in ("price", "freight_value"):
        series = items[column]
        low, high = iqr_bounds(series)
        rows.append([
            column, f"{series.median():,.2f}", f"{series.mean():,.2f}", f"{series.max():,.2f}",
            f"{high:,.2f}", f"{int((series > high).sum()):,} ({pct(int((series > high).sum()), total)})",
            int((series == 0).sum()), int((series < 0).sum()),
        ])
    lines.append(
        md_table(
            pd.DataFrame(
                rows,
                columns=["Cột", "Median", "Mean", "Max", "Ngưỡng trên IQR", "Vượt ngưỡng", "= 0", "< 0"],
            )
        )
        + "\n"
    )
    freight_over_price = int((items["freight_value"] > items["price"]).sum())
    lines.append(f"- {freight_over_price:,} dòng ({pct(freight_over_price, total)}) có phí ship > giá sản phẩm (hàng rẻ, nặng)")

    # IQR theo danh mục: giá cao ở danh mục đắt tiền là bình thường.
    categories = data["products"][["product_id", "product_category_name"]]
    with_category = items.merge(categories, on="product_id", how="left")
    category_high = with_category.groupby("product_category_name")["price"].transform(lambda s: iqr_bounds(s)[1])
    category_outliers = int((with_category["price"] > category_high).sum())
    top = items.nlargest(5, "price").merge(categories, on="product_id", how="left")
    lines.append(
        f"- Ngoại lai price theo IQR **trong từng danh mục**: {category_outliers:,} dòng "
        f"(so với {rows[0][5]} khi tính trên toàn bảng)"
    )
    lines.append(
        "- 5 dòng giá cao nhất: "
        + "; ".join(f"{row.price:,.2f} ({row.product_category_name})" for row in top.itertuples())
        + "\n"
    )
    issues.append(
        f"order_items: price/freight lệch phải mạnh (price median {rows[0][1]}, max {rows[0][3]}); "
        f"{rows[1][6]} dòng freight = 0 → giữ (giao dịch thật), dùng median và phân khoảng giá; "
        "phát hiện ngoại lai theo từng danh mục"
    )

    lines.append("### 1.4 shipping_limit_date\n")
    merged = items.merge(
        orders[["order_id", "order_purchase_timestamp", "order_status"]], on="order_id", how="left"
    )
    lag_days = (merged["shipping_limit_date"] - merged["order_purchase_timestamp"]).dt.days
    far = merged[lag_days > SHIPPING_LIMIT_MAX_DAYS]
    lines.append(
        f"- Từ {items['shipping_limit_date'].min()} đến {items['shipping_limit_date'].max()}; "
        f"số ngày sau khi mua: median {lag_days.median():.0f}, max {lag_days.max():,}"
    )
    lines.append(f"- {int((lag_days < 0).sum())} dòng có hạn giao trước ngày mua")
    lines.append(
        f"- {len(far)} dòng hạn giao > {SHIPPING_LIMIT_MAX_DAYS} ngày sau khi mua: "
        + "; ".join(f"{row.shipping_limit_date} ({row.order_status})" for row in far.head(5).itertuples())
        + "\n"
    )
    issues.append(
        f"order_items: {len(far)} dòng shipping_limit_date > {SHIPPING_LIMIT_MAX_DAYS} ngày sau khi mua "
        f"(max {items['shipping_limit_date'].max().date()}) → gắn cờ; Dim_Date sinh theo min/max thực tế"
    )

    lines.append("### 1.5 Trạng thái đơn của các dòng bán hàng\n")
    lines.append(count_table(merged["order_status"], "order_status") + "\n")
    non_revenue = merged[merged["order_status"].isin(NON_REVENUE_STATUSES)]
    lines.append(
        f"- {len(non_revenue):,} dòng thuộc đơn {'/'.join(NON_REVENUE_STATUSES)}, "
        f"giá trị {non_revenue['price'].sum():,.2f} BRL ({non_revenue['price'].sum() / items['price'].sum():.2%} tổng price)\n"
    )
    issues.append(
        f"order_items: {len(non_revenue):,} dòng thuộc đơn canceled/unavailable → giữ trong Fact, mang order_status; "
        "measure doanh thu trên Power BI lọc bỏ các trạng thái này"
    )

    lines.append("### 1.6 Toàn vẹn tham chiếu\n")
    checks = [
        ["order_id không có trong orders", int((~items["order_id"].isin(orders["order_id"])).sum())],
        ["product_id không có trong products", int((~items["product_id"].isin(data["products"]["product_id"])).sum())],
        ["seller_id không có trong sellers", int((~items["seller_id"].isin(data["sellers"]["seller_id"])).sum())],
        ["Sản phẩm thiếu danh mục (dòng)", int(with_category["product_category_name"].isna().sum())],
    ]
    lines.append(md_table(pd.DataFrame(checks, columns=["Kiểm tra", "Số dòng"])) + "\n")
    return lines, issues


def profile_reviews(data: dict[str, pd.DataFrame]) -> tuple[list[str], list[str]]:
    reviews = data["order_reviews"]
    orders = data["orders"]
    total = len(reviews)
    lines, issues = [], []

    lines.append("## 2. olist_order_reviews_dataset\n")
    lines.extend(basic_facts(reviews, ["review_id"]))
    lines.append(
        f"- Trùng khóa (review_id + order_id): {reviews.duplicated(subset=['review_id', 'order_id']).sum()} → "
        "khóa đúng của bảng là cặp này\n"
    )
    lines.append("### 2.1 Thống kê theo cột\n")
    lines.append(md_table(column_overview(reviews)) + "\n")

    lines.append("### 2.2 Trùng lặp\n")
    shared = reviews[reviews["review_id"].duplicated(keep=False)]
    same_content = shared.groupby("review_id")[
        ["review_score", "review_comment_message", "review_creation_date"]
    ].nunique(dropna=False).max(axis=1).eq(1)
    reviews_per_order = reviews.groupby("order_id")["review_id"].nunique()
    multi = reviews[reviews["order_id"].isin(reviews_per_order[reviews_per_order > 1].index)]
    score_changes = multi.groupby("order_id")["review_score"].nunique().gt(1).sum()
    lines.append(
        f"- {len(shared):,} dòng dùng chung {shared['review_id'].nunique():,} review_id cho nhiều đơn; "
        f"{int(same_content.sum())}/{same_content.size} review_id có nội dung giống hệt nhau giữa các đơn → "
        "1 lần đánh giá áp cho nhiều đơn (khách mua nhiều đơn cùng lúc)"
    )
    lines.append(
        f"- {int((reviews_per_order > 1).sum()):,} đơn có > 1 review (tối đa {reviews_per_order.max()}); "
        f"{score_changes} đơn trong số đó có điểm khác nhau giữa các review\n"
    )
    issues.append(
        f"reviews: review_id không duy nhất ({len(shared):,} dòng), {int((reviews_per_order > 1).sum())} đơn có > 1 review → "
        "khóa staging = review_id + order_id; dbt giữ review mới nhất (review_answer_timestamp) cho mỗi đơn"
    )

    lines.append("### 2.3 review_score\n")
    lines.append(count_table(reviews["review_score"], "review_score", sort_by_value=True) + "\n")
    lines.append(
        f"- Mean {reviews['review_score'].mean():.2f}, median {reviews['review_score'].median():.0f}; "
        "lệch về 5 điểm (J-shape) → báo cáo thêm tỷ lệ 1–2 điểm, không chỉ điểm trung bình\n"
    )

    lines.append("### 2.4 Bình luận (MNAR)\n")
    lines.append(md_table(null_pattern(reviews, ["review_comment_title", "review_comment_message"])) + "\n")
    has_comment = reviews["review_comment_message"].notna()
    blank = int((reviews["review_comment_message"].str.strip() == "").sum())
    by_score = has_comment.groupby(reviews["review_score"]).mean().map(lambda v: f"{v:.1%}")
    lines.append(
        "- Tỷ lệ có bình luận theo điểm: "
        + "; ".join(f"{score}★ {ratio}" for score, ratio in by_score.items())
        + " → khách không hài lòng viết bình luận nhiều hơn → khuyết **MNAR**, không điền"
    )
    length = reviews["review_comment_message"].str.len()
    lines.append(
        f"- Độ dài bình luận: median {length.median():.0f} ký tự, max {length.max():.0f}; "
        f"{blank} bình luận chỉ có khoảng trắng → coi là NULL\n"
    )
    issues.append(
        f"reviews: review_comment_title NULL {pct(int(reviews['review_comment_title'].isna().sum()), total)}, "
        f"message NULL {pct(int((~has_comment).sum()), total)} (MNAR) → giữ NULL, thêm cờ has_comment; "
        "GenAI/sentiment chỉ dùng phần có bình luận"
    )

    lines.append("### 2.5 Mốc thời gian\n")
    creation_has_time = int((reviews["review_creation_date"].dt.time.astype(str) != "00:00:00").sum())
    answer_hours = (reviews["review_answer_timestamp"] - reviews["review_creation_date"]).dt.total_seconds() / 3600
    merged = reviews.merge(orders, on="order_id", how="left")
    before_purchase = merged["review_creation_date"] < merged["order_purchase_timestamp"].dt.normalize()
    before_delivery = merged["review_creation_date"] < merged["order_delivered_customer_date"].dt.normalize()
    no_delivery = merged["order_delivered_customer_date"].isna()
    lines.append(
        f"- review_creation_date gần như chỉ có ngày: {creation_has_time} giá trị có giờ khác 00:00:00"
    )
    lines.append(
        f"- Thời gian từ gửi khảo sát → trả lời: median {answer_hours.median():.0f} giờ, max {answer_hours.max() / 24:,.0f} ngày; "
        f"trả lời trước khi tạo: {int((answer_hours < 0).sum())}"
    )
    lines.append(f"- {int(before_purchase.sum())} review được tạo trước ngày mua")
    lines.append(
        f"- {int(before_delivery.sum()):,} review tạo trước ngày khách nhận hàng, điểm TB "
        f"{merged.loc[before_delivery, 'review_score'].mean():.2f} (so với {merged['review_score'].mean():.2f} toàn bộ) "
        "→ khảo sát gửi theo ngày giao dự kiến, khách chưa nhận hàng thì chấm thấp"
    )
    lines.append(
        f"- {int(no_delivery.sum()):,} review thuộc đơn chưa giao tới khách, điểm TB "
        f"{merged.loc[no_delivery, 'review_score'].mean():.2f}\n"
    )
    issues.append(
        f"reviews: {int(before_purchase.sum())} review tạo trước ngày mua → gắn cờ; "
        f"{int(before_delivery.sum()):,} review tạo trước khi nhận hàng (điểm TB thấp) → là insight cho dashboard "
        "(giao trễ ↔ điểm thấp), không xóa"
    )

    lines.append("### 2.6 Toàn vẹn tham chiếu\n")
    lines.append(
        f"- order_id không có trong orders: {int((~reviews['order_id'].isin(orders['order_id'])).sum())}; "
        f"đơn không có review: {int((~orders['order_id'].isin(reviews['order_id'])).sum())}\n"
    )
    return lines, issues


def main() -> None:
    setup_console()
    run_report(
        "Profiling_OrderItems_Reviews.md",
        "Data profiling: order_items, order_reviews",
        [profile_order_items, profile_reviews],
        load_tables("order_items", "order_reviews", "orders", "products", "sellers"),
    )


if __name__ == "__main__":
    main()
