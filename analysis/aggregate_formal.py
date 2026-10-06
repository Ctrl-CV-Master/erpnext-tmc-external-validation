# -*- coding: utf-8 -*-
"""Aggregate the formal experiment: download all job artifacts for a run and
build the 432-run reward matrix (family x instance x condition x method).

Usage: python analysis/aggregate_formal.py <run_id>
Downloads artifacts via curl (blob endpoint unreachable from this network for
python-urllib). Writes analysis/formal_results.json + .csv and prints stats.
"""
import csv
import glob
import json
import os
import subprocess
import sys
import zipfile

REPO = "Ctrl-CV-Master/erpnext-tmc-external-validation"
RUN_ID = sys.argv[1]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(OUT, "formal_art")
os.makedirs(ART, exist_ok=True)

tok = open(os.path.join(OUT, "..", ".gh_token")).read().strip()


def curl_json(url):
    r = subprocess.run(["curl", "-s", "-m", "60", "-H", f"Authorization: token {tok}",
                        "-H", "Accept: application/vnd.github+json", url],
                       capture_output=True, text=True)
    return json.loads(r.stdout)


runs = curl_json(f"https://api.github.com/repos/{REPO}/actions/runs/{RUN_ID}/artifacts?per_page=100")
arts = runs.get("artifacts", [])
print(f"artifacts: {len(arts)}")

rows = []
for i, a in enumerate(arts):
    zpath = os.path.join(ART, f"{a['id']}.zip")
    for attempt in range(6):
        if os.path.exists(zpath) and os.path.getsize(zpath) > 100:
            break
        r = subprocess.run(["curl", "-sL", "-m", "120", "-H", f"Authorization: token {tok}",
                            f"https://api.github.com/repos/{REPO}/actions/artifacts/{a['id']}/zip",
                            "-o", zpath])
        if r.returncode == 0 and os.path.exists(zpath) and os.path.getsize(zpath) > 100:
            break
        import time
        time.sleep(10)
        if attempt == 5:
            print(f"  WARN: {a['name']} download failed after retries")
    try:
        zf = zipfile.ZipFile(zpath)
        for mf in sorted(n for n in zf.namelist() if n.endswith(".manifest.json")):
            m = json.loads(zf.read(mf))
            s = m.get("summary") or {}
            lu = s.get("llm_usage") or {}
            rows.append({
                "job": a["name"], "task_id": m.get("task_id"),
                "family": (m.get("task_id") or "").split("-")[0],
                "instance": (m.get("task_id") or "").rsplit("-I", 1)[-1],
                "condition": (m.get("task_id") or "").split("-")[1],
                "method": m.get("method"), "mock": m.get("mock"),
                "reward": m.get("reward"),
                "failed": "; ".join(m.get("eval_failed") or [])[:200],
                "browser_actions": s.get("browser_actions"),
                "llm_calls": lu.get("calls"),
                "llm_in": lu.get("input_tokens"), "llm_out": lu.get("output_tokens"),
                "wall_clock_s": m.get("wall_clock_s"),
            })
    except Exception as e:
        rows.append({"job": a["name"], "error": str(e)[:120]})
    if (i + 1) % 10 == 0:
        print(f"  {i+1}/{len(arts)}")

json.dump(rows, open(os.path.join(OUT, "formal_results.json"), "w"), indent=1)
glm = [r for r in rows if r.get("mock") is False]
with open(os.path.join(OUT, "formal_results.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(glm[0].keys()) if glm else ["job"])
    w.writeheader()
    w.writerows(glm)

print(f"GLM runs: {len(glm)} | reward 1: {sum(1 for r in glm if r.get('reward') == 1)}")
by_m, by_c = {}, {}
for r in glm:
    by_m.setdefault(r["method"], [0, 0])
    by_m[r["method"]][0] += r.get("reward") or 0
    by_m[r["method"]][1] += 1
    by_c.setdefault(r["condition"], [0, 0])
    by_c[r["condition"]][0] += r.get("reward") or 0
    by_c[r["condition"]][1] += 1
print("per method:", {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_m.items())})
print("per condition:", {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_c.items())})
print("total tokens:", sum((r.get("llm_in") or 0) + (r.get("llm_out") or 0) for r in glm))
