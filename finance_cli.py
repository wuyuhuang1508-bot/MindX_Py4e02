#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Dict, Any, Optional
from core import (
    validate_ranges_base, recalc_unit_metrics, apply_marketing_global,
    calc_b12, calc_b13_extra_units, b11_reference, fmt_vnd
)

def input_float(msg: str) -> float:
    while True:
        s = input(msg).strip().replace(",", "")
        try:
            return float(s)
        except: print("❌ Nhập số hợp lệ.")

def input_int(msg: str) -> int:
    while True:
        s = input(msg).strip()
        try:
            return int(s)
        except: print("❌ Nhập số nguyên hợp lệ.")

def step_ranges() -> List[Dict[str, Any]]:
    ranges: List[Dict[str, Any]] = []
    print("\n=== B3: Range (tối đa 3, tổng % = 100%) ===")
    for i in range(1, 4):
        ten = input(f"Tên range #{i} (Enter để dừng): ").strip()
        if not ten: break
        ty = input_float(f"  Tỷ lệ % cho '{ten}': ")
        gb = input_float(f"  Giá bán '{ten}' (VND): ")
        cogs = input_float(f"  COGS% '{ten}' (0-100): ")
        ranges.append({"ten": ten, "ty_le": ty, "gia_ban": gb, "cogs_pct": cogs})
    msg = validate_ranges_base(ranges)
    if msg: raise ValueError(msg)
    for r in ranges:
        e = recalc_unit_metrics(r)
        if e: raise ValueError(f"{r['ten']}: {e}")
    return ranges

def show_per_unit(ranges: List[Dict[str, Any]]):
    print("\n— Chỉ tiêu /đơn vị sau MKT GLOBAL —")
    for r in ranges:
        print(f"{r['ten']:<18} | Giá: {fmt_vnd(r['gia_ban'])} | COGS/đv: {fmt_vnd(r['cogs_per_unit'])} "
              f"| MKT/đv: {fmt_vnd(r['marketing_per_unit'])} | Tổng CP/đv: {fmt_vnd(r['total_cost_per_unit'])} "
              f"| LN sau MKT/đv: {fmt_vnd(r['profit_after_mkt_per_unit'])}")

