#!/usr/bin/env bash
# Collect final smoke metrics, assemble smoke-metrics.json, write job summary.
set -uo pipefail
WORKSPACE="${GITHUB_WORKSPACE:-$PWD}"
OUT="$WORKSPACE/smoke-out"

kill "$(cat "$OUT/sampler.pid" 2>/dev/null)" 2>/dev/null || true

if [ -d "$WORKSPACE/frappe_docker" ]; then
  cd "$WORKSPACE/frappe_docker"
  docker compose -f pwd.yml logs --tail 60 > "$OUT/stack_logs_tail.txt" 2>&1 || true
fi

echo "=== final df -h ===" | tee -a "$OUT/df.log"
df -h / | tee -a "$OUT/df.log"
echo "=== docker system df ===" | tee -a "$OUT/df.log"
docker system df | tee -a "$OUT/df.log"
echo "=== free -h ===" | tee "$OUT/free_final.txt"
free -h | tee -a "$OUT/df.log"

PEAK_KB=$(awk 'BEGIN{m=0}{if(($2+0)>m)m=$2+0}END{printf "%d",m}' "$OUT/peak_ram.log" 2>/dev/null || echo 0)
TOTAL_KB=$(awk '/MemTotal/{print $2}' /proc/meminfo)

python3 - "$OUT" "$PEAK_KB" "$TOTAL_KB" <<'PY' | tee "$OUT/smoke-metrics.pretty.json"
import json
import os
import sys

out, peak_kb, total_kb = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
env = {}
mf = os.path.join(out, "manifest.env")
if os.path.exists(mf):
    for line in open(mf):
        if "=" in line:
            k, v = line.rstrip("\n").split("=", 1)
            env[k] = v


def gb(x):
    return round(x / 1024 / 1024, 2)


digests = {}
for k, v in env.items():
    if k == "image_digest":
        parts = v.split()
        digests[parts[0]] = parts[1] if len(parts) > 1 else "unknown"

metrics = {
    "runner_vcpu": os.popen("nproc").read().strip(),
    "runner_total_ram_gb": gb(total_kb),
    "peak_used_ram_gb": gb(peak_kb),
    "disk_free_before_cleanup_gb": gb(int(env.get("disk_free_before_kb", "0") or 0)),
    "disk_free_after_cleanup_gb": gb(int(env.get("disk_free_after_kb", "0") or 0)),
    "disk_free_after_startup_kb": env.get("disk_free_after_startup_kb", ""),
    "erpnext_startup_seconds": env.get("erpnext_startup_seconds", ""),
    "erpnext_site": env.get("erpnext_site", ""),
    "frappe_docker_sha": env.get("frappe_docker_sha", ""),
    "playwright_version": env.get("playwright_version", ""),
    "python_version": env.get("python_version", ""),
    "node_version_before_cleanup": env.get("node_version_before", ""),
    "image_digests": digests,
}
ui_path = os.path.join(out, "ui_result.json")
if os.path.exists(ui_path):
    metrics["ui_smoke"] = json.load(open(ui_path))
with open(os.path.join(out, "smoke-metrics.json"), "w") as f:
    json.dump(metrics, f, indent=2, ensure_ascii=False)
print(json.dumps(metrics, indent=2, ensure_ascii=False))
PY

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "## ERPNext smoke metrics"
    echo '```json'
    cat "$OUT/smoke-metrics.json"
    echo '```'
  } >> "$GITHUB_STEP_SUMMARY"
fi
