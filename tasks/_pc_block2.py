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
        {"exists": [exists("u", "UOM", {"uom_name": name})]})

# F16 Warehouse: P terse
for tag, wh in (("I1", "RET-WH"), ("I2", "SAMPLE-WH")):
    add(f"F16-P-{tag}", "F16", "P", int(tag[-1]),
        f"请在公司 Open Preparation Lab 下新建仓库:{wh}。",
        {"doctype": "Warehouse", "kind": "create",
         "fields": {"warehouse_name": wh, "company": COMPANY},
         "hint": "Warehouse Name、Company", "invalidates": []},
        {"exists": [exists("w", "Warehouse", {"warehouse_name": wh})]})

# F17 Customer: P terse
for tag, name in (("I1", "Gamma Lab Client"), ("I2", "Delta Lab Client")):
    add(f"F17-P-{tag}", "F17", "P", int(tag[-1]),
        f"请新建客户:{name}(类型 Company,客户组 All Customer Groups)。",
        {"doctype": "Customer", "kind": "create",
         "fields": {"customer_name": name, "customer_type": "Company",
                    "customer_group": "All Customer Groups"},
         "hint": "Customer Name、Customer Type、Customer Group", "invalidates": []},
        {"exists": [exists("c", "Customer", {"customer_name": name})]})

# F18 Supplier: P terse
for tag, name in (("I1", "Gamma Lab Vendor"), ("I2", "Delta Lab Vendor")):
    add(f"F18-P-{tag}", "F18", "P", int(tag[-1]),
        f"请新建供应商:{name}(供应商组 All Supplier Groups)。",
        {"doctype": "Supplier", "kind": "create",
         "fields": {"supplier_name": name, "supplier_group": "All Supplier Groups"},
         "hint": "Supplier Name、Supplier Group", "invalidates": []},
        {"exists": [exists("s", "Supplier", {"supplier_name": name})]})

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
                            "price_list_rate": price})]})

# F20 Workstation: P terse
for tag, ws, cap in (("I1", "WS-REPACK", 3), ("I2", "WS-STERILIZE", 2)):
    add(f"F20-P-{tag}", "F20", "P", int(tag[-1]),
        f"请新建工作站:{ws},产能 {cap}。",
        {"doctype": "Workstation", "kind": "create",
         "fields": {"workstation_name": ws, "production_capacity": cap},
         "hint": "Workstation Name、Production Capacity", "invalidates": []},
        {"exists": [exists("w", "Workstation", {"workstation_name": ws})]})

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
                            "docstatus": 0})]})

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
