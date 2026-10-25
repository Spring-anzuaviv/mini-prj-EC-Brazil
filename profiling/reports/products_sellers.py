"""Báo cáo chi tiết: olist_products, olist_sellers, product_category_name_translation.

Kết quả: output/dataProfiling/Profiling_Products_Sellers_Category.md
"""
import re

import pandas as pd

from profiling.common import (
    DATA_DIR,
    DEFAULT_DIMENSIONS,
    TABLE_FILES,
    load_tables,
    normalize_text,
    pct,
    setup_console,
    zip_state_mode,
)
from profiling.reports.markdown import column_overview, md_table, null_pattern, run_report


PRODUCT_SIZE_COLUMNS = ["product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"]
PRODUCT_NUMERIC_COLUMNS = ["product_name_lenght", "product_description_lenght", "product_photos_qty", *PRODUCT_SIZE_COLUMNS]


def share_table(counts: pd.Series, label: str, count_label: str, total: int) -> str:
    return md_table(
        counts.rename_axis(label)
        .reset_index(name=count_label)
        .assign(**{"Tỷ lệ": lambda d: d[count_label].map(lambda c: pct(c, total))})
    )


def profile_products(t: dict[str, pd.DataFrame]) -> tuple[list[str], list[str]]:
    products, items = t["products"], t["order_items"]
    total = len(products)
    lines, issues = [], []

    lines.append("## 1. olist_products_dataset\n")
    lines.append(f"- Số dòng: **{total:,}**, số cột: **{products.shape[1]}**")
    lines.append(
        f"- Dòng trùng hoàn toàn: {products.duplicated().sum():,}; "
        f"product_id trùng: {products['product_id'].duplicated().sum():,}; "
        f"product_id đúng định dạng 32 ký tự hex: "
        f"{products['product_id'].str.fullmatch(r'[0-9a-f]{32}').sum():,}/{total:,}"
    )
    non_integer = sum(int((products[c].dropna() % 1 != 0).sum()) for c in PRODUCT_NUMERIC_COLUMNS)
    lines.append(
        f"- Các cột số được đọc là float64 chỉ vì có NULL; số giá trị lẻ (không nguyên): "
        f"{non_integer} → nên lưu INT ở Data Warehouse\n"
    )
    lines.append("### 1.1 Thống kê theo cột\n")
    lines.append(md_table(column_overview(products)) + "\n")

    lines.append("### 1.2 Mẫu giá trị thiếu (missing pattern)\n")
    lines.append(md_table(null_pattern(products)) + "\n")
    issues.append(
        f"products: {int(products['product_category_name'].isna().sum())} sản phẩm thiếu category + "
        "name/description/photos (luôn thiếu cùng nhau) → gán 'unknown' ở dim_product"
    )
    issues.append(f"products: {int(products['product_weight_g'].isna().sum())} sản phẩm thiếu toàn bộ cân nặng & kích thước")

    lines.append("### 1.3 Kiểm tra hợp lệ của cân nặng & kích thước\n")
    weight = products["product_weight_g"]
    zero_weight = products[weight == 0]
    length, height, width = DEFAULT_DIMENSIONS
    default_size = int(
        ((products["product_length_cm"] == length)
         & (products["product_height_cm"] == height)
         & (products["product_width_cm"] == width)).sum()
    )
    volume = products["product_length_cm"] * products["product_height_cm"] * products["product_width_cm"]
    heavy_tiny = int(((weight > 10_000) & (volume < 1_000)).sum())
    too_dense = int((weight / volume > 5).sum())  # g/cm³; nước = 1
    checks = [
        ["product_weight_g = 0", len(zero_weight),
         "Toàn bộ thuộc " + ", ".join(zero_weight["product_category_name"].dropna().unique())],
        [f"Kích thước đúng {length}x{height}x{width} cm (mặc định Correios)", default_size,
         "Nhiều khả năng là kích thước nhập mặc định, không phải thật"],
        ["Nặng > 10 kg nhưng thể tích < 1.000 cm³", heavy_tiny, "Mâu thuẫn cân nặng – kích thước"],
        ["Mật độ > 5 g/cm³ (gấp 5 lần nước, gần bằng sắt ~7.8)", too_dense, "Nghi sai đơn vị/nhập liệu"],
        ["Dài + cao + rộng > 200 cm", int((products[PRODUCT_SIZE_COLUMNS[1:]].sum(axis=1) > 200).sum()),
         "Vượt giới hạn gửi hàng Correios"],
        ["product_name_lenght < 10 ký tự", int((products["product_name_lenght"] < 10).sum()), "Tên sản phẩm quá ngắn"],
        ["product_description_lenght < 20 ký tự", int((products["product_description_lenght"] < 20).sum()),
         "Mô tả quá ngắn"],
    ]
    lines.append(md_table(pd.DataFrame(checks, columns=["Kiểm tra", "Số dòng", "Ghi chú"])) + "\n")
    issues.append(f"products: {len(zero_weight)} sản phẩm cân nặng = 0 g → đặt NULL (không dùng 0 khi tính TB)")
    issues.append(
        f"products: {heavy_tiny} sản phẩm nặng > 10 kg nhưng thể tích < 1 lít, "
        f"{too_dense} sản phẩm mật độ > 5 g/cm³ → gắn cờ nghi ngờ khi phân tích phí vận chuyển"
    )
    issues.append(f"products: phân phối lệch phải mạnh (weight skew {weight.skew():.1f}) → dùng median/bin thay vì mean")

    lines.append("### 1.4 Phân bố danh mục\n")
    category_counts = products["product_category_name"].value_counts()
    lines.append(
        f"- {category_counts.size} danh mục; top 10 danh mục chiếm "
        f"{pct(int(category_counts.head(10).sum()), total)} số sản phẩm; "
        f"{int((category_counts < 10).sum())} danh mục có < 10 sản phẩm\n"
    )
    lines.append(
        share_table(pd.concat([category_counts.head(5), category_counts.tail(5)]),
                    "product_category_name", "Số sản phẩm", total) + "\n"
    )

    lines.append("### 1.5 Toàn vẹn tham chiếu\n")
    untranslated = sorted(set(products["product_category_name"].dropna()) - set(t["category_translation"]["product_category_name"]))
    null_category_items = items["product_id"].isin(products.loc[products["product_category_name"].isna(), "product_id"])
    sellers_per_product = items.groupby("product_id")["seller_id"].nunique()
    single_sale = int((items["product_id"].value_counts() == 1).sum())
    lines.append(
        f"- Danh mục trong products **không có bản dịch**: {', '.join(untranslated)} "
        f"({int(products['product_category_name'].isin(untranslated).sum())} sản phẩm)"
    )
    lines.append(f"- Sản phẩm chưa từng bán (không có trong order_items): {int((~products['product_id'].isin(items['product_id'])).sum())}")
    lines.append(f"- product_id trong order_items không có trong products: {len(set(items['product_id']) - set(products['product_id']))}")
    lines.append(
        f"- Sản phẩm thiếu category xuất hiện ở {null_category_items.sum():,} order item "
        f"({pct(int(null_category_items.sum()), len(items))}), chiếm "
        f"{items.loc[null_category_items, 'price'].sum() / items['price'].sum():.2%} doanh thu"
    )
    lines.append(f"- {single_sale:,} sản phẩm ({pct(single_sale, total)}) chỉ bán đúng 1 lần (long tail)")
    lines.append(
        f"- {int((sellers_per_product > 1).sum()):,} sản phẩm được bán bởi > 1 seller "
        f"(tối đa {sellers_per_product.max()}) → product không thuộc riêng seller nào\n"
    )
    issues.append(
        f"products ↔ translation: {len(untranslated)} danh mục ({', '.join(untranslated)}) "
        "không có tên tiếng Anh → bổ sung thủ công trong dbt seed"
    )
    issues.append("products: tên cột sai chính tả product_name_lenght / product_description_lenght → đổi ở dbt")
    return lines, issues


