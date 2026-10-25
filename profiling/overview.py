"""Bảng 2.1 — Tổng quan từng bảng: số dòng/cột, khóa dự kiến, phạm vi thời gian.

Kết quả: output/Bang_Tong_Quan_Du_Lieu.csv
"""
import pandas as pd

from profiling.common import EXPECTED_KEYS, TABLE_FILES, is_time_column, read_table, save_csv, setup_console


def is_unique_key(df: pd.DataFrame, columns: list[str]) -> bool:
    """Khóa hợp lệ khi không NULL và không có bản ghi trùng."""
    return not df[columns].isna().any().any() and not df.duplicated(subset=columns).any()


def time_range(df: pd.DataFrame) -> str:
    columns = [c for c in df.columns if is_time_column(c) and df[c].notna().any()]
    if not columns:
        return "Không có dữ liệu thời gian"
    minimum = min(df[c].min() for c in columns)
    maximum = max(df[c].max() for c in columns)
    return f"{minimum:%Y-%m-%d %H:%M:%S} -> {maximum:%Y-%m-%d %H:%M:%S} ({', '.join(columns)})"


def build() -> pd.DataFrame:
    rows = []
    for table, file_name in TABLE_FILES.items():
        df = read_table(table)
        key = EXPECTED_KEYS[table]
        rows.append({
            "Bảng": file_name.removesuffix(".csv"),
            "Số dòng": len(df),
            "Số cột": len(df.columns),
            "Khóa dự kiến": " + ".join(key),
            "Khóa duy nhất?": "Có" if is_unique_key(df, key) else "Không",
            "Phạm vi thời gian": time_range(df),
        })
    return pd.DataFrame(rows)


def main() -> None:
    setup_console()
    summary = build()
    print(summary.to_string(index=False))
    save_csv(summary, "Bang_Tong_Quan_Du_Lieu.csv")


if __name__ == "__main__":
    main()
