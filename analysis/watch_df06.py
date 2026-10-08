# -*- coding: utf-8 -*-
"""Watch the DF06 gamma-differentiation pilot (6 runs) to completion, then
collect the manifests and report the TMC/R2/R3 split."""
import json
import subprocess
import sys
import time

tok = open("D:/tmc_erpnext_validation/.gh_token").read().strip()
REPO = "Ctrl-CV-Master/erpnext-tmc-external-validation"
LOG = "D:/tmc_erpnext_validation/analysis/df06_pilot_watch.log"


def api(url):
    r = subprocess.run(["curl", "-s", "-m", "60", "-H", f"Authorization: token {tok}",
                        "-H", "Accept: application/vnd.github+json", url],
                       capture_output=True, text=True)
    return json.loads(r.stdout)


deadline = time.time() + 50 * 60
seen_done = 0
while time.time() < deadline:
    d = api(f"https://api.github.com/repos/{REPO}/actions/workflows/erpnext-devtest.yml/runs?per_page=10&created=%3E%3D2026-10-07T14%3A50%3A00Z")
    runs = d["workflow_runs"]
    done = [r for r in runs if r["status"] == "completed"]
    infl = [r for r in runs if r["status"] != "completed"]
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S") + " done={} infl={}\n".format(len(done), len(infl)))
    if len(done) >= 6 and not infl:
        break
    time.sleep(90)

# collect the manifests
rows = []
d = api(f"https://api.github.com/repos/{REPO}/actions/workflows/erpnext-devtest.yml/runs?per_page=10&created=%3E%3D2026-10-07T14%3A50%3A00Z")
import urllib.request
import zipfile
import io
for r in d["workflow_runs"]:
    if r["status"] != "completed":
        continue
    a = api(f"https://api.github.com/repos/{REPO}/actions/runs/{r['id']}/artifacts")
    for art in a.get("artifacts", []):
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO}/actions/artifacts/{art['id']}/zip",
            headers={"Authorization": "token " + tok})
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                zf = zipfile.ZipFile(io.BytesIO(resp.read()))
            for mf in sorted(n for n in zf.namelist() if n.endswith(".manifest.json")):
                m = json.loads(zf.read(mf))
                s = m.get("summary") or {}
                rows.append({"task": m.get("task_id"), "method": m.get("method"),
                             "reward": m.get("reward"),
                             "invalidated": s.get("invalidated"),
                             "recalibrated": s.get("recalibrated"),
                             "failed": (m.get("eval_failed") or [""])[0][:100],
                             "conclusion": r["conclusion"]})
        except Exception as e:
            rows.append({"run": r["id"], "error": str(e)[:100]})

with open("D:/tmc_erpnext_validation/analysis/df06_pilot_results.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, indent=1, ensure_ascii=False)

glm = [x for x in rows if x.get("mock") is False]
with open(LOG, "a", encoding="utf-8") as f:
    for x in glm:
        f.write("RESULT {} {} reward={} invalidated={} recal={} concl={}\n".format(
            x.get("task"), x.get("method"), x.get("reward"), x.get("invalidated"),
            x.get("recalibrated"), x.get("conclusion")))
print("DF06 pilot results written:", len(glm), "GLM runs")
