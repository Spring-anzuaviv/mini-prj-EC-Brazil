"""Bảng 2.4 — Kiểm tra quan hệ (khóa ngoại) giữa các bảng nguồn.

Kết quả: output/Bang_Quan_He_Bang.csv
"""
import pandas as pd

from profiling.common import load_tables, pct, save_csv, setup_console


# (bảng con, cột ở bảng con, bảng cha, cột ở bảng cha)
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


def check_relationship(
    t: dict[str, pd.DataFrame], child: str, child_column: str, parent: str, parent_column: str
) -> dict[str, object]:
    child_keys = t[child][child_column]
    parent_keys = t[parent][parent_column].dropna()
    parent_set = set(parent_keys)

    # Bản ghi con không khớp: có giá trị khóa nhưng không tìm thấy ở bảng cha.
    has_key = child_keys.notna()
    orphan = has_key & ~child_keys.isin(parent_set)
    orphan_rows = int(orphan.sum())
    orphan_values = int(child_keys[orphan].nunique())
    null_rows = int((~has_key).sum())
    childless = len(parent_set - set(child_keys.dropna()))

    children_per_key = child_keys.dropna().value_counts()
    max_children = int(children_per_key.max()) if not children_per_key.empty else 0
    if not parent_keys.is_unique:
        relation_type = "n – n"
    else:
        relation_type = "1 – 1" if max_children <= 1 else "1 – n"

    notes = [
        f"{orphan_rows:,} dòng con ({pct(orphan_rows, len(child_keys))}, "
        f"{orphan_values:,} giá trị khóa) không có ở {parent}"
    ]
    if null_rows:
        notes.append(f"{null_rows:,} dòng con có khóa NULL")
    notes.append(f"{childless:,}/{len(parent_set):,} khóa ở {parent} không xuất hiện ở {child}")
    notes.append(f"Tối đa {max_children:,} dòng {child} / 1 khóa")
    if not parent_keys.is_unique:
        duplicated = len(parent_keys) - parent_keys.nunique()
        notes.append(f"Khóa ở {parent} không duy nhất ({duplicated:,} dòng trùng) → cần gom nhóm trước khi nối")
    if 0 < orphan_values <= 5:
        notes.append(f"Giá trị không khớp: {', '.join(sorted(child_keys[orphan].astype(str).unique()))}")

    return {
        "Quan hệ": f"{child} → {parent}",
        "Khóa nối": child_column if child_column == parent_column else f"{child_column} = {parent_column}",
        "Kiểu quan hệ": relation_type,
        "Số bản ghi không khớp": orphan_rows,
        "Nhận xét": "; ".join(notes),
    }


def build() -> pd.DataFrame:
    tables = load_tables()
    return pd.DataFrame([check_relationship(tables, *relationship) for relationship in RELATIONSHIPS])


def main() -> None:
    setup_console()
    relationships = build()
    print(relationships.to_string(index=False, max_colwidth=80))
    save_csv(relationships, "Bang_Quan_He_Bang.csv")


if __name__ == "__main__":
    main()
