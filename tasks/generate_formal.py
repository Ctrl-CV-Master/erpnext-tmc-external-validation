# -*- coding: utf-8 -*-
"""Generate the formal task set: 24 families x N/P/C x 2 instances = 144 tasks.

Deterministic pre-state names (see fixtures/build_base_fixture.py WO_SPEC):
  MFG-WO-2026-00001..00004   dev drafts (C20, D15, E25, F18)
  00005..00010               F03 submit-existing drafts (A30, B40, C46, D56, E31, F21)
  00011..00016               F04 qty-change drafts (A61, B62, C63, D64, E65, F66)
  00017..00022               F06 date-edit drafts (A81, B82, C83, D84, E85, F86)
  00023..00028               F05 cancel-targets, submitted (A71, B72, C73, D74, E75, F76)
"""
import json
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "formal")

COMPANY = "Open Preparation Lab"
WIP = "WIP-WH - OPL"
FGW = "FG-WH - OPL"
RMW = "RM-WH - OPL"
UOM = "Nos"
FG = "Preparations"
RM = "Raw Materials"

TASKS = []  # list of task dicts


def add(task_id, family, cond, inst, instruction, condition, rewards,
        expect_docstatus=None):
    condition = dict(condition)
    condition["id"] = "C0"
    if expect_docstatus is not None:
        condition["expect_docstatus"] = expect_docstatus
    TASKS.append({
        "task_id": task_id, "dev": False, "family": family,
        "condition": cond, "instance": inst,
        "instruction": instruction,
        "conditions": [condition],
        "reward_conditions": rewards,
    })


def exists(ref, doctype, filters, lo=1, hi=1):
    return {"ref": ref, "doctype": doctype, "filters": filters,
            "count_gte": lo, "count_le": hi}


def not_exists(doctype, filters):
    return {"doctype": doctype, "filters": filters, "count_eq": 0}


WIPF = {"wip_warehouse": WIP, "target_warehouse": FGW, "fg_warehouse": FGW}

# --------------------------------------------------------------- F01/F02 ----
# WO create: N full-info draft; P create+submit; C revised qty + submit,
# not_exists on the nominal quantity.
for fam, item, n_qty, p_qty, c_new, c_old in (
        ("F01", "PREP-A", 33, 35, 37, 33),
        ("F02", "PREP-B", 43, 45, 47, 43)):
    submit_n = fam == "F02"
    add(f"{fam}-N-I1", fam, "N", 1,
        f"在 ERPNext 中为成品 {item} 创建一张 {n_qty} 件的生产工单(Work Order)"
        + ("。创建后请提交(Submit)。" if submit_n else ",保存为草稿。")
        + f"公司 Open Preparation Lab,在制品仓库 {WIP},成品仓库 {FGW}。",
        {"doctype": "Work Order", "kind": "create",
         "fields": {"production_item": item, "qty": n_qty,
                    "company": COMPANY, **WIPF},
         "hint": "Work Order 表单:Production Item、Qty To Manufacture、仓库",
         "invalidates": []},
        {"exists": [exists("wo", "Work Order",
                           {"production_item": item, "qty": n_qty,
                            "docstatus": 1 if submit_n else 0}, hi=10 ** 9)]},
        expect_docstatus=1 if submit_n else None)
    add(f"{fam}-N-I2", fam, "N", 2,
        f"在 ERPNext 中为成品 {item} 创建一张 {n_qty + 1} 件的生产工单(Work Order)"
        + ("。创建后请提交(Submit)。" if submit_n else ",保存为草稿。"),
        {"doctype": "Work Order", "kind": "create",
         "fields": {"production_item": item, "qty": n_qty + 1,
                    "company": COMPANY, **WIPF},
         "hint": "Work Order 表单:Production Item、Qty To Manufacture、仓库",
         "invalidates": []},
        {"exists": [exists("wo", "Work Order",
                           {"production_item": item, "qty": n_qty + 1,
                            "docstatus": 1 if submit_n else 0}, hi=10 ** 9)]},
        expect_docstatus=1 if submit_n else None)
    add(f"{fam}-P-I1", fam, "P", 1,
        f"生产计划要求 {item} 的工单以 {p_qty} 件的规模执行。请创建该工单"
        + ("并直接提交(Submit)。" if submit_n else ",保存为草稿(仓库用默认设置)。"),
        {"doctype": "Work Order", "kind": "create",
         "fields": ({"production_item": item, "qty": p_qty,
                     "company": COMPANY, **WIPF} if submit_n else
                    {"production_item": item, "qty": p_qty, "company": COMPANY}),
         "hint": "创建 Work Order(仓库字段按需补全)",
         "invalidates": []},
        {"exists": [exists("wo", "Work Order",
                           {"production_item": item, "qty": p_qty,
                            "docstatus": 1 if submit_n else 0}, hi=10 ** 9)]},
        expect_docstatus=1 if submit_n else None)
    add(f"{fam}-P-I2", fam, "P", 2,
        f"生产计划要求 {item} 的工单以 {p_qty + 2} 件的规模执行。请创建该工单"
        + ("并直接提交(Submit)。" if submit_n else ",保存为草稿(仓库用默认设置)。"),
        {"doctype": "Work Order", "kind": "create",
         "fields": ({"production_item": item, "qty": p_qty + 2,
                     "company": COMPANY, **WIPF} if submit_n else
                    {"production_item": item, "qty": p_qty + 2, "company": COMPANY}),
         "hint": "创建 Work Order(仓库字段按需补全)",
         "invalidates": []},
        {"exists": [exists("wo", "Work Order",
                           {"production_item": item, "qty": p_qty + 2,
                            "docstatus": 1 if submit_n else 0}, hi=10 ** 9)]},
        expect_docstatus=1 if submit_n else None)
    add(f"{fam}-C-I1", fam, "C", 1,
        f"计划变更:原计划为 {item} 创建 {c_old} 件的工单,现修订为 {c_new} 件。"
        "请按新数量创建工单并提交(Submit)。原数量的已提交工单不应存在。",
        {"doctype": "Work Order", "kind": "create",
         "fields": {"production_item": item, "qty": c_new,
                    "company": COMPANY, **WIPF},
         "hint": f"按修订数量 {c_new} 创建并提交",
         "invalidates": []},
        {"exists": [exists("wo", "Work Order",
                           {"production_item": item, "qty": c_new, "docstatus": 1}, hi=10 ** 9)],
         "not_exists": [not_exists("Work Order",
                                   {"production_item": item, "qty": c_old,
                                    "docstatus": 1})]},
        expect_docstatus=1)
    add(f"{fam}-C-I2", fam, "C", 2,
        f"计划变更:原计划为 {item} 创建 {c_old + 1} 件的工单,现修订为 {c_new + 1} 件。"
        "请按新数量创建工单并提交(Submit)。原数量的已提交工单不应存在。",
        {"doctype": "Work Order", "kind": "create",
         "fields": {"production_item": item, "qty": c_new + 1,
                    "company": COMPANY, **WIPF},
         "hint": f"按修订数量 {c_new + 1} 创建并提交",
         "invalidates": []},
        {"exists": [exists("wo", "Work Order",
                           {"production_item": item, "qty": c_new + 1, "docstatus": 1}, hi=10 ** 9)],
         "not_exists": [not_exists("Work Order",
                                   {"production_item": item, "qty": c_old + 1,
                                    "docstatus": 1})]},
        expect_docstatus=1)

