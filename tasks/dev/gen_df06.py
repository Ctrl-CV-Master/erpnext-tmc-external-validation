# -*- coding: utf-8 -*-
"""DF06: relative-mirror gamma-differentiation family.

C0 creates a Batch whose description must MIRROR the item's CURRENT
description (resolved dynamically at fill time via @Item.<code>.description).
C1 then CHANGES the item's description — dirtying C0's confirmed state.

With gamma (TMC/R2): C0 is invalidated and re-executed; the @-reference
re-resolves to the NEW description → the batch description matches → reward 1.
Without gamma (R3): C0 stays confirmed with the OLD description → the batch
description no longer matches → reward 0.

Deterministic by construction: the condition list order (C0 then C1) plus the
information isolation (each condition's planner payload contains only its own
spec) forces the two-step execution.
"""
import json
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DF06")
os.makedirs(OUT, exist_ok=True)

CASES = [
    ("I1", "PREP-D", "PREP-D-B9001", "Rev C"),
    ("I2", "PREP-E", "PREP-E-B9001", "Rev 2"),
]

for tag, item, bid, new_desc in CASES:
    old_desc = "Synthetic finished preparation " + item
    task_id = "DF06-N-" + tag
    conditions = [
        {   # C0 at index 0: the mirror — resolved dynamically at fill time
            "id": "C0",
            "doctype": "Batch", "kind": "create",
            "fields": {"batch_id": bid, "item": item,
                       "description": "@Item." + item + ".description"},
            "hint": "批次描述必须与该物料当前的描述保持一致(从系统读取,不要凭记忆)",
            "invalidates": [],
        },
        {   # C1 at index 1: the write that dirties C0's confirmed state
            "id": "C1",
            "doctype": "Item", "kind": "edit",
            "route": "/app/item/" + item,
            "match": {"item_code": item, "description": old_desc},
            "fields": {"description": new_desc},
            "hint": "物料描述 -> " + new_desc,
            "invalidates": ["C0"],
        },
    ]
    rewards = {"exists": [
        {"ref": "b", "doctype": "Batch",
         "filters": {"batch_id": bid, "item": item, "description": new_desc},
         "count_gte": 1}]}
    task = {"task_id": task_id, "dev": True, "family": "DF06",
            "condition": "N", "instance": int(tag[-1]),
            "instruction": (
                "两步操作(按顺序执行):1) 为物料 {item} 创建一个批次,批次 ID 为 {bid},"
                "批次描述必须与该物料当前的描述保持一致(从系统读取后填写);"
                "2) 完成后,将该物料的描述(Description)改为 \"{new}\"。").format(
                    item=item, bid=bid, new=new_desc),
            "conditions": conditions,
            "reward_conditions": rewards}
    with open(os.path.join(OUT, task_id + ".json"), "w", encoding="utf-8") as f:
        json.dump(task, f, ensure_ascii=False, indent=2)
    print("wrote", task_id, "| item", item, "| new desc", new_desc)
