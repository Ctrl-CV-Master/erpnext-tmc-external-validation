#!/usr/bin/env bash
# Start the pinned ERPNext stack on the runner and wait until the site is really ready.
# Newer pwd.yml creates the site via a one-shot "create-site" service: readiness
# requires (1) create-site exited 0 AND (2) /api/method/ping returns pong.
set -euo pipefail

WORKSPACE="${GITHUB_WORKSPACE:-$PWD}"
OUT="$WORKSPACE/smoke-out"
mkdir -p "$OUT"

bash "$WORKSPACE/smoke/peak_ram_sampler.sh" &
echo $! > "$OUT/sampler.pid"

rm -rf "$WORKSPACE/frappe_docker"
git clone -q https://github.com/frappe/frappe_docker.git "$WORKSPACE/frappe_docker"
cd "$WORKSPACE/frappe_docker"
git checkout -q "$FRAPPE_DOCKER_SHA"
echo "frappe_docker_sha=$(git rev-parse HEAD)" >> "$OUT/manifest.env"

# Pin the ERPNext image tag regardless of pwd.yml defaults.
sed -i -E "s#(frappe/erpnext:)[^\"'[:space:]]+#\1${ERPNEXT_VERSION}#g" pwd.yml
grep -n "frappe/erpnext:" pwd.yml | tee "$OUT/pwd_image_pin.txt"

cat > .env <<EOF
ERPNEXT_VERSION=${ERPNEXT_VERSION}
DB_PASSWORD=${DB_PASSWORD}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
EOF

echo "[$(date -u +%T)] pulling pinned images ..."
docker compose -f pwd.yml pull 2>&1 | tail -5

: > "$OUT/images.txt"
docker images --format '{{.Repository}}:{{.Tag}}\t{{.Size}}' | tee "$OUT/images.txt"
for img in $(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E '^(frappe/erpnext|mariadb|redis):' || true); do
  d=$(docker inspect --format '{{index .RepoDigests 0}}' "$img" 2>/dev/null || echo unknown)
  echo "image_digest ${img} ${d}" >> "$OUT/manifest.env"
done
echo "=== df -h after image pull ===" | tee -a "$OUT/df.log"
df -h / | tee -a "$OUT/df.log"
docker system df >> "$OUT/df.log" 2>/dev/null || true

echo "[$(date -u +%T)] starting stack ..."
START=$(date +%s)
docker compose -f pwd.yml up -d

# 1) Wait for the one-shot create-site service to exit successfully.
# NOTE: docker ps --format does not support .ExitCode; use docker inspect for that.
CREATESITE_OK=""
for i in $(seq 1 120); do
  cid=$(docker ps -aq --filter "label=com.docker.compose.service=create-site" | head -1 || true)
  if [ -n "$cid" ]; then
    st=$(docker inspect -f "{{.State.Status}} {{.State.ExitCode}}" "$cid" 2>/dev/null || echo "unknown -1")
    state=${st%% *}; code=${st##* }
    if [ "$state" = "exited" ]; then
      if [ "$code" = "0" ]; then
        CREATESITE_OK=yes
      else
        echo "create-site FAILED (exit $code)"
        docker logs "$cid" --tail 60 2>&1 | tail -60 || true
      fi
      break
    fi
  fi
  sleep 8
done
if [ -z "$CREATESITE_OK" ]; then
  echo "CREATE_SITE_NOT_CONFIRMED"
  docker compose -f pwd.yml ps -a || true
  docker compose -f pwd.yml logs --tail 100 > "$OUT/stack_logs_fail.txt" 2>&1 || true
  exit 1
fi
echo "create-site completed successfully at $(date -u +%T)"

# 2) Wait until the API really answers pong.
READY=""
for i in $(seq 1 60); do
  body=$(curl -s -m 5 "http://localhost:8080/api/method/ping" || true)
  if echo "$body" | grep -q "pong"; then READY=yes; break; fi
  sleep 5
done
ELAPSED=$(( $(date +%s) - START ))
echo "erpnext_startup_seconds=${ELAPSED}" >> "$OUT/manifest.env"
if [ -z "$READY" ]; then
  echo "ERPNEXT_NOT_READY after ${ELAPSED}s"
  docker compose -f pwd.yml ps -a || true
  docker compose -f pwd.yml logs --tail 100 > "$OUT/stack_logs_fail.txt" 2>&1 || true
  exit 1
fi
echo "ERPNEXT_READY after ${ELAPSED}s (create-site exit 0 + pong)"

# 3) Deterministic credentials: detect the real site (a DIRECTORY under sites/),
#    set the password via ORM, skip the setup wizard, verify login via HTTP API.
SITE=$(docker compose -f pwd.yml exec -T backend bash -c \
  "cd /home/frappe/frappe-bench/sites && ls -d */ 2>/dev/null | head -1" | tr -d '/\r\n')
echo "erpnext_site=${SITE}" >> "$OUT/manifest.env"
echo "detected site: ${SITE}" | tee -a "$OUT/evaluator.txt"

docker compose -f pwd.yml exec -T backend bench --site "$SITE" set-admin-password "${ADMIN_PASSWORD}" \
  > "$OUT/setpw.out" 2>&1 \
  && echo "bench set-admin-password rc=0" >> "$OUT/evaluator.txt" \
  || echo "bench set-admin-password failed, output: $(tail -3 "$OUT/setpw.out" 2>/dev/null)" >> "$OUT/evaluator.txt"

docker compose -f pwd.yml exec -T -e SITE="$SITE" -e ADMPW="${ADMIN_PASSWORD}" backend bash -s <<'EOF' >> "$OUT/evaluator.txt" 2>&1 || true
cd /home/frappe/frappe-bench
python3 - <<'PY'
import os

import frappe

frappe.init(site=os.environ["SITE"])
frappe.connect()
from frappe.utils.password import update_password

update_password(user="Administrator", pwd=os.environ["ADMPW"])
try:
    frappe.db.set_single_value("System Settings", "setup_complete", 1)
except Exception:
    frappe.db.set_value("System Settings", "System Settings", "setup_complete", 1)
frappe.db.commit()
print("ORM_PW_SET + SETUP_COMPLETE=1")
frappe.destroy()
PY
EOF

LOGIN_CODE=""
for i in $(seq 1 12); do
  LOGIN_CODE=$(curl -s -o "$OUT/login_check.out" -w '%{http_code}' \
    -d "usr=Administrator&pwd=${ADMIN_PASSWORD}" "http://localhost:8080/api/method/login" || true)
  [ "$LOGIN_CODE" = "200" ] && break
  sleep 5
done
echo "curl_login_http=$LOGIN_CODE body=$(head -c 100 "$OUT/login_check.out" 2>/dev/null)" | tee -a "$OUT/evaluator.txt"

docker compose -f pwd.yml ps | tee "$OUT/compose_ps.txt"
echo "=== df -h after startup ===" | tee -a "$OUT/df.log"
df -h / | tee -a "$OUT/df.log"
df -k / | awk 'NR==2{print "disk_free_after_startup_kb="$4}' >> "$OUT/manifest.env"