# --------------------------------------------------------------- F03/F04 ----
# route-directed edits of existing drafts.
F03 = [("N-I1", "MFG-WO-2026-00005", "PREP-A", 30, 38),
       ("N-I2", "MFG-WO-2026-00006", "PREP-B", 40, 48),
       ("P-I1", "MFG-WO-2026-00007", "PREP-C", 46, 52),
       ("P-I2", "MFG-WO-2026-00008", "PREP-D", 56, 60),
       ("C-I1", "MFG-WO-2026-00009", "PREP-E", 31, 35),
       ("C-I2", "MFG-WO-2026-00010", "PREP-F", 21, 26)]
for tag, wo, item, old_q, new_q in F03:
    add(f"F03-{tag}", "F03", tag[0], int(tag[-1]),
        f"系统中有一张 {item}、数量 {old_q} 的生产工单草稿(编号 {wo})。"
        f"请打开它并提交(Submit)。"
        if tag[0] == "N" else
        f"工单 {wo}({item},数量 {old_q})的审核已完成,请将其提交(Submit)。",
        {"doctype": "Work Order", "kind": "edit",
         "route": f"/app/work-order/{wo}",
         "match": {"production_item": item, "qty": old_q, "docstatus": 0},
         "fields": {}, "hint": f"打开 {wo} 并提交", "invalidates": []},
        {"exists": [exists("wo", "Work Order",
                           {"production_item": item, "qty": old_q, "docstatus": 1})]},
        expect_docstatus=1)

F04 = [("N-I1", "MFG-WO-2026-00011", "PREP-A", 61, 70),
       ("N-I2", "MFG-WO-2026-00012", "PREP-B", 62, 71),
       ("P-I1", "MFG-WO-2026-00013", "PREP-C", 63, 72),
       ("P-I2", "MFG-WO-2026-00014", "PREP-D", 64, 73),
       ("C-I1", "MFG-WO-2026-00015", "PREP-E", 65, 74),
       ("C-I2", "MFG-WO-2026-00016", "PREP-F", 66, 75)]
for tag, wo, item, old_q, new_q in F04:
    add(f"F04-{tag}", "F04", tag[0], int(tag[-1]),
        f"计划变更:{wo}({item},当前数量 {old_q})的产量修订为 {new_q}。"
        f"请修改数量,保存并提交(Submit)。修订前的数量不应以已提交状态存在。",
        {"doctype": "Work Order", "kind": "edit",
         "route": f"/app/work-order/{wo}",
         "match": {"production_item": item, "qty": old_q, "docstatus": 0},
         "fields": {"qty": new_q},
         "hint": f"数量 {old_q} -> {new_q},然后提交", "invalidates": []},
        {"exists": [exists("wo", "Work Order",
                           {"production_item": item, "qty": new_q, "docstatus": 1})],
         "not_exists": [not_exists("Work Order",
                                   {"production_item": item, "qty": old_q,
                                    "docstatus": 1})]},
        expect_docstatus=1)

# --------------------------------------------------------------- F05/F06 ----
F05 = [("N-I1", "MFG-WO-2026-00023", "PREP-A", 71),
       ("N-I2", "MFG-WO-2026-00024", "PREP-B", 72),
       ("P-I1", "MFG-WO-2026-00025", "PREP-C", 73),
       ("P-I2", "MFG-WO-2026-00026", "PREP-D", 74),
       ("C-I1", "MFG-WO-2026-00027", "PREP-E", 75),
       ("C-I2", "MFG-WO-2026-00028", "PREP-F", 76)]
for tag, wo, item, q in F05:
    add(f"F05-{tag}", "F05", tag[0], int(tag[-1]),
        f"工单 {wo}({item},数量 {q})已被误提交。请将其取消(Cancel)以作废。"
        if tag[0] == "N" else
        f"计划调整:{wo}({item},数量 {q})需要作废,请执行取消(Cancel)。",
        {"doctype": "Work Order", "kind": "edit",
         "route": f"/app/work-order/{wo}",
         "match": {"production_item": item, "qty": q, "docstatus": 1},
         "fields": {}, "hint": f"打开 {wo} 并 Cancel", "invalidates": []},
        {"exists": [exists("wo", "Work Order",
                           {"production_item": item, "qty": q, "docstatus": 2})]},
        expect_docstatus=2)

F06 = [("N-I1", "MFG-WO-2026-00017", "PREP-A", 81),
       ("N-I2", "MFG-WO-2026-00018", "PREP-B", 82),
       ("P-I1", "MFG-WO-2026-00019", "PREP-C", 83),
       ("P-I2", "MFG-WO-2026-00020", "PREP-D", 84),
       ("C-I1", "MFG-WO-2026-00021", "PREP-E", 85),
       ("C-I2", "MFG-WO-2026-00022", "PREP-F", 86)]
for tag, wo, item, q in F06:
    add(f"F06-{tag}", "F06", tag[0], int(tag[-1]),
        f"请打开工单 {wo}({item}),把计划开始时间(Planned Start Date)改为 "
        f"2026-10-20 08:00:00,保存。"
        if tag[0] == "N" else
        f"{wo} 的排产需要后移:请把计划开始时间(Planned Start Date)改为 "
        f"2026-10-20 08:00:00 并保存。",
        {"doctype": "Work Order", "kind": "edit",
         "route": f"/app/work-order/{wo}",
         "match": {"production_item": item, "qty": q, "docstatus": 0},
         "fields": {"planned_start_date": "2026-10-20 08:00:00"},
         "hint": "Planned Start Date 字段", "invalidates": []},
        {"exists": [exists("wo", "Work Order",
                           {"production_item": item, "qty": q,
                            "planned_start_date": "2026-10-20 08:00:00",
                            "docstatus": 0})]})

# ---------------------------------------------------------- F07-F12 Item ----
F07 = [("I1", "PREP-G", "Liquid Preparation G"), ("I2", "PREP-H", "Liquid Preparation H")]
for tag, code, iname in F07:
    add(f"F07-N-{tag}", "F07", "N", int(tag[-1]),
        f"在 ERPNext 中创建新成品物料 {code},物料名称 {iname},物料组 {FG},"
        f"库存单位 {UOM},保存。",
        {"doctype": "Item", "kind": "create",
         "fields": {"item_code": code, "item_name": iname,
                    "item_group": FG, "stock_uom": UOM},
         "hint": "Item 表单:Item Code、Item Name、Item Group、Stock UOM",
         "invalidates": []},
        {"exists": [exists("it", "Item", {"item_code": code})],
         "fields": [{"ref": "it", "doctype": "Item",
                     "fields": {"item_group": FG, "stock_uom": UOM,
                                "item_name": iname}}]})

F08 = [("I1", "RM-A19", "Synthetic Raw Material A19"),
       ("I2", "RM-A20", "Synthetic Raw Material A20")]
