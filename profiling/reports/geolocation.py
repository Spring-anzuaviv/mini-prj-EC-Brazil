"""Báo cáo chi tiết: olist_geolocation.

Kết quả: output/dataProfiling/Profiling_Geolocation.md
"""
import pandas as pd

from profiling.common import (
    BRAZIL_LAT,
    BRAZIL_LNG,
    BRAZIL_STATES,
    FAR_POINT_KM,
    cep_state,
    load_tables,
    normalize_text,
    outside_brazil,
    pct,
    setup_console,
    zip_spread_km,
)
from profiling.reports.markdown import basic_facts, column_overview, count_table, md_table, run_report


def profile_geolocation(data: dict[str, pd.DataFrame]) -> tuple[list[str], list[str]]:
    geo = data["geolocation"]
    zip_col = "geolocation_zip_code_prefix"
    total = len(geo)
    lines, issues = [], []

    lines.append("## 1. Tổng quan\n")
    lines.extend(basic_facts(geo, [zip_col]))
    valid_zip = int(geo[zip_col].str.fullmatch(r"\d{5}").sum())
    lines.append(
        f"- Mỗi dòng = 1 điểm tọa độ của 1 zip prefix (không phải 1 địa chỉ); "
        f"zip đúng 5 chữ số: {valid_zip:,}/{total:,}; "
        f"zip bắt đầu bằng 0: {geo[zip_col].str.startswith('0').sum():,}\n"
    )
    lines.append("### 1.1 Thống kê theo cột\n")
    lines.append(md_table(column_overview(geo)) + "\n")

    # Trùng lặp và số điểm trên mỗi zip.
    lines.append("### 1.2 Trùng lặp & số điểm trên mỗi zip\n")
    full_duplicates = int(geo.duplicated().sum())
    points_per_zip = geo.groupby(zip_col).size()
    lines.append(f"- {full_duplicates:,} dòng trùng hoàn toàn ({pct(full_duplicates, total)})")
    lines.append(
        f"- {points_per_zip.size:,} zip prefix; số dòng/zip: median {points_per_zip.median():.0f}, "
        f"mean {points_per_zip.mean():.1f}, max {points_per_zip.max():,} "
        f"(zip {points_per_zip.idxmax()}); {int((points_per_zip == 1).sum()):,} zip chỉ có 1 dòng"
    )
    lines.append(
        f"- Sau khi bỏ dòng trùng: {total - full_duplicates:,} dòng → vẫn phải gom về 1 dòng/zip "
        "trước khi nối với customers/sellers, nếu không sẽ nhân bản dòng\n"
    )
    issues.append(
        f"geolocation: {full_duplicates:,} dòng trùng hoàn toàn; {total:,} dòng cho "
        f"{points_per_zip.size:,} zip (TB {points_per_zip.mean():.1f} dòng/zip) → "
        "bỏ trùng rồi gom 1 dòng/zip (trung vị lat/lng) ở stg_geolocation"
    )

    # Tọa độ.
    lines.append("### 1.3 Kiểm tra tọa độ\n")
    outside = geo[outside_brazil(geo)]
    lines.append(
        f"- {len(outside)} dòng ({outside[zip_col].nunique()} zip) có tọa độ ngoài khung lãnh thổ Brazil "
        f"(lat {BRAZIL_LAT}, lng {BRAZIL_LNG})\n"
    )
    lines.append(
        md_table(
            outside[[zip_col, "geolocation_lat", "geolocation_lng", "geolocation_city", "geolocation_state"]]
            .head(10)
            .round(4)
        )
        + "\n"
    )

    distance, spread = zip_spread_km(geo)
    far_zips = spread[spread > FAR_POINT_KM].sort_values(ascending=False)
    far_points = int((distance > FAR_POINT_KM).sum())
    lines.append(
        f"- Độ phân tán trong 1 zip (khoảng cách xa nhất tới điểm trung vị): median {spread.median():.2f} km, "
        f"P99 {spread.quantile(0.99):.1f} km, max {spread.max():,.0f} km"
    )
    lines.append(
        f"- {far_zips.size} zip có điểm cách trung vị > {FAR_POINT_KM} km ({far_points} dòng) → "
        "dùng trung vị (không dùng trung bình) khi gom để không bị điểm lệch kéo đi"
    )
    lines.append(
        "- Zip lệch nhiều nhất: "
        + "; ".join(f"{zip_code} ({km:,.0f} km)" for zip_code, km in far_zips.head(5).items())
        + "\n"
    )
    issues.append(
        f"geolocation: {len(outside)} dòng tọa độ ngoài Brazil → loại bỏ; "
        f"{far_zips.size} zip có điểm lệch > {FAR_POINT_KM} km → gom bằng trung vị"
    )

    # Bang.
    lines.append("### 1.4 Kiểm tra bang (geolocation_state)\n")
    invalid_state = sorted(set(geo["geolocation_state"]) - BRAZIL_STATES)
    states_per_zip = geo.groupby(zip_col)["geolocation_state"].nunique()
    multi_state = states_per_zip[states_per_zip > 1]
    zip_table = geo[[zip_col, "geolocation_state"]].drop_duplicates()
    zip_table["cep_state"] = cep_state(zip_table[zip_col])
    cep_mismatch = zip_table[zip_table["cep_state"] != zip_table["geolocation_state"]]
    lines.append(
        f"- {geo['geolocation_state'].nunique()} mã bang; mã không hợp lệ: {invalid_state or 'không có'}"
    )
    lines.append(
        f"- {multi_state.size} zip gắn với > 1 bang: "
        + ", ".join(
            f"{zip_code} ({'/'.join(sorted(geo.loc[geo[zip_col] == zip_code, 'geolocation_state'].unique()))})"
            for zip_code in multi_state.index
        )
    )
    lines.append(
        f"- {len(cep_mismatch)} cặp (zip, bang) có bang khác với dải CEP của Correios "
        "(VD 01000–19999 là SP, 20000–28999 là RJ)\n"
    )
    if len(cep_mismatch):
        lines.append(md_table(cep_mismatch.head(10)) + "\n")
    issues.append(
        f"geolocation: {multi_state.size} zip gắn với > 1 bang, {len(cep_mismatch)} cặp zip–bang trái dải CEP → "
        "lấy bang xuất hiện nhiều nhất của zip; có thể dùng dải CEP làm quy tắc kiểm tra (dbt test)"
    )

    # Thành phố.
    lines.append("### 1.5 Chất lượng geolocation_city\n")
    geo["city_normalized"] = geo["geolocation_city"].map(normalize_text)
    raw_cities = geo["geolocation_city"].nunique()
    normalized_cities = geo["city_normalized"].nunique()
    accented = int(geo["geolocation_city"].str.contains(r"[^\x00-\x7f]", regex=True).sum())
    odd_chars = geo.loc[~geo["city_normalized"].str.fullmatch(r"[a-z' -]+"), "geolocation_city"]
    cities_per_zip = geo.groupby(zip_col)["city_normalized"].nunique()
    variants = (
        geo.groupby("city_normalized")["geolocation_city"].unique().loc[lambda s: s.map(len) > 1]
    )
    lines.append(f"- {raw_cities:,} giá trị gốc → {normalized_cities:,} sau khi bỏ dấu/chữ thường/khoảng trắng")
    lines.append(f"- {accented:,} dòng có chữ có dấu (VD 'são paulo') trong khi phần lớn ghi không dấu")
    lines.append(
        f"- {len(odd_chars):,} dòng chứa ký tự lạ sau chuẩn hóa, VD: "
        + "; ".join(f"'{city}'" for city in odd_chars.drop_duplicates().head(8))
    )
    lines.append(
        f"- {int((cities_per_zip > 1).sum()):,} zip có > 1 tên thành phố sau chuẩn hóa "
        "(zip prefix 5 số có thể trải qua nhiều đô thị nhỏ)"
    )
    lines.append(
        "- VD biến thể của cùng 1 tên: "
        + "; ".join(f"{key}: {list(value)[:4]}" for key, value in variants.head(5).items())
        + "\n"
    )
    issues.append(
        f"geolocation: geolocation_city {raw_cities:,} → {normalized_cities:,} giá trị sau chuẩn hóa → "
        f"bỏ dấu, chữ thường, gộp khoảng trắng, sửa {len(odd_chars)} dòng lỗi mã hóa/ký tự lạ "
        "(VD 'sa£o paulo', '%26apos%3b', tên kèm bang); lấy tên xuất hiện nhiều nhất của mỗi zip"
    )

    # Độ phủ cho customers / sellers.
    lines.append("### 1.6 Độ phủ cho customers & sellers\n")
    geo_zips = set(geo[zip_col])
    coverage = []
    for name, column in (("customers", "customer_zip_code_prefix"), ("sellers", "seller_zip_code_prefix")):
        zips = data[name][column]
        missing_rows = int((~zips.isin(geo_zips)).sum())
        missing_zips = zips[~zips.isin(geo_zips)].nunique()
        coverage.append([name, f"{len(zips):,}", f"{zips.nunique():,}", missing_rows, missing_zips, pct(missing_rows, len(zips))])
    lines.append(
        md_table(
            pd.DataFrame(
                coverage,
                columns=["Bảng", "Số dòng", "Số zip", "Dòng không có trong geo", "Zip không có trong geo", "Tỷ lệ dòng"],
            )
        )
        + "\n"
    )
    used_zips = set(data["customers"]["customer_zip_code_prefix"]) | set(data["sellers"]["seller_zip_code_prefix"])
    unused = len(geo_zips - used_zips)
    lines.append(f"- {unused:,}/{len(geo_zips):,} zip trong geolocation không được customers hay sellers dùng tới\n")
    issues.append(
        f"geolocation: {coverage[0][3]} customer và {coverage[1][3]} seller có zip không có tọa độ → "
        "LEFT JOIN, cho phép lat/lng NULL (không vẽ được trên bản đồ)"
    )

    lines.append("### 1.7 Phân bố theo bang\n")
    lines.append(count_table(geo.drop_duplicates(subset=[zip_col])["geolocation_state"], "Bang (theo số zip)") + "\n")
    return lines, issues


def main() -> None:
    setup_console()
    run_report(
        "Profiling_Geolocation.md",
        "Data profiling: olist_geolocation",
        [profile_geolocation],
        load_tables("geolocation", "customers", "sellers"),
    )


if __name__ == "__main__":
    main()
