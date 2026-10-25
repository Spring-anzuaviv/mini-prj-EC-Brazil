"""Các khối Markdown dùng chung cho báo cáo profiling chi tiết."""
from pathlib import Path

import pandas as pd

from profiling.common import ID_PATTERN, REPORT_DIR, SEQUENCE_COLUMNS, fmt, iqr_bounds, pct


def md_table(df: pd.DataFrame) -> str:
    """Xuất DataFrame thành bảng Markdown (không cần thư viện tabulate)."""
    header = "| " + " | ".join(str(column) for column in df.columns) + " |"
    divider = "|" + "---|" * len(df.columns)
    rows = ["| " + " | ".join(str(value) for value in row) + " |" for row in df.values]
    return "\n".join([header, divider, *rows])


def count_table(series: pd.Series, label: str, sort_by_value: bool = False) -> str:
    """Bảng phân bố giá trị: giá trị | số dòng | tỷ lệ."""
    counts = series.value_counts(dropna=False)
    if sort_by_value:
        counts = counts.sort_index()
    return md_table(
        counts.rename_axis(label)
        .reset_index(name="Số dòng")
        .assign(**{"Tỷ lệ": lambda d: d["Số dòng"].map(lambda c: pct(c, len(series)))})
    )


def column_overview(df: pd.DataFrame) -> pd.DataFrame:
    """Thống kê chung cho mọi cột: kiểu, Null, Distinct và min/max/phân vị hoặc top giá trị."""
    rows = []
    total = len(df)
    for column in df.columns:
        series = df[column]
        null_count = int(series.isna().sum())
        row = {
            "Cột": column,
            "Kiểu": str(series.dtype),
            "Null": f"{null_count:,} ({pct(null_count, total)})",
            "Distinct": f"{series.nunique():,}",
        }
        if pd.api.types.is_datetime64_any_dtype(series):
            errors = df.attrs.get("parse_errors", {}).get(column, 0)
            row.update({
                "Min": fmt(series.min()),
                "Max": fmt(series.max()),
                "Ghi chú": f"{errors} giá trị sai định dạng ngày" if errors else "",
            })
        elif pd.api.types.is_numeric_dtype(series):
            low, high = iqr_bounds(series)
            outliers = int(((series < low) | (series > high)).sum())
            row.update({
                "Min": fmt(series.min()),
                "P25": fmt(series.quantile(0.25)),
                "Median": fmt(series.median()),
                "Mean": fmt(round(series.mean(), 2)),
                "P75": fmt(series.quantile(0.75)),
                "P99": fmt(series.quantile(0.99)),
                "Max": fmt(series.max()),
                "Skew": f"{series.skew():.2f}",
                "Ngoại lai IQR": f"{outliers:,} ({pct(outliers, total)})",
            })
        else:
            top = series.value_counts().head(3)
            row["Top 3"] = "; ".join(f"{str(value)[:40]} ({pct(count, total)})" for value, count in top.items())
        rows.append(row)
    return pd.DataFrame(rows).fillna("")


def null_pattern(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """Các tổ hợp cột cùng NULL và số dòng tương ứng (missing pattern)."""
    labels = df[columns or list(df.columns)].isna().apply(
        lambda row: ", ".join(c for c, v in row.items() if v) or "(không thiếu)", axis=1
    )
    return labels.value_counts().rename_axis("Các cột cùng NULL").reset_index(name="Số dòng")


def basic_facts(df: pd.DataFrame, keys: list[str]) -> list[str]:
    """Số dòng/cột, dòng trùng, trùng khóa và định dạng mã (32 ký tự hex)."""
    lines = [
        f"- Số dòng: **{len(df):,}**, số cột: **{df.shape[1]}**",
        f"- Dòng trùng hoàn toàn: {df.duplicated().sum():,}; "
        f"trùng khóa ({' + '.join(keys)}): {df.duplicated(subset=keys).sum():,}",
    ]
    id_columns = [c for c in df.columns if c.endswith("_id") and c not in SEQUENCE_COLUMNS]
    if id_columns:
        lines.append(
            "- Định dạng 32 ký tự hex: "
            + "; ".join(
                f"{c} {df[c].str.fullmatch(ID_PATTERN).sum():,}/{df[c].notna().sum():,}" for c in id_columns
            )
        )
    return lines


def write_report(file_name: str, title: str, sections: list[str], issues: list[str]) -> Path:
    report = [f"# {title}\n", *sections, "## Tổng hợp vấn đề & đề xuất xử lý\n"]
    report.extend(f"{index}. {issue}" for index, issue in enumerate(issues, start=1))
    path = REPORT_DIR / file_name
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Đã ghi báo cáo: {path}")
    return path


def run_report(file_name: str, title: str, profiles, tables: dict[str, pd.DataFrame]) -> Path:
    """Chạy lần lượt các hàm profile_* (mỗi hàm trả về (lines, issues)) rồi ghi báo cáo."""
    sections, issues = [], []
    for profile in profiles:
        lines, table_issues = profile(tables)
        sections.extend(lines)
        issues.extend(table_issues)
    return write_report(file_name, title, sections, issues)