for tag, code, iname in F08:
    add(f"F08-N-{tag}", "F08", "N", int(tag[-1]),
        f"在 ERPNext 中创建新原料物料 {code},物料名称 {iname},物料组 {RM},"
        f"库存单位 {UOM},保存。",
        {"doctype": "Item", "kind": "create",
         "fields": {"item_code": code, "item_name": iname,
                    "item_group": RM, "stock_uom": UOM},
         "hint": "Item 表单:Item Code、Item Name、Item Group、Stock UOM",
         "invalidates": []},
        {"exists": [exists("it", "Item", {"item_code": code})],
         "fields": [{"ref": "it", "doctype": "Item",
                     "fields": {"item_group": RM, "item_name": iname}}]})

F09 = [("I1", "RM-A02", "Raw Material A02 (updated)"),
       ("I2", "RM-A03", "Raw Material A03 (updated)")]
for tag, code, new_name in F09:
    add(f"F09-N-{tag}", "F09", "N", int(tag[-1]),
        f"把原料 {code} 的物料名称(Item Name)改为 \"{new_name}\",保存。"
        f"(该物料可直接访问 /app/item/{code})",
        {"doctype": "Item", "kind": "edit", "route": f"/app/item/{code}",
         "match": {"item_code": code},
         "fields": {"item_name": new_name},
         "hint": "Item Name 字段", "invalidates": []},
        {"exists": [exists("it", "Item",
                           {"item_code": code, "item_name": new_name})],
         "not_exists": [not_exists("Item",
                                   {"item_code": code,
                                    "item_name": f"Synthetic Raw Material {code[-3:]}"})]})

F10 = [("I1", "RM-A07"), ("I2", "RM-A09")]
for tag, code in F10:
    add(f"F10-N-{tag}", "F10", "N", int(tag[-1]),
        f"原料 {code} 已停产:请停用(Disabled)该物料并保存。",
        {"doctype": "Item", "kind": "edit", "route": f"/app/item/{code}",
         "match": {"item_code": code},
         "fields": {"disabled": 1},
         "hint": "Disabled 复选框", "invalidates": []},
        {"exists": [exists("it", "Item", {"item_code": code, "disabled": 1})]})

F11 = [("I1", "PREP-D", "Semi-solid preparation D revision C"),
       ("I2", "PREP-E", "Semi-solid preparation E revision C")]
for tag, code, new_desc in F11:
    add(f"F11-N-{tag}", "F11", "N", int(tag[-1]),
        f"把成品 {code} 的描述(Description)改为 \"{new_desc}\",保存。",
        {"doctype": "Item", "kind": "edit", "route": f"/app/item/{code}",
         "match": {"item_code": code},
         "fields": {"description": new_desc},
         "hint": "Description 富文本字段", "invalidates": []},
        {"exists": [exists("it", "Item",
                           {"item_code": code, "description": new_desc})]})

F12 = [("I1", "RM-A10"), ("I2", "RM-A11")]
for tag, code in F12:
    add(f"F12-N-{tag}", "F12", "N", int(tag[-1]),
        f"把原料 {code} 的物料组(Item Group)调整为 {FG},保存。",
        {"doctype": "Item", "kind": "edit", "route": f"/app/item/{code}",
         "match": {"item_code": code},
         "fields": {"item_group": FG},
         "hint": "Item Group 字段", "invalidates": []},
        {"exists": [exists("it", "Item",
                           {"item_code": code, "item_group": FG})]})

# ---------------------------------------------------------- F13/F14 Batch ---
F13 = [("I1", "RM-A02", "RM-A02-B9001"), ("I2", "RM-A03", "RM-A03-B9001")]
for tag, item, bid in F13:
    add(f"F13-N-{tag}", "F13", "N", int(tag[-1]),
        f"为原料 {item} 创建一个新的批次(Batch),批次 ID 为 {bid},保存。",
        {"doctype": "Batch", "kind": "create",
         "fields": {"batch_id": bid, "item": item},
         "hint": "Batch 表单:Batch ID、Item", "invalidates": []},
        {"exists": [exists("b", "Batch", {"batch_id": bid, "item": item}, hi=10 ** 9)]})

F14 = [("I1", "RM-A02-B0001", "Batch adjusted for pilot"),
       ("I2", "RM-A03-B0001", "Batch adjusted for pilot")]
for tag, bid, desc in F14:
    add(f"F14-N-{tag}", "F14", "N", int(tag[-1]),
        f"把批次 {bid} 的描述(Description)改为 \"{desc}\",保存。",
        {"doctype": "Batch", "kind": "edit", "route": f"/app/batch/{bid}",
         "match": {"batch_id": bid},
         "fields": {"description": desc},
         "hint": "Description 字段", "invalidates": []},
        {"exists": [exists("b", "Batch", {"batch_id": bid, "description": desc})]})

# ------------------------------------------------------- F15/F16 UOM/WH -----
F15 = [("I1", "Box of 24"), ("I2", "Pallet of 96")]
for tag, name in F15:
    add(f"F15-N-{tag}", "F15", "N", int(tag[-1]),
        f"在 ERPNext 中创建一个新的计量单位(UOM):{name},保存。",
        {"doctype": "UOM", "kind": "create",
         "fields": {"uom_name": name},
         "hint": "UOM 表单:UOM Name", "invalidates": []},
        {"exists": [exists("u", "UOM", {"uom_name": name}, hi=10 ** 9)]})

F16 = [("I1", "RET-WH"), ("I2", "SAMPLE-WH")]
for tag, wh in F16:
    add(f"F16-N-{tag}", "F16", "N", int(tag[-1]),
        f"在公司 Open Preparation Lab 下创建一个新仓库(Warehouse):{wh},保存。",
        {"doctype": "Warehouse", "kind": "create",
         "fields": {"warehouse_name": wh, "company": COMPANY},
         "hint": "Warehouse 表单:Warehouse Name、Company", "invalidates": []},
        {"exists": [exists("w", "Warehouse", {"warehouse_name": wh}, hi=10 ** 9)]})

# ------------------------------------------------- F17/F18 Customer/Supplier -
F17 = [("I1", "Gamma Lab Client"), ("I2", "Delta Lab Client")]
for tag, name in F17:
    add(f"F17-N-{tag}", "F17", "N", int(tag[-1]),
        f"在 ERPNext 中创建一个新客户(Customer):{name},客户类型 Company,"
        f"客户组 All Customer Groups,保存。",
        {"doctype": "Customer", "kind": "create",
         "fields": {"customer_name": name, "customer_type": "Company",
                    "customer_group": "All Customer Groups"},
         "hint": "Customer 表单:Customer Name、Customer Type、Customer Group",
         "invalidates": []},
        {"exists": [exists("c", "Customer", {"customer_name": name}, hi=10 ** 9)]})

F18 = [("I1", "Gamma Lab Vendor"), ("I2", "Delta Lab Vendor")]
for tag, name in F18:
    add(f"F18-N-{tag}", "F18", "N", int(tag[-1]),
        f"在 ERPNext 中创建一个新供应商(Supplier):{name},"
        f"供应商组 All Supplier Groups,保存。",
        {"doctype": "Supplier", "kind": "create",
         "fields": {"supplier_name": name, "supplier_group": "All Supplier Groups"},
         "hint": "Supplier 表单:Supplier Name、Supplier Group",
         "invalidates": []},
        {"exists": [exists("s", "Supplier", {"supplier_name": name}, hi=10 ** 9)]})

