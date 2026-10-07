import json
import subprocess
import sys
import time

tok = sys.argv[1]
logf = sys.argv[2]
pairs = json.load(open("D:/tmc_erpnext_validation/analysis/rerun_list.json"))
REPO = "Ctrl-CV-Master/erpnext-tmc-external-validation"


def log(msg):
    with open(logf, "a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S") + " " + msg + "\n")


for tid, method in pairs:
    fam = tid.split("-")[0]
    path = "tasks/formal/{}/{}.json".format(fam, tid)
    r = subprocess.run(["curl", "-s", "-m", "30", "-o", "/dev/null",
                        "-w", "%{http_code}", "-X", "POST",
                        "-H", "Authorization: token " + tok,
                        "-H", "Accept: application/vnd.github+json",
                        "https://api.github.com/repos/{}/actions/workflows/erpnext-devtest.yml/dispatches".format(REPO),
                        "-d", json.dumps({"ref": "main", "inputs": {
                            "task": path, "method": method, "mock": False}})],
                       capture_output=True, text=True)
    log("dispatched {} {} -> {}".format(tid, method, r.stdout.strip()))
    time.sleep(2)
log("dispatch phase done")
