#!/usr/bin/env bash
# Start the pinned ERPNext stack on the runner and wait until the site is ready.
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

READY=""
for i in $(seq 1 150); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:8080/api/method/ping" || true)
  if [ "$code" = "200" ]; then READY=yes; break; fi
  sleep 8
done
ELAPSED=$(( $(date +%s) - START ))
echo "erpnext_startup_seconds=${ELAPSED}" >> "$OUT/manifest.env"

if [ -z "$READY" ]; then
  echo "ERPNEXT_NOT_READY after ${ELAPSED}s"
  docker compose -f pwd.yml ps -a || true
  docker compose -f pwd.yml logs --tail 100 > "$OUT/stack_logs_fail.txt" 2>&1 || true
  exit 1
fi
echo "ERPNEXT_READY after ${ELAPSED}s"

SITE=$(docker compose -f pwd.yml exec -T backend bash -c \
  "ls /home/frappe/frappe-bench/sites | grep -Ev '^(apps|assets|common_site_config.json|sites.txt)$' | head -1" \
  | tr -d '\r\n')
echo "erpnext_site=${SITE}" >> "$OUT/manifest.env"
docker compose -f pwd.yml exec -T backend bench --site "$SITE" set-admin-password "${ADMIN_PASSWORD}" \
  || echo "set-admin-password failed; ui_smoke will try default creds"

docker compose -f pwd.yml ps | tee "$OUT/compose_ps.txt"
echo "=== df -h after startup ===" | tee -a "$OUT/df.log"
df -h / | tee -a "$OUT/df.log"
df -k / | awk 'NR==2{print "disk_free_after_startup_kb="$4}' >> "$OUT/manifest.env"