# ------------------------------------------------------- F19 Item Price -----
F19 = [("I1", "RM-A02", 25), ("I2", "RM-A03", 31)]
for tag, item, price in F19:
    add(f"F19-N-{tag}", "F19", "N", int(tag[-1]),
        f"为原料 {item} 创建一个售价(Item Price):价格表 Standard Selling,"
        f"单价 {price},保存。",
        {"doctype": "Item Price", "kind": "create",
         "fields": {"item_code": item, "price_list": "Standard Selling",
                    "selling": 1, "price_list_rate": price},
         "hint": "Item Price 表单:Item Code、Price List、Price List Rate",
         "invalidates": []},
        {"exists": [exists("ip", "Item Price",
                           {"item_code": item, "price_list": "Standard Selling",
                            "price_list_rate": price}, hi=10 ** 9)]})

# ---------------------------------------------------- F20 Workstation -------
F20 = [("I1", "WS-REPACK", 3), ("I2", "WS-STERILIZE", 2)]
for tag, ws, cap in F20:
    add(f"F20-N-{tag}", "F20", "N", int(tag[-1]),
        f"在 ERPNext 中创建一个新工作站(Workstation):{ws},产能 {cap},保存。",
        {"doctype": "Workstation", "kind": "create",
         "fields": {"workstation_name": ws, "production_capacity": cap},
         "hint": "Workstation 表单:Workstation Name、Production Capacity",
         "invalidates": []},
        {"exists": [exists("w", "Workstation", {"workstation_name": ws}, hi=10 ** 9)]})

# ------------------------------------------- F21 SR (hard: child rows) ------
F21 = [("I1", "RM-A07", 100), ("I2", "RM-A08", 120)]
for tag, item, qty in F21:
    add(f"F21-N-{tag}", "F21", "N", int(tag[-1]),
        f"在 ERPNext 中创建一张库存盘点(Stock Reconciliation):盘点 {item} 在"
        f" {RMW} 的数量为 {qty},保存并提交(Submit)。",
        {"doctype": "Stock Reconciliation", "kind": "create",
         "fields": {"company": COMPANY, "item_code": item,
                    "warehouse": RMW, "qty": qty},
         "hint": "Stock Reconciliation:在 items 表中 Add Row 并填 Item、Warehouse、Qty",
         "invalidates": []},
        {"exists": [exists("sr", "Stock Reconciliation", {"docstatus": 1})],
         "child_rows": [{"ref": "sr", "doctype": "Stock Reconciliation",
                         "child_field": "items",
                         "match": {"item_code": item, "qty": qty}}]},
        expect_docstatus=1)

# ---------------------------------------------------------- F22 QI draft ----
F22 = [("I1", "MFG-WO-2026-00001", "PREP-C", "QI-LIQUID"),
       ("I2", "MFG-WO-2026-00002", "PREP-D", "QI-SEMI")]
for tag, wo, item, tpl in F22:
    add(f"F22-N-{tag}", "F22", "N", int(tag[-1]),
        f"为在制工单 {wo}({item})创建一张过程质量检验(Quality Inspection)草稿:"
        f"检验类型 In Process,检验模板 {tpl},保存(不提交)。",
        {"doctype": "Quality Inspection", "kind": "create",
         "fields": {"inspection_type": "In Process", "item_code": item,
                    "reference_type": "Work Order", "reference_name": wo,
                    "quality_inspection_template": tpl},
         "hint": "Inspection Type=In Process、Item Code、Reference、Template",
         "invalidates": []},
        {"exists": [exists("qi", "Quality Inspection",
                           {"item_code": item, "inspection_type": "In Process",
                            "reference_name": wo, "docstatus": 0}, hi=10 ** 9)]})

# ------------------------------------------------ F23/F24 Customer/Supplier -
F23 = [("I1", "Alpha Lab Client", "Alpha Lab Client (renamed)"),
       ("I2", "Beta Lab Client", "Beta Lab Client (renamed)")]
for tag, old, new in F23:
    add(f"F23-N-{tag}", "F23", "N", int(tag[-1]),
        f"把客户 {old} 的客户名称(Customer Name)改为 \"{new}\",保存。",
        {"doctype": "Customer", "kind": "edit", "route": f"/app/customer/{old.replace(' ', '-')}",
         "match": {"customer_name": old},
         "fields": {"customer_name": new},
         "hint": "Customer Name 字段", "invalidates": []},
        {"exists": [exists("c", "Customer", {"customer_name": new})],
         "not_exists": [not_exists("Customer", {"customer_name": old})]})

F24 = [("I1", "Alpha Lab Vendor"), ("I2", "Beta Lab Vendor")]
for tag, name in F24:
    add(f"F24-N-{tag}", "F24", "N", int(tag[-1]),
        f"供应商 {name} 暂停合作:请将其冻结(Is Frozen)并保存。",
        {"doctype": "Supplier", "kind": "edit", "route": f"/app/supplier/{name.replace(' ', '-')}",
         "match": {"supplier_name": name},
         "fields": {"is_frozen": 1},
         "hint": "Is Frozen 复选框", "invalidates": []},
        {"exists": [exists("s", "Supplier", {"supplier_name": name, "is_frozen": 1})]})

# ------------------------------------------- P/C for item-master families ----
# P variants drop the route (agent must locate the record); C variants add a
# not_exists / conflict guard.

# F09 rename: P without route, C plan-change with intermediate name
for tag, code, new_name, old_name in (
        ("I1", "RM-A02", "Raw Material A02 (updated)", "Synthetic Raw Material A02"),
        ("I2", "RM-A03", "Raw Material A03 (updated)", "Synthetic Raw Material A03")):
    add(f"F09-P-{tag}", "F09", "P", int(tag[-1]),
        f"把原料 {code} 的物料名称(Item Name)改为 \"{new_name}\",保存。",
        {"doctype": "Item", "kind": "edit",
         "match": {"item_code": code},
         "fields": {"item_name": new_name},
         "hint": "先找到该物料(可直接访问 /app/item/" + code + ")", "invalidates": []},
        {"exists": [exists("it", "Item",
                           {"item_code": code, "item_name": new_name})]})
    mid = "Raw Material " + code[-3:] + " (interim)"
    add(f"F09-C-{tag}", "F09", "C", int(tag[-1]),
        f"计划两次修订:{code} 的名称先改为 \"{mid}\",最终定为 \"{new_name}\"。"
        f"请确保最终名称为 \"{new_name}\"(中间名不应保留)。",
        {"doctype": "Item", "kind": "edit", "route": f"/app/item/{code}",
         "match": {"item_code": code, "item_name": old_name},
         "fields": {"item_name": new_name},
         "hint": f"最终 Item Name = {new_name}", "invalidates": []},
        {"exists": [exists("it", "Item",
                           {"item_code": code, "item_name": new_name})],
         "not_exists": [not_exists("Item",
                                   {"item_code": code, "item_name": mid})]})

