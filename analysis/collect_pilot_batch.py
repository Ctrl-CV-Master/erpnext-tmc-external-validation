# -*- coding: utf-8 -*-
"""Batch-collect manifests from all devtest runs in a time window."""
import json
import os
import subprocess
import sys
import zipfile

REPO = "Ctrl-CV-Master/erpnext-tmc-external-validation"
OUT = "D:/tmc_erpnext_validation/analysis/pilot_batch"
os.makedirs(OUT, exist_ok=True)
tok = open("D:/tmc_erpnext_validation/.gh_token").read().strip()

after = sys.argv[1] if len(sys.argv) > 1 else "2026-10-07T12:30:00Z"


def api(url):
    r = subprocess.run(["curl", "-s", "-m", "60", "-H", f"Authorization: token {tok}",
                        "-H", "Accept: application/vnd.github+json", url],
                       capture_output=True, text=True)
    return json.loads(r.stdout)


runs = []
page = 1
while True:
    d = api(f"https://api.github.com/repos/{REPO}/actions/workflows/erpnext-devtest.yml/runs?per_page=50&page={page}&created=%3E%3D{after}")
    runs += d["workflow_runs"]
    if len(d["workflow_runs"]) < 50:
        break
    page += 1

print("runs in window:", len(runs))
rows = []
for i, r in enumerate(runs):
    if r["status"] != "completed":
        continue
    d = api(f"https://api.github.com/repos/{REPO}/actions/runs/{r['id']}/artifacts")
    for a in d.get("artifacts", []):
        zpath = os.path.join(OUT, f"{a['id']}.zip")
        if not (os.path.exists(zpath) and os.path.getsize(zpath) > 100):
            for attempt in range(4):
                subprocess.run(["curl", "-sL", "-m", "120", "-H", f"Authorization: token {tok}",
                                f"https://api.github.com/repos/{REPO}/actions/artifacts/{a['id']}/zip",
                                "-o", zpath])
                if os.path.exists(zpath) and os.path.getsize(zpath) > 100:
                    break
            else:
                continue
        try:
            zf = zipfile.ZipFile(zpath)
        except Exception:
            continue
        for mf in sorted(n for n in zf.namelist() if n.endswith(".manifest.json")):
            try:
                m = json.loads(zf.read(mf))
            except Exception:
                continue
            s = m.get("summary") or {}
            lu = s.get("llm_usage") or {}
            rows.append({
                "run_id": r["id"], "conclusion": r["conclusion"],
                "task_id": m.get("task_id"), "method": m.get("method"),
                "mock": m.get("mock"), "reward": m.get("reward"),
                "family": (m.get("task_id") or "").split("-")[0],
                "failed": "; ".join(m.get("eval_failed") or [])[:200],
                "browser_actions": s.get("browser_actions"),
                "invalidated": s.get("invalidated"),
                "recalibrated": s.get("recalibrated"),
                "llm_calls": lu.get("calls"),
                "llm_in": lu.get("input_tokens"), "llm_out": lu.get("output_tokens"),
                "wall_clock_s": m.get("wall_clock_s"),
            })
    if (i + 1) % 10 == 0:
        print(f"  {i+1}/{len(runs)}")

json.dump(rows, open(os.path.join(OUT, "batch_rows.json"), "w"), indent=1)
glm = [r for r in rows if r.get("mock") is False]
print("GLM rows collected:", len(glm))