def profile_sellers(t: dict[str, pd.DataFrame]) -> tuple[list[str], list[str]]:
    sellers, items = t["sellers"], t["order_items"]
    total = len(sellers)
    zips = sellers["seller_zip_code_prefix"]
    lines, issues = [], []

    valid_zip = int(zips.str.fullmatch(r"\d{5}").sum())
    lines.append("## 2. olist_sellers_dataset\n")
    lines.append(f"- Số dòng: **{total:,}**, số cột: **{sellers.shape[1]}**")
    lines.append(
        f"- Dòng trùng hoàn toàn: {sellers.duplicated().sum():,}; "
        f"seller_id trùng: {sellers['seller_id'].duplicated().sum():,}; "
        f"zip đúng 5 chữ số: {valid_zip:,}/{total:,}; "
        f"zip bắt đầu bằng 0: {zips.str.startswith('0').sum():,}\n"
    )
    lines.append("### 2.1 Thống kê theo cột\n")
    lines.append(md_table(column_overview(sellers)) + "\n")

    lines.append("### 2.2 Phân bố theo bang\n")
    state_counts = sellers["seller_state"].value_counts()
    lines.append(
        f"- {state_counts.size}/27 bang có seller; SP chiếm {pct(int(state_counts['SP']), total)}; "
        f"{int((state_counts <= 5).sum())} bang có ≤ 5 seller → phân tích theo bang cần gom nhóm vùng\n"
    )
    lines.append(share_table(state_counts, "seller_state", "Số seller", total) + "\n")

    lines.append("### 2.3 Chất lượng seller_city\n")
    city = sellers["seller_city"]
    normalized = city.map(normalize_text)
    dirty = int((~city.str.fullmatch(r"[a-z ]+")).sum())
    garbage = city[city.str.contains(r"@|\d", regex=True)].tolist()
    with_state = city[city.str.contains(r"[/\\,]|\s-\s|-[a-z]{2}$", regex=True)]
    variants = {k: list(v) for k, v in city.groupby(normalized).unique().items() if len(v) > 1}
    lines.append(f"- {city.nunique()} giá trị gốc → {normalized.nunique()} sau khi bỏ dấu/khoảng trắng")
    lines.append(f"- {dirty} dòng chứa ký tự ngoài [a-z ] (dấu, '/', '-', ',', số, email)")
    lines.append(
        f"- {len(with_state)} dòng gộp cả tên bang vào city, VD: "
        + "; ".join(f"'{value}'" for value in with_state.head(5))
    )
    lines.append(f"- Giá trị rác (không phải tên thành phố): {garbage}")
    lines.append("- Biến thể cùng 1 thành phố: " + "; ".join(f"{k}: {v}" for k, v in variants.items()) + "\n")

    lines.append("### 2.4 Đối chiếu zip/state với geolocation\n")
    missing_zip = zips[~zips.isin(t["geolocation"]["geolocation_zip_code_prefix"])]
    geo_state = zips.map(zip_state_mode(t["geolocation"]))
    mismatch = sellers.assign(geo_state=geo_state)[geo_state.notna() & (sellers["seller_state"] != geo_state)]
    lines.append(f"- {len(missing_zip)} seller có zip không tồn tại trong geolocation: {', '.join(missing_zip)}")
    lines.append(
        f"- {len(mismatch)} seller có seller_state khác bang suy ra từ zip "
        f"({int((mismatch['seller_state'] == 'SP').sum())} trường hợp ghi nhầm thành 'SP')\n"
    )
    lines.append(md_table(mismatch[["seller_zip_code_prefix", "seller_city", "seller_state", "geo_state"]].head(10)) + "\n")

    lines.append("### 2.5 Hoạt động bán hàng (join order_items)\n")
    orders_per_seller = items.groupby("seller_id")["order_id"].nunique()
    products_per_seller = items.groupby("seller_id")["product_id"].nunique()
    top_10pct = orders_per_seller.sort_values(ascending=False).head(int(total * 0.1)).sum()
    lines.append(
        f"- Seller không có đơn: {int((~sellers['seller_id'].isin(orders_per_seller.index)).sum())}; "
        f"seller_id trong order_items không có trong sellers: {len(set(items['seller_id']) - set(sellers['seller_id']))}"
    )
    lines.append(
        f"- Số đơn/seller: median {orders_per_seller.median():.0f}, mean {orders_per_seller.mean():.1f}, "
        f"max {orders_per_seller.max():,}; {int((orders_per_seller == 1).sum())} seller chỉ có 1 đơn"
    )
    lines.append(f"- Top 10% seller chiếm {top_10pct / orders_per_seller.sum():.1%} số đơn (phân phối rất tập trung)")
    lines.append(f"- Số sản phẩm/seller: median {products_per_seller.median():.0f}, max {products_per_seller.max()}\n")

    issues.append(f"sellers: seller_city bẩn ({dirty} dòng: kèm bang, có dấu, email, số) → chuẩn hóa và ưu tiên phân tích theo state")
    issues.append(f"sellers: {len(mismatch)} seller_state mâu thuẫn với zip (đa số ghi 'SP') → suy lại bang từ zip qua geolocation")
    issues.append(f"sellers: {len(missing_zip)} zip không có trong geolocation → không vẽ được bản đồ, cho phép NULL lat/lng")
    return lines, issues


