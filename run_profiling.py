"""Chạy toàn bộ data profiling cho bộ dữ liệu Olist.

    python run_profiling.py                  # chạy tất cả các bước
    python run_profiling.py issues reports   # chỉ chạy một số bước

Kết quả: bảng CSV trong output/, báo cáo Markdown trong output/dataProfiling/.
"""
import argparse
import time

from profiling import column_quality, issues, overview, relationships
from profiling.common import setup_console
from profiling.reports import geolocation, items_reviews, orders_payments_customers, products_sellers


STEPS = {
    "overview": [overview],  # Bảng 2.1
    "column_quality": [column_quality],  # Bảng 2.2
    "relationships": [relationships],  # Bảng 2.4
    "issues": [issues],  # Bảng 2.5
    "reports": [products_sellers, geolocation, orders_payments_customers, items_reviews],
}


def main() -> None:
    setup_console()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("steps", nargs="*", help=f"các bước cần chạy: {', '.join(STEPS)} (mặc định: tất cả)")
    selected = parser.parse_args().steps or list(STEPS)
    if unknown := [step for step in selected if step not in STEPS]:
        parser.error(f"bước không hợp lệ: {', '.join(unknown)} (chọn trong: {', '.join(STEPS)})")

    for step in selected:
        for module in STEPS[step]:
            start = time.perf_counter()
            print(f"\n=== {module.__name__} ===")
            module.main()
            print(f"({time.perf_counter() - start:.1f}s)")


if __name__ == "__main__":
    main()
