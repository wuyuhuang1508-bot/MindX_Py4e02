#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Dict, Optional, Any
import math

EPS = 1e-6

# ============== Helpers ==============
def fmt_vnd(v: float) -> int:
    try:
        return int(round(float(v)))
    except Exception:
        return 0

# ============== Validation ==============
def validate_ranges_base(ranges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Kiểm tra danh mục sản phẩm:
      - ranges là list không rỗng, tối đa 3
      - mỗi item có: ten, ty_le, gia_ban, cogs_pct
      - 0<=ty_le<=100 và tổng ty_le≈100
      - gia_ban>0, 0<cogs_pct<100
    Trả về chính ranges nếu hợp lệ; raise ValueError nếu sai.
    """
    if not isinstance(ranges, list) or not ranges:
        raise ValueError("ranges phải là list không rỗng.")
    if len(ranges) > 3:
        raise ValueError("Tối đa 3 range.")

    total_pct = 0.0
    for i, r in enumerate(ranges, 1):
        for k in ("ten", "ty_le", "gia_ban", "cogs_pct"):
            if k not in r:
                raise ValueError(f"Range #{i} thiếu '{k}'.")
        try:
            ty = float(r["ty_le"])
            gia = float(r["gia_ban"])
            cogs_pct = float(r["cogs_pct"])
        except Exception:
            raise ValueError(f"Range #{i} có dữ liệu số không hợp lệ.")
        if not (0 <= ty <= 100):
            raise ValueError(f"Range '{r['ten']}' 'ty_le' phải trong [0,100].")
        if gia <= 0:
            raise ValueError(f"Range '{r['ten']}' 'gia_ban' phải > 0.")
        if not (0 < cogs_pct < 100):
            raise ValueError(f"Range '{r['ten']}' 'cogs_pct' phải trong (0,100).")
        # chuẩn lại kiểu float
        r["ty_le"] = ty
        r["gia_ban"] = gia
        r["cogs_pct"] = cogs_pct
        total_pct += ty

    if not math.isclose(total_pct, 100.0, rel_tol=1e-3, abs_tol=1e-6):
        raise ValueError(f"Tổng mix % phải bằng 100% (hiện = {total_pct}).")
    return ranges

# ============== Recalc per-unit metrics ==============
def recalc_unit_metrics(ranges: List[Dict[str, Any]], marketing_pct: float) -> List[Dict[str, Any]]:
    """
    Tính chỉ tiêu/đơn vị cho toàn bộ danh mục với %MKT trên GIÁ BÁN:
      cogs_per_unit       = gia_ban * cogs_pct/100
      marketing_per_unit  = gia_ban * marketing_pct/100
      total_cost_per_unit = cogs_per_unit + marketing_per_unit
      profit_after_mkt    = gia_ban - total_cost_per_unit
      margin_after_mkt_%  = profit_after_mkt / gia_ban
    """
    try:
        m = float(marketing_pct)
    except Exception:
        raise ValueError("marketing_global_pct không hợp lệ.")
    if not (0 <= m < 100):
        raise ValueError("marketing_global_pct phải trong [0,100).")
    m /= 100.0

    for r in ranges:
        gia = float(r["gia_ban"])
        cogs_pct = float(r["cogs_pct"])
        cogs = gia * (cogs_pct / 100.0)
        mkt  = gia * m
        total = cogs + mkt
        profit = gia - total
        margin_pct = 100.0 * profit / (gia + EPS)
        r["cogs_per_unit"] = cogs
        r["marketing_per_unit"] = mkt
        r["total_cost_per_unit"] = total
        r["profit_after_mkt_per_unit"] = profit
        r["margin_after_mkt_pct"] = margin_pct
    return ranges

def apply_marketing_global(ranges: List[Dict[str, Any]], mkt_pct_global: float) -> List[Dict[str, Any]]:
    """Áp %MKT global (trên GIÁ BÁN) cho toàn bộ ranges."""
    return recalc_unit_metrics(ranges, mkt_pct_global)

# ============== Composite helper ==============
def composite_profit_after_mkt_per_unit(ranges: List[Dict[str, Any]]) -> float:
    """
    Lợi nhuận sau MKT/đv bình quân có xét mix:
      Σ (profit_after_mkt_per_unit * ty_le/100)
    """
    if not ranges:
        return 0.0
    val = 0.0
    for r in ranges:
        pa = float(r.get("profit_after_mkt_per_unit", 0.0))
        w  = float(r.get("ty_le", 0.0)) / 100.0
        val += pa * w
    return val

# ============== B11 reference ==============
def b11_reference(
    ranges: List[Dict[str, Any]],
    capital: float,
    payback_months: int,
    overheads_month: float
) -> Dict[str, Any]:
    """
    - composite_profit_after_mkt_per_unit
    - need_net_cf_per_month = capital / payback_months
    - target_gp_after_per_month = overheads_month + need_net_cf_per_month
    - units_target_per_month (nếu composite>0), và chia theo mix
    """
    comp_gp = composite_profit_after_mkt_per_unit(ranges)
    if payback_months < 1:
        raise ValueError("payback_months phải >= 1.")
    need_net_cf = float(capital) / float(payback_months)
    target_gp_after = float(overheads_month) + need_net_cf

    if comp_gp > 0:
        units_target = target_gp_after / comp_gp
        split = [
            {"ten": r["ten"], "ty_le": float(r["ty_le"]),
             "units_thang": units_target * (float(r["ty_le"]) / 100.0)}
            for r in ranges
        ]
    else:
        units_target, split = None, []

    return {
        "composite_profit_after_mkt_per_unit": comp_gp,
        "need_net_cf_per_month": need_net_cf,
        "target_gp_after_per_month": target_gp_after,
        "units_target_per_month": units_target,
        "split_by_range": split
    }

# ============== B12 ==============
def calc_b12(
    ranges: List[Dict[str, Any]],
    units_by_range: Dict[str, float],
    overheads_month: float,
    capital: float
) -> Dict[str, Any]:
    """
    - Doanh thu/tháng      = Σ (gia_ban * units)
    - LN sau MKT/tháng     = Σ (profit_after_mkt_per_unit * units)
    - Dòng tiền ròng/tháng = LN sau MKT - overheads
    - Tháng hoà vốn        = capital / (dòng tiền ròng)  (None nếu <=0)
    """
    rev = 0.0
    ln_after = 0.0
    for r in ranges:
        name = r["ten"]
        u = float(units_by_range.get(name, 0.0))
        rev += u * float(r["gia_ban"])
        ln_after += u * float(r["profit_after_mkt_per_unit"])
    net_cf = ln_after - float(overheads_month)
    months = None if net_cf <= 0 else float(capital) / net_cf
    return {
        "doanh_thu_thang": rev,
        "ln_sau_mkt_thang": ln_after,
        "dong_tien_rong_thang": net_cf,
        "thang_hoa_von": months
    }

# ============== B13 ==============
def calc_b13_extra_units(
    ranges: List[Dict[str, Any]],
    capital: float,
    payback_months: int,
    overheads_month: float,
    current_ln: float
) -> Dict[str, Any]:
    """
    - need_ln_thang (mục tiêu LN sau MKT) = capital/payback + overheads
    - gap_ln = need_ln_thang - current_ln (>=0)
    - composite_ln_per_unit
    - units_bo_sung = gap_ln / composite_ln_per_unit
    - phân bổ theo mix
    """
    if payback_months < 1:
        raise ValueError("payback_months phải >= 1.")
    need_ln_thang = float(capital) / float(payback_months) + float(overheads_month)
    gap_ln = max(0.0, need_ln_thang - float(current_ln))
    comp = composite_profit_after_mkt_per_unit(ranges)
    units_total = 0.0 if comp <= 0 else gap_ln / comp

    chi_tiet = []
    if units_total > 0:
        for r in ranges:
            chi_tiet.append({
                "ten": r["ten"],
                "ty_le": float(r["ty_le"]),
                "units_bo_sung": units_total * (float(r["ty_le"]) / 100.0)
            })

    return {
        "target_ln": need_ln_thang,
        "gap_ln": gap_ln,
        "units_bo_sung": max(0.0, units_total),
        "chi_tiet": chi_tiet
    }

# ============== What-if overrides ==============
def apply_whatif_overrides(
    ranges: List[Dict[str, Any]],
    price_override: Optional[Dict[str, float]] = None,
    cogs_pct_override: Optional[Dict[str, float]] = None,
    mix_override: Optional[Dict[str, float]] = None
) -> List[Dict[str, Any]]:
    """
    Ghi đè nhanh cấu hình theo từng range (nếu có):
      - giá bán
      - %COGS
      - %mix
    Không tính lại metrics ở đây; sau khi override, hãy gọi apply_marketing_global(...).
    """
    for r in ranges:
        ten = r["ten"]
        if price_override and ten in price_override and price_override[ten] is not None:
            r["gia_ban"] = float(price_override[ten])
        if cogs_pct_override and ten in cogs_pct_override and cogs_pct_override[ten] is not None:
            r["cogs_pct"] = float(cogs_pct_override[ten])
        if mix_override and ten in mix_override and mix_override[ten] is not None:
            r["ty_le"] = float(mix_override[ten])
    # Sau khi mix đổi, bạn có thể muốn re-validate tổng 100% ở tầng gọi.
    return ranges