def main():
    print("=== PROJECT TÀI CHÍNH (CLI) — B1→14 ===")
    # B1
    capital = input_float("B1) Vốn dự kiến (VND): ")

    # B2 (rút gọn)
    portfolio = []
    print("\nB2) Danh mục dự án (Enter để bỏ qua):")
    while True:
        ten = input("  Tên dự án (Enter để dừng): ").strip()
        if not ten: break
        von = input_float("  Vốn phân bổ (VND): ")
        portfolio.append({"ten": ten, "von": von})

    # B3–5
    ranges = step_ranges()

    # B7: MKT GLOBAL
    mkt = input_float("\nB7) Marketing % GLOBAL trên Tổng chi phí: ")
    e = apply_marketing_global(ranges, mkt)
    if e: raise ValueError(e)
    show_per_unit(ranges)

    # B8–10: Overheads/tháng
    print("\nB8–10) Overheads/tháng:")
    salary = input_float("  Lương: ")
    fixed  = input_float("  Cố định: ")
    others = input_float("  Overheads khác: ")
    overheads_month = salary + fixed + others

    # B11: Payback
    payback = input_int("\nB11) Số tháng kỳ vọng hoàn vốn: ")
    ref = b11_reference(ranges, capital, payback, overheads_month)
    print("\n— Tham chiếu B11 —")
    print(f"LN/đv bình quân sau MKT: {ref['composite_profit_after_mkt_per_unit']:.2f}")
    print(f"Cần CF ròng/tháng: {fmt_vnd(ref['need_net_cf_per_month'])}")
    print(f"Target LN sau MKT/tháng: {fmt_vnd(ref['target_gp_after_per_month'])}")
    if ref["units_target_per_month"]:
        print(f"Đơn vị/tháng cần bán: {ref['units_target_per_month']:.2f}")

    # B12: nhập sản lượng/tháng
    print("\nB12) Nhập sản lượng/tháng:")
    units_map = {}
    for r in ranges:
        units_map[r["ten"]] = input_float(f"  {r['ten']}: ")
    b12 = calc_b12(ranges, units_map, overheads_month, capital)
    print("\n— Kết quả B12 —")
    print(f"Doanh thu/tháng: {fmt_vnd(b12['doanh_thu_thang'])}")
    print(f"LN sau MKT/tháng: {fmt_vnd(b12['ln_sau_mkt_thang'])}")
    print(f"Dòng tiền ròng/tháng: {fmt_vnd(b12['dong_tien_rong_thang'])}")
    print(f"Tháng hoà vốn (ước tính): {b12['thang_hoa_von'] if b12['thang_hoa_von'] else '—'}")

    # B13: số lượng bổ sung cần bán
    b13 = calc_b13_extra_units(ranges, overheads_month, capital, payback, b12)
    print("\n— Kết quả B13 —")
    A = b13["A"]; B = b13["B"]
    print(f"[A] Hoà vốn tháng: thiếu LN {fmt_vnd(A['gap_ln'])} → cần thêm {A['units_bo_sung']:.2f} 'đv composite'")
    if A["chi_tiet"]:
        for it in A["chi_tiet"]:
            print(f"    - {it['ten']}: +{it['units_bo_sung']:.2f} đv/tháng")
    if B:
        print(f"[B] Hoàn vốn {payback} tháng: thiếu LN {fmt_vnd(B['gap_ln'])} → cần thêm {B['units_bo_sung']:.2f}")
        if B["chi_tiet"]:
            for it in B["chi_tiet"]:
                print(f"    - {it['ten']}: +{it['units_bo_sung']:.2f} đv/tháng")

    # B14: What-if (loop)
    while True:
        more = input("\nB14) Chạy What-if? (Y/N): ").strip().lower()
        if more not in ("y", "yes"): break
        # overrides
        try_mkt = input("  %MKT GLOBAL (Enter giữ): ").strip()
        if try_mkt:
            e = apply_marketing_global(ranges, float(try_mkt))
            if e: print("  ⚠️", e)
        for r in ranges:
            s = input(f"  Giá '{r['ten']}' (Enter giữ): ").strip()
            if s:
                r["gia_ban"] = float(s)
            s = input(f"  COGS% '{r['ten']}' (Enter giữ): ").strip()
            if s:
                r["cogs_pct"] = float(s)
            recalc_unit_metrics(r)
        show_per_unit(ranges)
        s = input("  Overheads/tháng (Enter giữ): ").strip()
        if s: overheads_month = float(s)
        s = input("  Payback tháng (Enter giữ): ").strip()
        if s: payback = int(s)
        # units
        print("  Sản lượng/tháng kịch bản:")
        for r in ranges:
            s = input(f"    {r['ten']} (Enter giữ): ").strip()
            if s: units_map[r["ten"]] = float(s)
        b12 = calc_b12(ranges, units_map, overheads_month, capital)
        b13 = calc_b13_extra_units(ranges, overheads_month, capital, payback, b12)
        print("  — KQ What-if —")
        print(f"    DT/tháng: {fmt_vnd(b12['doanh_thu_thang'])} | LN sau MKT: {fmt_vnd(b12['ln_sau_mkt_thang'])} "
              f"| CF ròng: {fmt_vnd(b12['dong_tien_rong_thang'])} | Tháng HV: {b12['thang_hoa_von']}")
        print(f"    Bổ sung (A): {b13['A']['units_bo_sung']:.2f} | Bổ sung (B): {b13['B']['units_bo_sung'] if b13['B'] else '—'}")

    print("\n✅ Hoàn tất. Cảm ơn bạn!")

if __name__ == "__main__":
    main()
