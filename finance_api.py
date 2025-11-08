# finance_api.py
import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from core import (
    validate_ranges_base, apply_marketing_global, b11_reference,
    calc_b12, calc_b13_extra_units, apply_whatif_overrides
)

# Serve static files (index3.html nằm trong ./static)
app = Flask(__name__, static_folder='static', static_url_path='')
# CORS: cho phép tất cả trong giai đoạn dev; khi cần, đổi origins thành list các domain ngrok + localhost
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ---------- STATIC / FRONTEND ----------
from flask import send_file

@app.route("/")
def home():
    return send_file("index3.html")  # đường dẫn tính từ thư mục bạn chạy lệnh


# (tuỳ chọn) healthcheck cho ngrok
@app.route("/health")
def health():
    return {"ok": True}, 200

# ---------- API ----------
@app.route("/api/v1/project", methods=["POST"])
def api_project():
    data = request.get_json(force=True)

    capital = float(data["capital"])
    ranges = validate_ranges_base(data["ranges"])
    mkt_pct = float(data.get("marketing_global_pct", 0.0))

    ranges = apply_marketing_global(ranges, mkt_pct)

    oh = data.get("overheads", {}) or {}
    overheads_month = float(oh.get("salary", 0) + oh.get("fixed", 0) + oh.get("others", 0))
    payback_months = int(data.get("payback_months", 12))

    ref = b11_reference(ranges, capital, payback_months, overheads_month)
    return jsonify({
        "ok": True,
        "ranges": ranges,
        "overheads": {"total_per_month": overheads_month},
        "payback_months": payback_months,
        "b11": ref
    })

@app.route("/api/v1/b12", methods=["POST"])
def api_b12():
    data = request.get_json(force=True)
    capital = float(data["capital"])
    ranges = data["ranges"]
    overheads_month = float(data["overheads_month"])
    units_by_range = data.get("units_by_range", {}) or {}

    b12 = calc_b12(ranges, units_by_range, overheads_month, capital)
    return jsonify({"ok": True, **b12})

@app.route("/api/v1/b13", methods=["POST"])
def api_b13():
    data = request.get_json(force=True)
    capital = float(data["capital"])
    ranges = data["ranges"]
    overheads_month = float(data["overheads_month"])
    payback_months = int(data["payback_months"])
    units_by_range = data.get("units_by_range", {}) or {}

    b12 = calc_b12(ranges, units_by_range, overheads_month, capital)
    b13 = calc_b13_extra_units(ranges, capital, payback_months, overheads_month, b12["ln_sau_mkt_thang"])
    return jsonify({"ok": True, "A": {"target_ln": b12["ln_sau_mkt_thang"], **b12}, "B": b13})

@app.route("/api/v1/what-if", methods=["POST"])
def api_what_if():
    data = request.get_json(force=True)
    capital = float(data["capital"])
    ranges = data["ranges"]

    # Overrides (tuỳ chọn)
    mkt_pct = data.get("marketing_global_pct")
    if mkt_pct is not None:
        ranges = apply_marketing_global(ranges, float(mkt_pct))

    price_ov = data.get("price_override")
    cogs_ov  = data.get("cogs_pct_override")
    mix_ov   = data.get("mix_override")
    if any([price_ov, cogs_ov, mix_ov]):
        ranges = apply_whatif_overrides(ranges, price_ov, cogs_ov, mix_ov)

    overheads_month = float(data.get("overheads_month", 0))
    if "overheads_month_override" in data and data["overheads_month_override"] is not None:
        overheads_month = float(data["overheads_month_override"])

    payback_months = int(data.get("payback_months", 12))
    if "payback_months_override" in data and data["payback_months_override"] is not None:
        payback_months = int(data["payback_months_override"])

    units_by_range = data.get("units_by_range", {}) or {}
    b12 = calc_b12(ranges, units_by_range, overheads_month, capital)
    b13 = calc_b13_extra_units(ranges, capital, payback_months, overheads_month, b12["ln_sau_mkt_thang"])

    return jsonify({"ok": True, "b12": b12, "b13": b13})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)
