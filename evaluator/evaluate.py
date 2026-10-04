"""Formal evaluator engine: checks machine-readable reward conditions against the
final database state. Runs INSIDE the backend container with the bench python env.

    python evaluate.py --task /tmp/task.json --out /tmp/result.json

The agent never sees this file or the task condition JSON. All conditions must
hold for reward = 1.

Task JSON schema (produced from tasks_144.jsonl entries):
{
  "task_id": "F04-N-I1",
  "reward_conditions": {
    "exists":      [{"ref": "wo1", "doctype": "Work Order", "filters": {...},
                      "count_gte": 1, "count_le": 1}],
    "fields":      [{"ref": "wo1", "doctype": "Work Order",
                      "fields": {"qty": 50, "status": ["Draft", "Not Started"]}}],
    "child_rows":  [{"ref": "wo1", "child_field": "items",
                      "rows": [{"item_code": "RM-A01", "qty": 20}]}],
    "state":       [{"ref": "wo1", "docstatus": 1, "workflow_state": "Completed"}],
    "stock":       [{"item": "PREP-A", "warehouse": "FG-WH - OPL", "qty_gte": 40}],
    "preserved":   {"Item": ["PREP-B", "RM-A01"], "BOM": ["any:PREP-A"]},
    "not_exists":  [{"doctype": "Stock Entry", "filters": {...}, "count_eq": 0}]
  }
}
"filters" values may be:
  - scalars (exact match)
  - ["in", v1, v2, ...]           -> IN list
  - ["like", "%x%"]               -> LIKE
  - [">=", v] / ["<=", v] / [">", v] / ["<", v]
  - ["!=", v]
"preserved" entries may be exact names, or "any:<filters-dict-json>" meaning
"at least one document matching filters must still exist".
"""
import argparse
import json
import sys
import traceback

import frappe

TOL = 1e-4


def _filter_term(k, v):
    if isinstance(v, list) and v and isinstance(v[0], str) and v[0] in (
            "in", "like", ">=", "<=", ">", "<", "!=", "not in", "between"):
        return [k, v[0], v[1:]] if v[0] in ("in", "not in", "between") else [k, v[0], v[1]]
    return [k, "=", v]


def _frappe_filters(filters):
    out = []
    for k, v in (filters or {}).items():
        out.append(tuple(_filter_term(k, v)))
    return out


def _doc_of(dt, filters):
    names = frappe.get_all(dt, filters=_frappe_filters(filters), pluck="name", order_by="creation asc")
    return (names[0] if names else None), names


def cond_exists(c, refs):
    n = frappe.db.count(c["doctype"], filters=_frappe_filters(c.get("filters", {})))
    lo = c.get("count_gte", 1)
    hi = c.get("count_le", 10 ** 9)
    ok = lo <= n <= hi
    if ok and c.get("ref"):
        first, _ = _doc_of(c["doctype"], c.get("filters", {}))
        if first:
            refs[c["ref"]] = first
    return ok, f"count={n} want [{lo},{hi if hi < 10**9 else 'inf'}]"


def cond_fields(c, refs):
    doc = frappe.get_doc(c["doctype"], refs[c["ref"]])
    bad = []
    for f, want in (c.get("fields") or {}).items():
        got = doc.get(f)
        if isinstance(want, list) and want and want[0] in ("in", ">=", "<=", ">", "<", "!="):
            op = want[0]
            target = want[1]
            if op == "in":
                okf = got in want[1:]
            elif op == ">=":
                okf = got is not None and got >= target
            elif op == "<=":
                okf = got is not None and got <= target
            elif op == ">":
                okf = got is not None and got > target
            elif op == "<":
                okf = got is not None and got < target
            else:
                okf = got != target
        elif isinstance(want, str) and want.startswith("~"):
            import re
            okf = bool(re.match(want[1:], str(got or "")))
        elif isinstance(want, (int, float)) and isinstance(got, (int, float)):
            okf = abs(got - want) <= TOL
        else:
            okf = got == want
        if not okf:
            bad.append(f"{f}: got {got!r} want {want!r}")
    return not bad, "; ".join(bad) or "ok"


def cond_child_rows(c, refs):
    doc = frappe.get_doc(c["doctype"], refs[c["ref"]])
    rows = doc.get(c["child_field"]) or []
    msgs = []
    ok = True
    for want in c.get("rows", []):
        hit = any(all(_eq(row.get(k), v) for k, v in want.items()) for row in rows)
        ok &= hit
        if not hit:
            msgs.append(f"missing child row {want}")
    if c.get("count_exact") is not None:
        ok &= len(rows) == c["count_exact"]
        if not ok:
            msgs.append(f"child rows {len(rows)} != {c['count_exact']}")
    if c.get("count_gte") is not None:
        ok &= len(rows) >= c["count_gte"]
    return ok, "; ".join(msgs) or f"rows={len(rows)}"