# F10 disable: C = disable the right item, leave the decoy alone
for tag, target, decoy in (("I1", "RM-A12", "RM-A09"), ("I2", "RM-A14", "RM-A15")):
    add(f"F10-C-{tag}", "F10", "C", int(tag[-1]),
        f"计划变更:应停用的原料是 {target} 而不是 {decoy}。"
        f"请停用 {target}(Disabled),并确保 {decoy} 保持启用。",
        {"doctype": "Item", "kind": "edit", "route": f"/app/item/{target}",
         "match": {"item_code": target},
         "fields": {"disabled": 1},
         "hint": f"停用 {target};{decoy} 不动", "invalidates": []},
        {"exists": [exists("it", "Item", {"item_code": target, "disabled": 1})],
         "not_exists": [not_exists("Item", {"item_code": decoy, "disabled": 1})]})

# F11 description: C with not_exists on the original text
for tag, code, new_desc, old_desc in (
        ("I1", "PREP-D", "Semi-solid preparation D revision C",
         "Synthetic finished preparation PREP-D"),
        ("I2", "PREP-E", "Semi-solid preparation E revision C",
         "Synthetic finished preparation PREP-E")):
    add(f"F11-C-{tag}", "F11", "C", int(tag[-1]),
        f"计划变更:{code} 的描述由 \"{old_desc}\" 改为 \"{new_desc}\","
        f"请更新并保存。旧描述不应保留。",
        {"doctype": "Item", "kind": "edit", "route": f"/app/item/{code}",
         "match": {"item_code": code, "description": old_desc},
         "fields": {"description": new_desc},
         "hint": f"Description -> {new_desc}", "invalidates": []},
        {"exists": [exists("it", "Item",
                           {"item_code": code, "description": new_desc})],
         "not_exists": [not_exists("Item",
                                   {"item_code": code, "description": old_desc})]})

# F12 group-move: C moves one item while the decoy must stay put
for tag, target, decoy in (("I1", "RM-A10", "RM-A11"), ("I2", "RM-A13", "RM-A14")):
    add(f"F12-C-{tag}", "F12", "C", int(tag[-1]),
        f"计划变更:{target} 的物料组应调整为 {FG},而 {decoy} 必须保留在 {RM}。"
        f"请只移动 {target} 并保存。",
        {"doctype": "Item", "kind": "edit", "route": f"/app/item/{target}",
         "match": {"item_code": target},
         "fields": {"item_group": FG},
         "hint": f"仅 {target} 移动到 {FG}", "invalidates": []},
        {"exists": [exists("it", "Item", {"item_code": target, "item_group": FG})],
         "not_exists": [not_exists("Item",
                                   {"item_code": decoy, "item_group": FG})]})

# F13 batch-create: C plan-change on the batch id
for tag, item, bid, new_bid in (
        ("I1", "RM-A04", "RM-A04-B9001", "RM-A04-B9002"),
        ("I2", "RM-A05", "RM-A05-B9001", "RM-A05-B9002")):
    add(f"F13-C-{tag}", "F13", "C", int(tag[-1]),
        f"计划变更:为 {item} 创建的批次 ID 由 {bid} 修订为 {new_bid}。"
        f"请按新 ID 创建批次,原 ID 不应存在。",
        {"doctype": "Batch", "kind": "create",
         "fields": {"batch_id": new_bid, "item": item},
         "hint": f"Batch ID = {new_bid}", "invalidates": []},
        {"exists": [exists("b", "Batch", {"batch_id": new_bid, "item": item})],
         "not_exists": [not_exists("Batch", {"batch_id": bid})]})

# F14 batch-edit: P without route
for tag, bid, desc in (("I1", "RM-A02-B0001", "Batch adjusted for pilot"),
                       ("I2", "RM-A03-B0001", "Batch adjusted for pilot")):
    add(f"F14-P-{tag}", "F14", "P", int(tag[-1]),
        f"把批次 {bid} 的描述(Description)改为 \"{desc}\",保存。",
        {"doctype": "Batch", "kind": "edit",
         "match": {"batch_id": bid},
         "fields": {"description": desc},
         "hint": "先找到该批次(/app/batch/" + bid + ")", "invalidates": []},
        {"exists": [exists("b", "Batch", {"batch_id": bid, "description": desc})]})

# F15 UOM: C plan-change
for tag, name, new_name in (("I1", "Box of 24", "Box of 36"),
                            ("I2", "Pallet of 96", "Pallet of 48")):
    add(f"F15-C-{tag}", "F15", "C", int(tag[-1]),
        f"计划变更:计量单位 \"{name}\" 应为 \"{new_name}\"。"
        f"若已按旧名创建请改名;否则直接创建新名的计量单位。旧名不应存在。",
        {"doctype": "UOM", "kind": "create",
         "fields": {"uom_name": new_name},
         "hint": f"UOM Name = {new_name}", "invalidates": []},
        {"exists": [exists("u", "UOM", {"uom_name": new_name})],
         "not_exists": [not_exists("UOM", {"uom_name": name})]})

# F16 Warehouse: C plan-change
for tag, wh, new_wh in (("I1", "RET-WH", "RETURN-WH"),
                        ("I2", "SAMPLE-WH", "SAMPLE-STORE-WH")):
    add(f"F16-C-{tag}", "F16", "C", int(tag[-1]),
        f"计划变更:仓库 \"{wh}\" 的名称应为 \"{new_wh}\"。"
        f"请创建(或改名)为 {new_wh},旧名不应存在。",
        {"doctype": "Warehouse", "kind": "create",
         "fields": {"warehouse_name": new_wh, "company": COMPANY},
         "hint": f"Warehouse Name = {new_wh}", "invalidates": []},
        {"exists": [exists("w", "Warehouse", {"warehouse_name": new_wh})],
         "not_exists": [not_exists("Warehouse", {"warehouse_name": wh})]})

# F17 Customer: C plan-change
for tag, name, new_name in (("I1", "Gamma Lab Client", "Gamma Lab Client (updated)"),
                            ("I2", "Delta Lab Client", "Delta Lab Client (updated)")):
    add(f"F17-C-{tag}", "F17", "C", int(tag[-1]),
        f"计划变更:客户 \"{name}\" 的名称应为 \"{new_name}\"。"
        f"请创建(或改名)为新名称,旧名不应存在。",
        {"doctype": "Customer", "kind": "create",
         "fields": {"customer_name": new_name, "customer_type": "Company",
                    "customer_group": "All Customer Groups"},
         "hint": f"Customer Name = {new_name}", "invalidates": []},
        {"exists": [exists("c", "Customer", {"customer_name": new_name})],
         "not_exists": [not_exists("Customer", {"customer_name": name})]})

# F18 Supplier: C plan-change
for tag, name, new_name in (("I1", "Gamma Lab Vendor", "Gamma Lab Vendor (updated)"),
                            ("I2", "Delta Lab Vendor", "Delta Lab Vendor (updated)")):
    add(f"F18-C-{tag}", "F18", "C", int(tag[-1]),
        f"计划变更:供应商 \"{name}\" 的名称应为 \"{new_name}\"。"
        f"请创建(或改名)为新名称,旧名不应存在。",
        {"doctype": "Supplier", "kind": "create",
         "fields": {"supplier_name": new_name, "supplier_group": "All Supplier Groups"},
         "hint": f"Supplier Name = {new_name}", "invalidates": []},
        {"exists": [exists("s", "Supplier", {"supplier_name": new_name})],
         "not_exists": [not_exists("Supplier", {"supplier_name": name})]})

