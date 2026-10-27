#!/usr/bin/env python3
"""
benchmark_v2/tools/compute_kappa.py
Tính độ đồng thuận (Percent Agreement) và hệ số Cohen's Kappa (κ) giữa 2 người đánh giá (hoặc Agent nháp vs Chuyên gia).
Hỗ trợ cả CLI và module import.
"""

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def cohen_kappa(rater1: List[str], rater2: List[str]) -> Tuple[float, float, Dict]:
    """
    Tính percent agreement (po) và Cohen's Kappa (kappa).
    Trả về: (po, kappa, stats_dict)
    """
    if len(rater1) != len(rater2):
        raise ValueError(f"Kích thước 2 danh sách không khớp: {len(rater1)} vs {len(rater2)}")
    n = len(rater1)
    if n == 0:
        return 1.0, 1.0, {}

    # Danh sách tất cả categories
    categories = sorted(list(set(rater1) | set(rater2)))

    # Observed agreement
    agree_count = sum(1 for a, b in zip(rater1, rater2) if a == b)
    p_o = agree_count / n

    # Marginals for chance agreement
    c1 = Counter(rater1)
    c2 = Counter(rater2)

    p_e = sum((c1[cat] / n) * (c2[cat] / n) for cat in categories)

    if p_e >= 1.0:
        kappa = 1.0
    else:
        kappa = (p_o - p_e) / (1.0 - p_e)

    # Confusion matrix
    matrix = {c1_cat: {c2_cat: 0 for c2_cat in categories} for c1_cat in categories}
    disagreements = []
    for idx, (a, b) in enumerate(zip(rater1, rater2)):
        matrix[a][b] += 1
        if a != b:
            disagreements.append({"index": idx, "rater1": a, "rater2": b})

    stats = {
        "n": n,
        "agree_count": agree_count,
        "p_o": p_o,
        "p_e": p_e,
        "kappa": kappa,
        "categories": categories,
        "confusion_matrix": matrix,
        "disagreements": disagreements,
    }
    return p_o, kappa, stats


def print_report(title: str, stats: Dict):
    print("=" * 60)
    print(f"KẾT QUẢ ĐỒNG THUẬN & COHEN'S KAPPA: {title}")
    print("=" * 60)
    print(f"Số mẫu đánh giá (N): {stats['n']}")
    print(f"Số ca đồng thuận:   {stats['agree_count']}/{stats['n']} ({stats['p_o']*100:.2f}%)")
    print(f"Xác suất ngẫu nhiên (Pe): {stats['p_e']*100:.2f}%")
    print(f"Hệ số Cohen's Kappa (κ):  {stats['kappa']:.4f}")

    # Diễn giải Kappa theo Landis & Koch (1977)
    k = stats["kappa"]
    if k < 0:
        interp = "Poor (kém hơn ngẫu nhiên)"
    elif k <= 0.20:
        interp = "Slight (rất thấp)"
    elif k <= 0.40:
        interp = "Fair (chấp nhận được nhưng yếu)"
    elif k <= 0.60:
        interp = "Moderate (trung bình)"
    elif k <= 0.80:
        interp = "Substantial (đáng kể / tốt)"
    else:
        interp = "Almost Perfect (gần như hoàn hảo)"
    print(f"Mức độ đánh giá:    {interp}")
    print("-" * 60)

    print("Ma trận nhầm lẫn (Rater 1 hàng \\ Rater 2 cột):")
    cats = stats["categories"]
    header = f"{'':15} | " + " | ".join(f"{c:>12}" for c in cats)
    print(header)
    print("-" * len(header))
    for c1 in cats:
        row = f"{c1:15} | " + " | ".join(f"{stats['confusion_matrix'][c1][c2]:>12}" for c2 in cats)
        print(row)

    if stats["disagreements"]:
        print("-" * 60)
        print(f"Các ca bất đồng ({len(stats['disagreements'])} ca):")
        for d in stats["disagreements"][:10]:
            print(f"  - Dòng #{d['index']}: Rater1 = '{d['rater1']}' vs Rater2 = '{d['rater2']}'")
        if len(stats["disagreements"]) > 10:
            print(f"  ... và {len(stats['disagreements']) - 10} ca khác.")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Tính Cohen's Kappa cho benchmark triage / validation")
    parser.add_argument("--csv", type=str, help="Đường dẫn file CSV chứa 2 cột nhãn rater")
    parser.add_argument("--col1", type=str, default="track", help="Tên cột của Rater 1")
    parser.add_argument("--col2", type=str, default="track_human", help="Tên cột của Rater 2")
    args = parser.parse_args()

    if not args.csv:
        print("Vui lòng cung cấp --csv hoặc import hàm cohen_kappa.")
        sys.exit(1)

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Lỗi: Không tìm thấy file {csv_path}")
        sys.exit(1)

    with open(csv_path, encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    if not reader:
        print("File CSV rỗng.")
        sys.exit(1)

    if args.col1 not in reader[0] or args.col2 not in reader[0]:
        print(f"Lỗi: File CSV phải chứa 2 cột '{args.col1}' và '{args.col2}'")
        print(f"Các cột hiện có: {list(reader[0].keys())}")
        sys.exit(1)

    r1 = [row[args.col1].strip() for row in reader]
    r2 = [row[args.col2].strip() for row in reader]

    p_o, k, stats = cohen_kappa(r1, r2)
    print_report(f"{args.col1} vs {args.col2}", stats)


if __name__ == "__main__":
    main()
