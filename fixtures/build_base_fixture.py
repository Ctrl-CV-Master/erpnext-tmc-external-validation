"""Build the synthetic "Open Preparation Lab" base fixture inside the ERPNext backend.

Run INSIDE the backend container with the bench python env, cwd=frappe-bench:
    python3 build_base_fixture.py              # build masters + opening stock + print hash
    python3 build_base_fixture.py --hash-only  # print current state hash only

Site is taken from $SITE (default: frontend). Idempotent and deterministic.
"""
import hashlib
import json
import os
import sys

import frappe

# frappe's RotatingFileHandler needs its log dirs to exist; different frappe
# versions derive the path differently, so create every candidate up front.
import os as _os
_site = _os.environ.get("SITE", "frontend")
for _d in (
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    _os.path.join("/home/frappe/frappe-bench", _site, "logs"),
    _os.path.join("/home/frappe/frappe-bench", "sites", _site, "logs"),
    "/home/frappe/frappe-bench/sites/logs",
):
    try:
        _os.makedirs(_d, exist_ok=True)
    except OSError:
        pass

COMPANY = "Open Preparation Lab"
ABBR = "OPL"
CURRENCY = "CNY"
COUNTRY = "China"
SITE = os.environ.get("SITE", "frontend")

FINISHED = {
    "PREP-A": ("Liquid Preparation A", "ROUTE-LIQUID", {"RM-A01": 20, "RM-A02": 4, "RM-A07": 1}),
    "PREP-B": ("Liquid Preparation B", "ROUTE-LIQUID", {"RM-A02": 15, "RM-A03": 6, "RM-A08": 2, "RM-A11": 1}),
    "PREP-C": ("Liquid Preparation C", "ROUTE-LIQUID", {"RM-A01": 30, "RM-A04": 3, "RM-A09": 2}),
    "PREP-D": ("Semi-solid Preparation D", "ROUTE-SEMI", {"RM-A05": 10, "RM-A06": 5, "RM-A12": 1}),
    "PREP-E": ("Semi-solid Preparation E", "ROUTE-SEMI", {"RM-A03": 12, "RM-A06": 8, "RM-A10": 3, "RM-A13": 1}),
    "PREP-F": ("Semi-solid Preparation F", "ROUTE-SEMI", {"RM-A04": 9, "RM-A05": 7, "RM-A14": 2, "RM-A15": 1}),
}
RAW_ITEMS = [f"RM-A{n:02d}" for n in range(1, 19)]
BATCHED_RM = {"RM-A01", "RM-A02", "RM-A03", "RM-A04", "RM-A05", "RM-A06"}
RM_RATE = {f"RM-A{n:02d}": 5 + (n * 7) % 25 for n in range(1, 19)}
FG_RATE = {"PREP-A": 88, "PREP-B": 96, "PREP-C": 105, "PREP-D": 72, "PREP-E": 118, "PREP-F": 92}
WAREHOUSES = ["RM-WH", "WIP-WH", "FG-WH", "QC-HOLD"]
WORKSTATIONS = ["WS-WEIGH", "WS-MIX", "WS-FILL", "WS-PACK"]
OPERATIONS = [
    ("Weighing", "WS-WEIGH", 10),
    ("Mixing", "WS-MIX", 30),
    ("Filling", "WS-FILL", 15),
    ("Packaging", "WS-PACK", 12),
]
ROUTE_TIMES = {
    "ROUTE-LIQUID": {"Weighing": 10, "Mixing": 30, "Filling": 15, "Packaging": 12},
    "ROUTE-SEMI": {"Weighing": 12, "Mixing": 35, "Filling": 18, "Packaging": 15},
}
QI_PARAMETERS = ["Appearance", "pH Value", "Fill Volume", "Viscosity", "Package Integrity"]
QI_TEMPLATES = {
    "QI-LIQUID": ["Appearance", "pH Value", "Fill Volume"],
    "QI-SEMI": ["Appearance", "Viscosity"],
    "QI-PACK": ["Package Integrity"],
}
OPENING_RM_QTY = 1000
UOM = "Nos"


def commit():
    frappe.db.commit()


def ensure(dt, name, values=None):
    if frappe.db.exists(dt, name):
        print(f"exists  {dt}: {name}")
        return frappe.get_doc(dt, name)
    doc = frappe.get_doc({"doctype": dt, **(values or {})})
    doc.insert(ignore_permissions=True)
    commit()
    print(f"created {dt}: {name}")
    return doc