# F19 Item Price: C revises the rate
for tag, item, price, new_price in (("I1", "RM-A02", 25, 28),
                                    ("I2", "RM-A03", 31, 34)):
    add(f"F19-C-{tag}", "F19", "C", int(tag[-1]),
        f"计划变更:{item} 的标准售价由 {price} 修订为 {new_price}。"
        f"请创建(或更新)价格,旧价格不应存在。",
        {"doctype": "Item Price", "kind": "create",
         "fields": {"item_code": item, "price_list": "Standard Selling",
                    "selling": 1, "price_list_rate": new_price},
         "hint": f"Price List Rate = {new_price}", "invalidates": []},
        {"exists": [exists("ip", "Item Price",
                           {"item_code": item, "price_list": "Standard Selling",
                            "price_list_rate": new_price}, hi=10 ** 9)],
         "not_exists": [not_exists("Item Price",
                                   {"item_code": item, "price_list": "Standard Selling",
                                    "price_list_rate": price})]})

# F20 Workstation: C revises capacity
for tag, ws, cap, new_cap in (("I1", "WS-REPACK", 3, 5),
                              ("I2", "WS-STERILIZE", 2, 4)):
    add(f"F20-C-{tag}", "F20", "C", int(tag[-1]),
        f"计划变更:工作站 \"{ws}\" 的产能由 {cap} 修订为 {new_cap}。"
        f"请创建(或更新),旧产能设置不应存在。",
        {"doctype": "Workstation", "kind": "create",
         "fields": {"workstation_name": ws, "production_capacity": new_cap},
         "hint": f"Production Capacity = {new_cap}", "invalidates": []},
        {"exists": [exists("w", "Workstation",
                           {"workstation_name": ws, "production_capacity": new_cap}, hi=10 ** 9)],
         "not_exists": [not_exists("Workstation",
                                   {"workstation_name": ws,
                                    "production_capacity": cap})]})

# F21 SR: C changes the counted qty (not_exists via child-row check below)
for tag, item, qty, new_qty in (("I1", "RM-A07", 100, 110),
                                ("I2", "RM-A08", 120, 130)):
    add(f"F21-C-{tag}", "F21", "C", int(tag[-1]),
        f"计划变更:盘点数量由 {qty} 修订为 {new_qty}。"
        f"请按新数量完成盘点并提交;提交记录中不应有数量 {qty} 的行。",
        {"doctype": "Stock Reconciliation", "kind": "create",
         "fields": {"company": COMPANY, "item_code": item,
                    "warehouse": RMW, "qty": new_qty},
         "hint": f"Qty = {new_qty}", "invalidates": []},
        {"exists": [exists("sr", "Stock Reconciliation", {"docstatus": 1})],
         "child_rows": [{"ref": "sr", "doctype": "Stock Reconciliation",
                         "child_field": "items",
                         "match": {"item_code": item, "qty": new_qty}}],
         "not_exists": [not_exists("Stock Reconciliation", {"docstatus": 1, "name": "N/A-see-child"})]})

# F22 QI: P without route; C plan-change (template swap on the same WO)
for tag, wo, item, tpl in (("I1", "MFG-WO-2026-00001", "PREP-C", "QI-LIQUID"),
                           ("I2", "MFG-WO-2026-00002", "PREP-D", "QI-SEMI")):
    add(f"F22-P-{tag}", "F22", "P", int(tag[-1]),
        f"为在制工单 {wo}({item})创建过程质量检验草稿:类型 In Process,"
        f"模板 {tpl},保存(不提交)。",
        {"doctype": "Quality Inspection", "kind": "create",
         "fields": {"inspection_type": "In Process", "item_code": item,
                    "reference_type": "Work Order", "reference_name": wo,
                    "quality_inspection_template": tpl},
         "hint": "In Process、Item Code、Reference、Template", "invalidates": []},
        {"exists": [exists("qi", "Quality Inspection",
                           {"item_code": item, "inspection_type": "In Process",
                            "reference_name": wo, "docstatus": 0}, hi=10 ** 9)]})
    add(f"F22-C-{tag}", "F22", "C", int(tag[-1]),
        f"计划变更:工单 {wo} 的过程检验改用全面模板:检验模板应为 QI-PACK"
        f"(原 {tpl})。请创建(或修改)检验草稿并保持草稿状态。",
        {"doctype": "Quality Inspection", "kind": "create",
         "fields": {"inspection_type": "In Process", "item_code": item,
                    "reference_type": "Work Order", "reference_name": wo,
                    "quality_inspection_template": "QI-PACK"},
         "hint": "Template -> QI-PACK", "invalidates": []},
        {"exists": [exists("qi", "Quality Inspection",
                           {"item_code": item, "reference_name": wo,
                            "quality_inspection_template": "QI-PACK",
                            "docstatus": 0}, hi=10 ** 9)],
         "not_exists": [not_exists("Quality Inspection",
                                   {"item_code": item, "reference_name": wo,
                                    "quality_inspection_template": tpl})]})

# F23 Customer-edit: C plan-change
for tag, old, new in (("I1", "Alpha Lab Client", "Alpha Lab Client (renamed)"),
                      ("I2", "Beta Lab Client", "Beta Lab Client (renamed)")):
    add(f"F23-C-{tag}", "F23", "C", int(tag[-1]),
        f"计划变更:客户 \"{old}\" 的名称最终应为 \"{new}\"。"
        f"请改名并确保旧名不再存在。",
        {"doctype": "Customer", "kind": "edit", "route": f"/app/customer/{old.replace(' ', '-')}",
         "match": {"customer_name": old},
         "fields": {"customer_name": new},
         "hint": f"Customer Name -> {new}", "invalidates": []},
        {"exists": [exists("c", "Customer", {"customer_name": new})],
         "not_exists": [not_exists("Customer", {"customer_name": old})]})

# F24 Supplier-edit: C freeze the OTHER supplier (decoy design)
for tag, name, other in (("I1", "Alpha Lab Vendor", "Beta Lab Vendor"),
                         ("I2", "Beta Lab Vendor", "Alpha Lab Vendor")):
    add(f"F24-C-{tag}", "F24", "C", int(tag[-1]),
        f"计划变更:最初以为要冻结的是 {name},确认后需冻结的是 {other}。"
        f"请只冻结 {other},{name} 必须保持未冻结。",
        {"doctype": "Supplier", "kind": "edit", "route": f"/app/supplier/{other.replace(' ', '-')}",
         "match": {"supplier_name": other},
         "fields": {"is_frozen": 1},
         "hint": f"冻结 {other};{name} 保持未冻结", "invalidates": []},
        {"exists": [exists("s", "Supplier", {"supplier_name": other, "is_frozen": 1})],
         "not_exists": [not_exists("Supplier",
                                   {"supplier_name": name, "is_frozen": 1})]})