def profile_translation(t: dict[str, pd.DataFrame]) -> tuple[list[str], list[str]]:
    translation = t["category_translation"]
    source, english = translation["product_category_name"], translation["product_category_name_english"]
    has_bom = (DATA_DIR / TABLE_FILES["category_translation"]).read_bytes()[:3] == b"\xef\xbb\xbf"
    lines = ["## 3. product_category_name_translation\n"]
    lines.append(f"- Số dòng: **{len(translation)}**, số cột: **{translation.shape[1]}**")
    lines.append(f"- File có BOM UTF-8: **{'Có' if has_bom else 'Không'}**")
    lines.append(
        f"- Null: {int(translation.isna().sum().sum())}; trùng tên PT: {source.duplicated().sum()}; "
        f"trùng tên EN: {english.duplicated().sum()}"
    )
    bad_format = [v for column in translation for v in translation[column] if not re.fullmatch(r"[a-z0-9_]+", v)]
    lines.append(f"- Giá trị không theo định dạng snake_case: {bad_format or 'không có'}")
    # Một số bản dịch giữ nguyên tiếng Bồ Đào Nha hoặc bị sai chính tả.
    lines.append(f"- Bản dịch giống hệt tên gốc: {source[source == english].tolist()}")
    typo = translation[english.str.contains("fashio_|_2$", regex=True)]
    lines.append(
        "- Bản dịch có lỗi/hậu tố khó hiểu: "
        + "; ".join(f"{row.product_category_name} → {row.product_category_name_english}" for row in typo.itertuples())
    )
    unused = sorted(set(source) - set(t["products"]["product_category_name"].dropna()))
    lines.append(f"- Danh mục có bản dịch nhưng không có sản phẩm: {unused or 'không có'}\n")

    issues = [
        "translation: file có BOM → đọc bằng utf-8-sig / cấu hình encoding ở Mage, "
        "nếu không cột đầu thành '\\ufeffproduct_category_name'",
        "translation: thiếu danh mục (xem mục 1.5), có lỗi chính tả 'fashio_female_clothing', hậu tố '_2' "
        "→ tạo seed dbt chuẩn hóa tên hiển thị (VD: Title Case, thay '_' bằng khoảng trắng)",
    ]
    return lines, issues


def main() -> None:
    setup_console()
    run_report(
        "Profiling_Products_Sellers_Category.md",
        "Data profiling: products, sellers, category translation",
        [profile_products, profile_sellers, profile_translation],
        load_tables("products", "sellers", "category_translation", "order_items", "geolocation"),
    )


if __name__ == "__main__":
    main()