def table_field(dt, keyword):
    """First Table field on dt whose fieldname or child-doctype options contains keyword."""
    for f in frappe.get_meta(dt).fields:
        fn = (f.fieldname or "").lower()
        op = (f.options or "").lower()
        if f.fieldtype == "Table" and (keyword in fn or keyword in op):
            return f
    raise ValueError(f"no Table field matching '{keyword}' on {dt}")


def build():
    frappe.flags.mute_emails = True

    # --- master fixtures the setup wizard would normally load --------------------
    for wt in ("Transit", "Stores", "Work In Progress", "Finished Goods",
               "Rejection", "Quarantine", "Reserved", "Supplier", "Customer"):
        ensure("Warehouse Type", wt, {"warehouse_type": wt})

    # --- company ---------------------------------------------------------------
    if not frappe.db.exists("Company", COMPANY):
        frappe.get_doc({
            "doctype": "Company", "company_name": COMPANY, "abbr": ABBR,
            "default_currency": CURRENCY, "country": COUNTRY,
        }).insert(ignore_permissions=True)
        commit()
    print("company ready")
    try:
        frappe.db.set_single_value("System Settings", "default_company", COMPANY)
        frappe.db.set_single_value("System Settings", "default_currency", CURRENCY)
        commit()
    except Exception as e:
        print("system settings defaults skipped:", e)

    # --- item groups / uom -------------------------------------------------------
    for grp in ("Preparations", "Raw Materials"):
        ensure("Item Group", grp, {"item_group_name": grp, "parent_item_group": "All Item Groups", "is_group": 0})
    if not frappe.db.exists("UOM", UOM):
        frappe.get_doc({"doctype": "UOM", "uom_name": UOM}).insert(ignore_permissions=True)
        commit()

    # --- warehouses -----------------------------------------------------------------
    group_whs = frappe.get_all("Warehouse", filters={"company": COMPANY, "is_group": 1}, pluck="name")
    group_wh = next((w for w in group_whs if w.startswith("All Warehouses")), group_whs[0] if group_whs else None)
    for wh in WAREHOUSES:
        ensure("Warehouse", f"{wh} - {ABBR}", {
            "warehouse_name": wh, "company": COMPANY, "parent_warehouse": group_wh, "is_group": 0,
        })

    # --- items ------------------------------------------------------------------------
    for code, (iname, _route, _rms) in FINISHED.items():
        ensure("Item", code, {
            "item_code": code, "item_name": iname, "item_group": "Preparations",
            "stock_uom": UOM, "is_stock_item": 1, "is_sales_item": 1, "is_purchase_item": 0,
            "has_batch_no": 1, "create_new_batch": 1, "batch_number_series": f"{code}-B.####",
            "standard_rate": FG_RATE[code], "description": f"Synthetic finished preparation {code}",
        })
    for code in RAW_ITEMS:
        vals = {
            "item_code": code, "item_name": f"Synthetic Raw Material {code[-3:]}", "item_group": "Raw Materials",
            "stock_uom": UOM, "is_stock_item": 1, "is_sales_item": 0, "is_purchase_item": 1,
            "standard_rate": RM_RATE[code], "description": f"Synthetic raw material {code}",
        }
        if code in BATCHED_RM:
            vals.update({"has_batch_no": 1, "create_new_batch": 1, "batch_number_series": f"{code}-B.####"})
        ensure("Item", code, vals)

    # --- workstations / operations -------------------------------------------------------
    for ws in WORKSTATIONS:
        ensure("Workstation", ws, {"workstation_name": ws, "production_capacity": 1})
    ws_field = frappe.get_meta("Operation").get_field("workstation")
    for op, ws, _t in OPERATIONS:
        doc = ensure("Operation", op, {"operation": op})
        if ws_field and not doc.get("workstation"):
            doc.set("workstation", ws)
            doc.save(ignore_permissions=True)
            commit()

    # --- quality inspection parameters + templates ------------------------------------------
    for p in QI_PARAMETERS:
        ensure("Quality Inspection Parameter", p, {"parameter": p})
    for tpl, params in QI_TEMPLATES.items():
        if frappe.db.exists("Quality Inspection Template", tpl):
            print(f"exists  Quality Inspection Template: {tpl}")
            continue
        tf = table_field("Quality Inspection Template", "parameter")
        frappe.get_doc({
            "doctype": "Quality Inspection Template", "quality_inspection_template_name": tpl,
            tf.fieldname: [{"parameter": p} for p in params],
        }).insert(ignore_permissions=True)
        commit()
        print(f"created Quality Inspection Template: {tpl}")

    # --- routings ------------------------------------------------------------------------------
    rf = table_field("Routing", "operation")
    rmeta = frappe.get_meta(rf.options)
    for route in ("ROUTE-LIQUID", "ROUTE-SEMI"):
        if frappe.db.exists("Routing", route):
            print(f"exists  Routing: {route}")
            continue
        rows = []
        for i, (op, ws, _t) in enumerate(OPERATIONS, start=1):
            row = {"operation": op, "workstation": ws, "time_in_mins": ROUTE_TIMES[route][op]}
            if rmeta.get_field("sequence_id"):
                row["sequence_id"] = i
            if rmeta.get_field("hour_rate"):
                row["hour_rate"] = 100
            rows.append(row)
        frappe.get_doc({"doctype": "Routing", "routing_name": route, rf.fieldname: rows}).insert(ignore_permissions=True)
        commit()
        print(f"created Routing: {route}")

    # --- opening stock of raw materials (so transfers/manufacture have real stock) ---------------
    if not frappe.db.exists("Stock Reconciliation", {"company": COMPANY, "docstatus": 1}):
        itf = table_field("Stock Reconciliation", "item")
        rows = [{"item_code": c, "warehouse": f"RM-WH - {ABBR}", "qty": OPENING_RM_QTY,
                 "valuation_rate": RM_RATE[c]} for c in RAW_ITEMS]
        doc = frappe.get_doc({"doctype": "Stock Reconciliation", "company": COMPANY,
                              "purpose": "Opening Stock", itf.fieldname: rows})
        doc.insert(ignore_permissions=True)
        doc.submit()
        commit()
        print("created+submitted Stock Reconciliation (opening RM stock)")

    # --- BOMs (after opening stock so valuation rates exist) --------------------------------------
    for code, (_iname, route, rms) in FINISHED.items():
        if frappe.db.exists("BOM", {"item": code, "docstatus": 1}):
            print(f"exists  BOM for {code}")
            continue
        opf = table_field("BOM", "operation")
        itf = table_field("BOM", "item")
        op_rows = []
        for i, (op, ws, _t) in enumerate(OPERATIONS, start=1):
            row = {"operation": op, "workstation": ws, "time_in_mins": ROUTE_TIMES[route][op]}
            if frappe.get_meta(opf.options).get_field("hour_rate"):
                row["hour_rate"] = 100
            if frappe.get_meta(opf.options).get_field("sequence_id"):
                row["sequence_id"] = i
            op_rows.append(row)
        doc = frappe.get_doc({
            "doctype": "BOM", "item": code, "company": COMPANY, "quantity": 1, "uom": UOM,
            "with_operations": 1, "routing": route, "is_active": 1, "is_default": 1,
            "rm_cost_as_per": "Valuation Rate",
            itf.fieldname: [{"item_code": rm, "qty": q, "uom": UOM, "rate": RM_RATE[rm]}
                            for rm, q in rms.items()],
            opf.fieldname: op_rows,
        })
        doc.insert(ignore_permissions=True)
        doc.submit()
        commit()
        print(f"created+submitted BOM for {code}")

    print("BUILD_DONE")


def state_hash():
    parts = {}
    for dt in ("Company", "Item Group", "Item", "Warehouse", "Workstation", "Operation",
               "Routing", "BOM", "Quality Inspection Parameter", "Quality Inspection Template",
               "Stock Reconciliation"):
        try:
            parts[dt] = sorted(frappe.get_all(dt, pluck="name"))
        except Exception as e:
            parts[dt] = f"ERR {e}"
    balances = {}
    try:
        for r in frappe.db.sql(
                "SELECT item_code, warehouse, actual_qty FROM `tabBin` ORDER BY item_code, warehouse",
                as_dict=True):
            balances[f"{r.item_code}|{r.warehouse}"] = round(r.actual_qty, 4)
    except Exception as e:
        balances["ERR"] = str(e)
    parts["Bin"] = balances
    return hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


if __name__ == "__main__":
    frappe.init(site=SITE, sites_path="/home/frappe/frappe-bench/sites")
    frappe.connect()
    if "--hash-only" in sys.argv:
        print("STATE_HASH=" + state_hash())
    else:
        build()
        print("STATE_HASH=" + state_hash())
    frappe.destroy()
