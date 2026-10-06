# -*- coding: utf-8 -*-
"""Single-run orchestrator: adapter -> method episode -> ORM evaluator -> records.

Runs on the workflow runner (host side). ERPNext stack must be up at localhost:8080.

    python runner.py --task tasks/dev/D01.json --method TMC --out-dir runs/dev
        [--mock]   # deterministic planner, no LLM calls (dev validation only)

Outputs:
  {out-dir}/{task_id}__{method}.manifest.json   full run record
  {out-dir}/{task_id}__{method}.traj.jsonl.gz   compact trajectory
  {out-dir}/run_manifest.csv                    one row per run (append)
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "adapter"))

from erpnext_env import ERPNextEnv  # noqa: E402
from episode import BROWSER_BUDGET, Episode  # noqa: E402
from glm_client import GLMClient  # noqa: E402

FRAPPE_DIR = os.environ.get("FRAPPE_DOCKER_DIR", "frappe_docker")
SITE = os.environ.get("ERPNEXT_SITE", "frontend")


class MockPlanner:
    """Deterministic planner for dev validation (never used in formal runs)."""

    def __init__(self):
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.model = "mock"
        self.substitutions = []

    def chat(self, messages, temperature=0.0, force_json=False):
        self.calls += 1
        task = json.loads(messages[1]["content"])
        cond = task["condition"]
        actions = [{"type": "fill", "fieldname": k, "value": v} for k, v in cond["fields"].items()]
        actions.append({"type": "save"})
        if cond.get("expect_docstatus") == 1:
            # submit flow: menu action + confirmation dialog
            actions.append({"type": "click", "text": "Submit"})
            actions.append({"type": "click", "text": "Yes"})
        return json.dumps({"actions": actions})

    def usage(self):
        return {"calls": self.calls, "input_tokens": 0, "output_tokens": 0,
                "model": "mock", "substitutions": []}


def _backend_cid():
    r = subprocess.run(
        ["docker", "compose", "-f", f"{FRAPPE_DIR}/pwd.yml", "ps", "-q", "backend"],
        capture_output=True, text=True, check=True)
    return r.stdout.strip()


def orm_evaluate(task_path, out_path):
    """Run the JSON-driven evaluator inside the backend container (bench python)."""
    here = os.path.dirname(os.path.abspath(__file__))
    ev_src = os.path.join(here, "..", "evaluator", "evaluate.py")
    cid = _backend_cid()
    subprocess.run(["docker", "cp", task_path, f"{cid}:/tmp/task.json"], check=True)
    subprocess.run(["docker", "cp", os.path.abspath(ev_src),
                    f"{cid}:/home/frappe/frappe-bench/evaluate.py"], check=True)
    probe = subprocess.run(
        ["docker", "compose", "-f", f"{FRAPPE_DIR}/pwd.yml", "exec", "-T", "backend", "bash", "-c",
         'for p in /home/frappe/frappe-bench/env/bin/python /home/frappe/frappe-bench/env/bin/python3; '
         'do [ -x "$p" ] && echo "$p" && exit 0; done; head -1 "$(command -v bench)" | sed "s/^#!//"'],
        capture_output=True, text=True)
    bpy = probe.stdout.strip().splitlines()[-1] if probe.stdout.strip() else "python3"
    subprocess.run(
        ["docker", "compose", "-f", f"{FRAPPE_DIR}/pwd.yml", "exec", "-T", "-u", "root",
         "backend", "bash", "-c",
         "mkdir -p /home/frappe/logs /home/frappe/frappe-bench/logs "
         "/home/frappe/frappe-bench/*/logs /home/frappe/frappe-bench/sites/*/logs"],
        check=False)
    subprocess.run(["docker", "compose", "-f", f"{FRAPPE_DIR}/pwd.yml", "exec", "-T",
                    "-u", "root", "-w", "/home/frappe/frappe-bench", "-e", f"SITE={SITE}",
                    "backend", bpy, "evaluate.py",
                    "--task", "/tmp/task.json", "--out", "/tmp/eval_out.json"], check=False)
    res = subprocess.run(
        ["docker", "compose", "-f", f"{FRAPPE_DIR}/pwd.yml", "exec", "-T", "backend",
         "cat", "/tmp/eval_out.json"], capture_output=True, text=True)
    try:
        return json.loads(res.stdout)
    except Exception:
        return {"reward": 0, "error": "evaluator output unreadable: " + res.stdout[:200]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--method", default="TMC", choices=["TMC", "R2", "R3"])
    ap.add_argument("--out-dir", default="runs/dev")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--admin-password", default=os.environ.get("ADMIN_PASSWORD", "admin"))
    a = ap.parse_args()

    task = json.load(open(a.task, encoding="utf-8"))
    task_id = task["task_id"]
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.time()

    env = ERPNextEnv(admin_password=a.admin_password, budget=BROWSER_BUDGET)
    if a.mock:
        glm = MockPlanner()
    else:
        model = "glm-5.3-flashx" if a.method == "TMC" else "glm-5.3-flash"
        glm = GLMClient(model=model, tag=task_id)
    ep = Episode(task, a.method, env, glm, run_id=f"{task_id}|{a.method}")
    summary = ep.run()

    tmp_task = os.path.abspath(a.task)
    ev = orm_evaluate(tmp_task, "/tmp/eval_out.json")

    record = {
        "task_id": task_id, "method": a.method, "mock": a.mock,
        "reward": ev.get("reward"), "eval_failed": ev.get("failed", []),
        "wall_clock_s": round(time.time() - t0, 1),
        "browser_actions": env.actions_used,
        "summary": summary,
        "eval_error": ev.get("error"),
    }
    with open(os.path.join(a.out_dir, f"{task_id}__{a.method}.manifest.json"), "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    with gzip.open(os.path.join(a.out_dir, f"{task_id}__{a.method}.traj.jsonl.gz"), "wt",
                   encoding="utf-8") as f:
        for row in ep.trajectory:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    mpath = os.path.join(a.out_dir, "run_manifest.csv")
    new = not os.path.exists(mpath)
    with open(mpath, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["task_id", "method", "reward", "browser_actions", "llm_calls",
                        "input_tokens", "output_tokens", "wall_clock_s", "terminated"])
        u = glm.usage()
        w.writerow([task_id, a.method, ev.get("reward"), env.actions_used, u["calls"],
                    u["input_tokens"], u["output_tokens"],
                    record["wall_clock_s"], summary.get("terminated")])
    env.close()
    print("RUN_DONE", task_id, a.method, "reward", ev.get("reward"))
    return 0 if ev.get("reward") == 1 else 1


if __name__ == "__main__":
    sys.exit(main())