# ------------------------------------------------- remaining P/C/N fills ----
# F09: N tasks had the wrong condition letter; re-emit as N
for tag, code, new_name in (("I1", "RM-A02", "Raw Material A02 (updated)"),
                            ("I2", "RM-A03", "Raw Material A03 (updated)")):
    add(f"F09-N-{tag}", "F09", "N", int(tag[-1]),
        f"把原料 {code} 的物料名称(Item Name)改为 \"{new_name}\",保存。"
        f"(该物料可直接访问 /app/item/{code})",
        {"doctype": "Item", "kind": "edit", "route": f"/app/item/{code}",
         "match": {"item_code": code},
         "fields": {"item_name": new_name},
         "hint": "Item Name 字段", "invalidates": []},
        {"exists": [exists("it", "Item",
                           {"item_code": code, "item_name": new_name})]})

# F07 Item-create-FG: P partial fields; C create-then-correct (plan change)
for tag, code, iname, new_iname in (
        ("I1", "PREP-G", "Liquid Preparation G", "Liquid Preparation G (rev A)"),
        ("I2", "PREP-H", "Liquid Preparation H", "Liquid Preparation H (rev A)")):
    add(f"F07-P-{tag}", "F07", "P", int(tag[-1]),
        f"在 ERPNext 中创建新成品物料 {code}(物料名称 {iname},物料组 {FG})。"
        f"库存单位等其他必填项按系统默认/惯例补全,保存。",
        {"doctype": "Item", "kind": "create",
         "fields": {"item_code": code, "item_name": iname, "item_group": FG},
         "hint": "Stock UOM 用 Nos", "invalidates": []},
        {"exists": [exists("it", "Item", {"item_code": code})],
         "fields": [{"ref": "it", "doctype": "Item",
                     "fields": {"item_group": FG, "stock_uom": UOM,
                                "item_name": iname}}]})
    add(f"F07-C-{tag}", "F07", "C", int(tag[-1]),
        f"计划变更:物料 {code} 的名称由 \"{iname}\" 修订为 \"{new_iname}\"。"
        f"请创建(或改名),旧名称不应存在。",
        {"doctype": "Item", "kind": "create",
         "fields": {"item_code": code, "item_name": new_iname,
                    "item_group": FG, "stock_uom": UOM},
         "hint": f"Item Name = {new_iname}", "invalidates": []},
        {"exists": [exists("it", "Item",
                           {"item_code": code, "item_name": new_iname})],
         "not_exists": [not_exists("Item", {"item_code": code, "item_name": iname})]})

# F08 Item-create-RM: P partial; C create-then-correct
for tag, code, iname, new_iname in (
        ("I1", "RM-A19", "Synthetic Raw Material A19", "Raw Material A19 (rev A)"),
        ("I2", "RM-A20", "Synthetic Raw Material A20", "Raw Material A20 (rev A)")):
    add(f"F08-P-{tag}", "F08", "P", int(tag[-1]),
        f"在 ERPNext 中创建新原料物料 {code}(物料名称 {iname},物料组 {RM})。"
        f"库存单位等其他必填项按系统默认/惯例补全,保存。",
        {"doctype": "Item", "kind": "create",
         "fields": {"item_code": code, "item_name": iname, "item_group": RM},
         "hint": "Stock UOM 用 Nos", "invalidates": []},
        {"exists": [exists("it", "Item", {"item_code": code})],
         "fields": [{"ref": "it", "doctype": "Item",
                     "fields": {"item_group": RM, "stock_uom": UOM,
                                "item_name": iname}}]})
    add(f"F08-C-{tag}", "F08", "C", int(tag[-1]),
        f"计划变更:物料 {code} 的名称由 \"{iname}\" 修订为 \"{new_iname}\"。"
        f"请创建(或改名),旧名称不应存在。",
        {"doctype": "Item", "kind": "create",
         "fields": {"item_code": code, "item_name": new_iname,
                    "item_group": RM, "stock_uom": UOM},
         "hint": f"Item Name = {new_iname}", "invalidates": []},
        {"exists": [exists("it", "Item",
                           {"item_code": code, "item_name": new_iname})],
         "not_exists": [not_exists("Item", {"item_code": code, "item_name": iname})]})

# F10 disable: P without route
for tag, code in (("I1", "RM-A07"), ("I2", "RM-A09")):
    add(f"F10-P-{tag}", "F10", "P", int(tag[-1]),
        f"原料 {code} 已停产:请停用(Disabled)该物料并保存。",
        {"doctype": "Item", "kind": "edit",
         "match": {"item_code": code},
         "fields": {"disabled": 1},
         "hint": "先找到该物料(/app/item/" + code + ")", "invalidates": []},
        {"exists": [exists("it", "Item", {"item_code": code, "disabled": 1})]})

# F11 description: P without route
for tag, code, new_desc in (
        ("I1", "PREP-D", "Semi-solid preparation D revision C"),
        ("I2", "PREP-E", "Semi-solid preparation E revision C")):
    add(f"F11-P-{tag}", "F11", "P", int(tag[-1]),
        f"把成品 {code} 的描述(Description)改为 \"{new_desc}\",保存。",
        {"doctype": "Item", "kind": "edit",
         "match": {"item_code": code},
         "fields": {"description": new_desc},
         "hint": "先找到该物料(/app/item/" + code + ")", "invalidates": []},
        {"exists": [exists("it", "Item",
                           {"item_code": code, "description": new_desc})]})

# F12 group-move: P without route
for tag, code in (("I1", "RM-A10"), ("I2", "RM-A13")):
    add(f"F12-P-{tag}", "F12", "P", int(tag[-1]),
        f"把原料 {code} 的物料组(Item Group)调整为 {FG},保存。",
        {"doctype": "Item", "kind": "edit",
         "match": {"item_code": code},
         "fields": {"item_group": FG},
         "hint": "先找到该物料(/app/item/" + code + ")", "invalidates": []},
        {"exists": [exists("it", "Item",
                           {"item_code": code, "item_group": FG})]})

# F13 batch-create: P without the exact batch id (agent names it)
for tag, item in (("I1", "RM-A04"), ("I2", "RM-A05")):
    add(f"F13-P-{tag}", "F13", "P", int(tag[-1]),
        f"为原料 {item} 再创建一个新的批次(Batch),保存。"
        f"完成后该物料应至少有两个批次。",
        {"doctype": "Batch", "kind": "create",
         "fields": {"item": item},
         "hint": "Batch ID 可自行命名或留空由系统生成", "invalidates": []},
        {"exists": [exists("b", "Batch", {"item": item}, lo=2, hi=10**9)]})

# F14 batch-edit: C plan-change
for tag, bid, desc, new_desc in (
        ("I1", "RM-A02-B0001", "Batch adjusted for pilot",
         "Batch description revised for formal run"),
        ("I2", "RM-A03-B0001", "Batch adjusted for pilot",
         "Batch description revised for formal run")):
    add(f"F14-C-{tag}", "F14", "C", int(tag[-1]),
        f"计划变更:批次 {bid} 的描述由 \"{desc}\" 修订为 \"{new_desc}\","
        f"请更新,旧描述不应存在。",
        {"doctype": "Batch", "kind": "edit", "route": f"/app/batch/{bid}",
         "match": {"batch_id": bid, "description": desc},
         "fields": {"description": new_desc},
         "hint": f"Description -> {new_desc}", "invalidates": []},
        {"exists": [exists("b", "Batch", {"batch_id": bid, "description": new_desc})],
         "not_exists": [not_exists("Batch", {"batch_id": bid, "description": desc})]})

