"""Apply a deterministic task fixture (initial state) inside the ERPNext backend.

Runs INSIDE the backend container with the bench python env, cwd=frappe-bench:
    python apply_task_fixture.py --fixture /tmp/fixture.json

Fixture JSON (declarative, generated from tasks_144.jsonl entries):
{
  "task_id": "F05-P-I1",
  "create": [
    {"doctype": "Work Order",
     "fields": {"company": "Open Preparation Lab", "production_item": "PREP-A",
                "qty": 50, "fg_warehouse": "FG-WH - OPL", "wip_warehouse": "WIP-WH - OPL",
                "bom_no": "any:BOM", "stock_uom": "Nos"},
     "submit": true}
  ],
  "batches": [{"item": "PREP-A", "batch_id": "PREP-A-B0001",
               "manufacturing_date": "2026-09-01", "expiry_date": "2027-09-01"}],
  "stock_entries": [
    {"purpose": "Material Transfer", "company": "Open Preparation Lab",
     "from_warehouse": "RM-WH - OPL", "to_warehouse": "WIP-WH - OPL",
     "items": [{"item_code": "RM-A01", "qty": 20}]}
  ],
  "patches": [{"doctype": "Work Order", "match": {...}, "fields": {...}}]
}

Idempotency: creation steps are skipped when an identical marker already exists
(marker = doctype + key fields recorded under "marker" in the entry).
"""
import argparse
import hashlib
import json
import os

import frappe

COMPANY_DEFAULT = "Open Preparation Lab"


def _abbr(name):
    return f"{name} - OPL" if " - " not in name and not name.endswith("- OPL") else name


def _resolve_warehouses(fields):
    for k in ("fg_warehouse", "wip_warehouse", "source_warehouse", "target_warehouse",
              "from_warehouse", "to_warehouse", "warehouse", "set_warehouse"):
        if k in fields and isinstance(fields[k], str) and " - " not in fields[k]:
            fields[k] = _abbr(fields[k])
    return fields


def _marker(entry):
    m = entry.get("marker") or {"doctype": entry.get("doctype"), "fields": entry.get("fields", {})}
    raw = json.dumps(m, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _already_applied(marker_id):
    return frappe.db.exists("Comment", {
        "comment_type": "Fixture Marker", "reference_doctype": "Task Fixture",
        "content": marker_id,
    })


def _stamp(marker_id):
    frappe.get_doc({
        "doctype": "Comment", "comment_type": "Fixture Marker",
        "reference_doctype": "Task Fixture", "reference_name": "Task Fixture",
        "content": marker_id, "subject": "fixture",
    }).insert(ignore_permissions=True)


def _make_doc(entry):
    dt = entry["doctype"]
    fields = _resolve_warehouses(dict(entry.get("fields", {})))
    doc = frappe.get_doc({"doctype": dt, **fields})
    if entry.get("children"):
        for child_field, rows in entry["children"].items():
            for row in rows:
                doc.append(child_field, row)
    return doc


def create_docs(entries, log):
    for e in entries or []:
        mid = _marker(e)
        if _already_applied(mid):
            log.append(f"skip create {e['doctype']} (marker {mid})")
            continue
        doc = _make_doc(e)
        doc.insert(ignore_permissions=True)
        if e.get("submit"):
            doc.submit()
        frappe.db.commit()
        _stamp(mid)
        frappe.db.commit()
        log.append(f"created {e['doctype']} {doc.name} (submit={bool(e.get('submit'))})")


def create_batches(entries, log):
    for b in entries or []:
        bid = b["batch_id"]
        if frappe.db.exists("Batch", bid):
            log.append(f"skip batch {bid}")
            continue
        frappe.get_doc({
            "doctype": "Batch", "batch_id": bid, "item": b["item"],
            "manufacturing_date": b.get("manufacturing_date"),
            "expiry_date": b.get("expiry_date"),
        }).insert(ignore_permissions=True)
        frappe.db.commit()
        log.append(f"created batch {bid}")


def make_stock_entries(entries, log):
    for e in entries or []:
        mid = _marker(e)
        if _already_applied(mid):
            log.append(f"skip stock entry (marker {mid})")
            continue
        purpose = e.get("purpose", "Material Transfer")
        fields = _resolve_warehouses(dict(e.get("fields", {})))
        doc = frappe.get_doc({
            "doctype": "Stock Entry", "stock_entry_type": purpose, "purpose": purpose,
            "company": e.get("company", COMPANY_DEFAULT), **fields,
        })
        for row in e["items"]:
            item = {
                "item_code": row["item_code"], "qty": row["qty"],
                "s_warehouse": _abbr(e["from_warehouse"]) if e.get("from_warehouse") else None,
                "t_warehouse": _abbr(e["to_warehouse"]) if e.get("to_warehouse") else None,
            }
            if row.get("batch_no"):
                item["batch_no"] = row["batch_no"]
                item["use_serial_batch_fields"] = 1
            if e.get("work_order"):
                item["work_order"] = e["work_order"]
            doc.append("items", {k: v for k, v in item.items() if v})
        doc.insert(ignore_permissions=True)
        doc.submit()
        frappe.db.commit()
        _stamp(mid)
        frappe.db.commit()
        log.append(f"created stock entry {doc.name} ({purpose})")


def apply_patches(entries, log):
    for p in entries or []:
        names = frappe.get_all(p["doctype"], filters=[tuple(f) for f in _as_filters(p["match"])], pluck="name")
        for n in names:
            frappe.db.set_value(p["doctype"], n, p["fields"], update_modified=False)
        frappe.db.commit()
        log.append(f"patched {p['doctype']} x{len(names)}: {p['fields']}")


def _as_filters(match):
    out = []
    for k, v in (match or {}).items():
        if isinstance(v, list) and v and isinstance(v[0], str) and v[0] in ("in", "like", ">=", "<=", "!=", ">", "<"):
            out.append((k, v[0], v[1]))
        else:
            out.append((k, "=", v))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--site", default="frontend")
    a = ap.parse_args()
    fx = json.load(open(a.fixture, encoding="utf-8"))
    log = [f"applying fixture {fx.get('task_id')}"]
    try:
        create_docs(fx.get("create"), log)
        create_batches(fx.get("batches"), log)
        make_stock_entries(fx.get("stock_entries"), log)
        apply_patches(fx.get("patches"), log)
        result = {"task_id": fx.get("task_id"), "ok": True, "log": log}
    except Exception as e:
        import traceback
        result = {"task_id": fx.get("task_id"), "ok": False,
                  "error": traceback.format_exc()[-1200:], "log": log}
    json.dump(result, open(a.out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    frappe.destroy()