def _eq(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= TOL
    return a == b


def cond_state(c, refs):
    doc = frappe.get_doc(c["doctype"], refs[c["ref"]])
    bad = []
    if c.get("docstatus") is not None and doc.docstatus != c["docstatus"]:
        bad.append(f"docstatus={doc.docstatus} want {c['docstatus']}")
    if c.get("status") and doc.get("status") != c["status"]:
        bad.append(f"status={doc.get('status')} want {c['status']}")
    if c.get("workflow_state") and doc.get("workflow_state") != c["workflow_state"]:
        bad.append(f"workflow_state={doc.get('workflow_state')} want {c['workflow_state']}")
    return not bad, "; ".join(bad) or "ok"


def cond_stock(c, refs):
    row = frappe.db.sql(
        "SELECT actual_qty FROM `tabBin` WHERE item_code=%(i)s AND warehouse=%(w)s",
        {"i": c["item"], "w": c["warehouse"]}, as_dict=True)
    got = row[0]["actual_qty"] if row else 0
    if c.get("qty") is not None:
        ok = abs(got - c["qty"]) <= TOL
        return ok, f"bin={got} want {c['qty']}"
    if c.get("qty_gte") is not None:
        return got >= c["qty_gte"] - TOL, f"bin={got} want >= {c['qty_gte']}"
    if c.get("qty_le") is not None:
        return got <= c["qty_le"] + TOL, f"bin={got} want <= {c['qty_le']}"
    return True, f"bin={got}"


def cond_not_exists(c, refs):
    n = frappe.db.count(c["doctype"], filters=_frappe_filters(c.get("filters", {})))
    ok = n == c.get("count_eq", 0)
    return ok, f"count={n} want {c.get('count_eq', 0)}"


def check_preserved(preserved):
    msgs, ok = [], True
    for dt, entries in (preserved or {}).items():
        for e in entries:
            if e.startswith("any:"):
                filters = json.loads(e[4:])
                n = frappe.db.count(dt, filters=_frappe_filters(filters))
                if n < 1:
                    ok = False
                    msgs.append(f"preserved missing {dt} matching {filters}")
            else:
                if not frappe.db.exists(dt, e):
                    ok = False
                    msgs.append(f"preserved missing {dt}: {e}")
    return ok, "; ".join(msgs) or "ok"


def evaluate(task):
    rc = task["reward_conditions"]
    refs = {}
    results = []

    for c in rc.get("exists", []):
        results.append(("exists", c.get("ref") or c["doctype"], *cond_exists(c, refs)))
    for c in rc.get("not_exists", []):
        results.append(("not_exists", c.get("doctype"), *cond_not_exists(c, refs)))
    for c in rc.get("fields", []):
        results.append(("fields", c.get("ref"), *cond_fields(c, refs)))
    for c in rc.get("child_rows", []):
        results.append(("child_rows", c.get("ref"), *cond_child_rows(c, refs)))
    for c in rc.get("state", []):
        results.append(("state", c.get("ref"), *cond_state(c, refs)))
    for c in rc.get("stock", []):
        results.append(("stock", f"{c['item']}@{c['warehouse']}", *cond_stock(c, refs)))
    ok_pres, msg_pres = check_preserved(rc.get("preserved"))
    results.append(("preserved", "-", ok_pres, msg_pres))

    failed = [f"{kind}:{what}: {msg}" for kind, what, ok, msg in results if not ok]
    reward = 1 if not failed else 0
    return {
        "task_id": task.get("task_id"),
        "reward": reward,
        "n_conditions": len(results),
        "failed": failed,
        "details": [{"kind": k, "what": w, "ok": ok, "msg": m} for k, w, ok, m in results],
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--site", default=None)
    a = ap.parse_args()
    try:
        frappe.init(site=a.site or "frontend", sites_path="/home/frappe/frappe-bench/sites")
        frappe.connect()
        task = json.load(open(a.task, encoding="utf-8"))
        result = evaluate(task)
    except Exception:
        result = {"task_id": task.get("task_id") if "task" in dir() else None,
                  "reward": 0, "error": traceback.format_exc()[-1500:]}
    json.dump(result, open(a.out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print("EVAL_REWARD", result.get("reward"), "FAILED", len(result.get("failed", [])))
    frappe.destroy()