# F15 UOM: P without the exact-name redundancy (terse instruction)
for tag, name in (("I1", "Box of 24"), ("I2", "Pallet of 96")):
    add(f"F15-P-{tag}", "F15", "P", int(tag[-1]),
        f"请在 ERPNext 中新建计量单位:{name}。",
        {"doctype": "UOM", "kind": "create",
         "fields": {"uom_name": name},
         "hint": "UOM Name", "invalidates": []},
        {"exists": [exists("u", "UOM", {"uom_name": name}, hi=10 ** 9)]})

# F16 Warehouse: P terse
for tag, wh in (("I1", "RET-WH"), ("I2", "SAMPLE-WH")):
    add(f"F16-P-{tag}", "F16", "P", int(tag[-1]),
        f"请在公司 Open Preparation Lab 下新建仓库:{wh}。",
        {"doctype": "Warehouse", "kind": "create",
         "fields": {"warehouse_name": wh, "company": COMPANY},
         "hint": "Warehouse Name、Company", "invalidates": []},
        {"exists": [exists("w", "Warehouse", {"warehouse_name": wh}, hi=10 ** 9)]})

# F17 Customer: P terse
for tag, name in (("I1", "Gamma Lab Client"), ("I2", "Delta Lab Client")):
    add(f"F17-P-{tag}", "F17", "P", int(tag[-1]),
        f"请新建客户:{name}(类型 Company,客户组 All Customer Groups)。",
        {"doctype": "Customer", "kind": "create",
         "fields": {"customer_name": name, "customer_type": "Company",
                    "customer_group": "All Customer Groups"},
         "hint": "Customer Name、Customer Type、Customer Group", "invalidates": []},
        {"exists": [exists("c", "Customer", {"customer_name": name}, hi=10 ** 9)]})

# F18 Supplier: P terse
for tag, name in (("I1", "Gamma Lab Vendor"), ("I2", "Delta Lab Vendor")):
    add(f"F18-P-{tag}", "F18", "P", int(tag[-1]),
        f"请新建供应商:{name}(供应商组 All Supplier Groups)。",
        {"doctype": "Supplier", "kind": "create",
         "fields": {"supplier_name": name, "supplier_group": "All Supplier Groups"},
         "hint": "Supplier Name、Supplier Group", "invalidates": []},
        {"exists": [exists("s", "Supplier", {"supplier_name": name}, hi=10 ** 9)]})

# F19 Item Price: P terse
for tag, item, price in (("I1", "RM-A02", 25), ("I2", "RM-A03", 31)):
    add(f"F19-P-{tag}", "F19", "P", int(tag[-1]),
        f"为原料 {item} 创建售价:价格表 Standard Selling,单价 {price}。",
        {"doctype": "Item Price", "kind": "create",
         "fields": {"item_code": item, "price_list": "Standard Selling",
                    "selling": 1, "price_list_rate": price},
         "hint": "Item Code、Price List、Price List Rate、Selling", "invalidates": []},
        {"exists": [exists("ip", "Item Price",
                           {"item_code": item, "price_list": "Standard Selling",
                            "price_list_rate": price}, hi=10 ** 9)]})

# F20 Workstation: P terse
for tag, ws, cap in (("I1", "WS-REPACK", 3), ("I2", "WS-STERILIZE", 2)):
    add(f"F20-P-{tag}", "F20", "P", int(tag[-1]),
        f"请新建工作站:{ws},产能 {cap}。",
        {"doctype": "Workstation", "kind": "create",
         "fields": {"workstation_name": ws, "production_capacity": cap},
         "hint": "Workstation Name、Production Capacity", "invalidates": []},
        {"exists": [exists("w", "Workstation", {"workstation_name": ws}, hi=10 ** 9)]})

# F21 SR: P terse
for tag, item, qty in (("I1", "RM-A07", 100), ("I2", "RM-A08", 120)):
    add(f"F21-P-{tag}", "F21", "P", int(tag[-1]),
        f"请创建一张库存盘点:盘点 {item} 在 {RMW} 的数量为 {qty},保存并提交。",
        {"doctype": "Stock Reconciliation", "kind": "create",
         "fields": {"company": COMPANY, "item_code": item,
                    "warehouse": RMW, "qty": qty},
         "hint": "items 表:Add Row,填 Item、Warehouse、Qty", "invalidates": []},
        {"exists": [exists("sr", "Stock Reconciliation", {"docstatus": 1})],
         "child_rows": [{"ref": "sr", "doctype": "Stock Reconciliation",
                         "child_field": "items",
                         "match": {"item_code": item, "qty": qty}}]},
        expect_docstatus=1)

# F22 QI: P terse
for tag, item, tpl in (("I1", "RM-A09", "QI-SEMI"), ("I2", "RM-A10", "QI-PACK")):
    add(f"F22-P-{tag}", "F22", "P", int(tag[-1]),
        f"为原料 {item} 创建质量检验草稿:类型 Incoming,模板 {tpl},保存。",
        {"doctype": "Quality Inspection", "kind": "create",
         "fields": {"inspection_type": "Incoming", "item_code": item,
                    "quality_inspection_template": tpl},
         "hint": "Inspection Type、Item Code、Template", "invalidates": []},
        {"exists": [exists("qi", "Quality Inspection",
                           {"item_code": item, "inspection_type": "Incoming",
                            "docstatus": 0}, hi=10 ** 9)]})

# F23 Customer-edit: P without route
for tag, old, new in (("I1", "Alpha Lab Client", "Alpha Lab Client (renamed)"),
                      ("I2", "Beta Lab Client", "Beta Lab Client (renamed)")):
    add(f"F23-P-{tag}", "F23", "P", int(tag[-1]),
        f"把客户 {old} 的名称改为 \"{new}\",保存。",
        {"doctype": "Customer", "kind": "edit",
         "match": {"customer_name": old},
         "fields": {"customer_name": new},
         "hint": "先找到该客户(/app/customer/" + old.replace(' ', '-') + ")",
         "invalidates": []},
        {"exists": [exists("c", "Customer", {"customer_name": new})]})

# F24 Supplier-edit: P without route
for tag, name in (("I1", "Alpha Lab Vendor"), ("I2", "Beta Lab Vendor")):
    add(f"F24-P-{tag}", "F24", "P", int(tag[-1]),
        f"供应商 {name} 暂停合作:请将其冻结(Is Frozen)并保存。",
        {"doctype": "Supplier", "kind": "edit",
         "match": {"supplier_name": name},
         "fields": {"is_frozen": 1},
         "hint": "先找到该供应商(/app/supplier/" + name.replace(' ', '-') + ")",
         "invalidates": []},
        {"exists": [exists("s", "Supplier", {"supplier_name": name, "is_frozen": 1})]})

# ------------------------------------------------------------------- emit ---
for t in TASKS:
    d = os.path.join(OUT, t["family"])
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{t['task_id']}.json"), "w", encoding="utf-8") as f:
        json.dump(t, f, ensure_ascii=False, indent=2)

print(f"emitted {len(TASKS)} tasks into {OUT}")
fams = sorted(set(t["family"] for t in TASKS))
print("families:", len(fams), fams)
