# -*- coding: utf-8 -*-
"""Watch the 12 correction runs until all complete, then report."""
import json
import subprocess
import time

tok = open("D:/tmc_erpnext_validation/.gh_token").read().strip()
REPO = "Ctrl-CV-Master/erpnext-tmc-external-validation"


def api(url):
    r = subprocess.run(["curl", "-s", "-m", "60", "-H", f"Authorization: token {tok}",
                        "-H", "Accept: application/vnd.github+json", url],
                       capture_output=True, text=True)
    return json.loads(r.stdout)


deadline = time.time() + 80 * 60
seen_done = 0
while time.time() < deadline:
    d = api(f"https://api.github.com/repos/{REPO}/actions/workflows/erpnext-devtest.yml/runs?per_page=30&created=%3E%3D2026-10-07T13:45:00Z")
    runs = d["workflow_runs"]
    done = [r for r in runs if r["status"] == "completed"]
    infl = [r for r in runs if r["status"] != "completed"]
    print(f"{time.strftime('%H:%M:%S')} done={len(done)} in_flight={len(infl)}")
    if runs and len(done) >= 12 and not infl:
        for r in done:
            print("  ", r["id"], r["conclusion"])
        break
    time.sleep(120)
print("correction batch settled")
