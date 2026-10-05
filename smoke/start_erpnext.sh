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
case "$ERPNEXT_VERSION" in
  v15.*) sed -i -E "s#image: mariadb:[^\"'[:space:]]+#image: mariadb:10.6#g" pwd.yml ;;
esac
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

# 3) Deterministic credentials: a real site dir contains site_config.json
#    (sites/ also holds non-site dirs like assets/).
SITE=$(docker compose -f pwd.yml exec -T backend bash -c \
  "cd /home/frappe/frappe-bench/sites && for d in */; do [ -f \"\${d}site_config.json\" ] && echo \"\${d}\" && break; done" \
  | tr -d '/\r\n')
echo "erpnext_site=${SITE}" >> "$OUT/manifest.env"
echo "detected site: ${SITE}" | tee -a "$OUT/evaluator.txt"

# The database name is NOT necessarily the site name: read it from site_config.json.
DBRAW=$(docker compose -f pwd.yml exec -T backend bash -c \
  "grep -oE '\"db_name\": *\"[^\"]+\"' /home/frappe/frappe-bench/sites/$SITE/site_config.json | head -1" \
  | tr -d '\r\n')
echo "db_name raw match: ${DBRAW:-none}" | tee -a "$OUT/evaluator.txt"
DBNAME=$(echo "$DBRAW" | cut -d'"' -f4 | tr -d '\r\n')
DBNAME=${DBNAME:-$SITE}
echo "erpnext_db=${DBNAME}" >> "$OUT/manifest.env"
echo "db: ${DBNAME}" | tee -a "$OUT/evaluator.txt"

docker compose -f pwd.yml exec -T backend bench --site "$SITE" set-admin-password "${ADMIN_PASSWORD}" \
  > "$OUT/setpw.out" 2>&1 \
  && echo "bench setpw rc=0" >> "$OUT/evaluator.txt" \
  || echo "bench setpw failed: $(tail -2 "$OUT/setpw.out" 2>/dev/null)" >> "$OUT/evaluator.txt"

# Skip the setup wizard: mark setup complete via SQL (no frappe python env
# needed in backend), then clear frappe's caches.
# v16 semantics: System Settings.setup_complete.
# v15 semantics: frappe.is_setup_complete() reads Installed Application rows
# for frappe/erpnext (System Settings.setup_complete is ignored), so both
# flags must be set or the desk keeps redirecting to /app/setup-wizard.
cat > "$OUT/setup_complete.sql" <<'SQL'
INSERT INTO `tabSingles` (`doctype`, `field`, `value`)
VALUES ('System Settings', 'setup_complete', '1')
ON DUPLICATE KEY UPDATE `value` = '1';
SQL
if [[ "${ERPNEXT_VERSION}" == v15.* ]]; then
  cat >> "$OUT/setup_complete.sql" <<'SQL'
UPDATE `tabInstalled Application` SET `is_setup_complete`=1
WHERE app_name IN ('frappe', 'erpnext');
SQL
fi
docker compose -f pwd.yml exec -T db sh -c "exec mariadb -uroot -p\"\$MYSQL_ROOT_PASSWORD\" $DBNAME" \
  < "$OUT/setup_complete.sql" >> "$OUT/evaluator.txt" 2>&1 \
  && echo "setup_complete written via SQL" | tee -a "$OUT/evaluator.txt" \
  || echo "setup_complete SQL FAILED" | tee -a "$OUT/evaluator.txt"
SC=$(docker compose -f pwd.yml exec -T db sh -c "exec mariadb -uroot -p\"\$MYSQL_ROOT_PASSWORD\" $DBNAME -N -e \"SELECT value FROM tabSingles WHERE doctype='System Settings' AND field='setup_complete';\"" 2>/dev/null | tail -1 || true)
echo "setup_complete now: ${SC:-unset}" | tee -a "$OUT/evaluator.txt"
if [[ "${ERPNEXT_VERSION}" == v15.* ]]; then
  printf 'SELECT CONCAT(app_name, "=", is_setup_complete) FROM `tabInstalled Application`;\n' \
    > "$OUT/ia_check.sql"
  IA=$(docker compose -f pwd.yml exec -T db sh -c "exec mariadb -uroot -p\"\$MYSQL_ROOT_PASSWORD\" $DBNAME -N" \
    < "$OUT/ia_check.sql" 2>/dev/null | tr '\n' ' ' || true)
  echo "installed_apps: ${IA:-query_failed}" | tee -a "$OUT/evaluator.txt"
fi

# Set language explicitly: an unset locale crashes desk boot (AltShortcutGroup
# RangeError) and leaves every desk page blank.
cat > "$OUT/language.sql" <<'SQL'
UPDATE `tabUser` SET language = 'en' WHERE name = 'Administrator';
INSERT INTO `tabSingles` (`doctype`, `field`, `value`)
VALUES ('System Settings', 'language', 'en')
ON DUPLICATE KEY UPDATE `value` = 'en';
SQL
docker compose -f pwd.yml exec -T db sh -c "exec mariadb -uroot -p\"\$MYSQL_ROOT_PASSWORD\" $DBNAME" \
  < "$OUT/language.sql" >> "$OUT/evaluator.txt" 2>&1 \
  && echo "language set to en" | tee -a "$OUT/evaluator.txt" \
  || echo "language SQL FAILED" | tee -a "$OUT/evaluator.txt"

# Raw tabSingles SQL does not update frappe's defaults store: boot.sysdefaults
# comes from frappe.defaults.get_defaults() (tabDefaultValue), which is only
# populated by SystemSettings.save() -> set_defaults(). Without this,
# sysdefaults.language stays null and desk boot crashes with
# "Incorrect locale information provided" (seen on v15).
# Run with the bench venv python: system python3 has no frappe module.
BENCH_PY=$(docker compose -f pwd.yml exec -T backend bash -c \
  'for p in /home/frappe/frappe-bench/env/bin/python /home/frappe/frappe-bench/env/bin/python3; do [ -x "$p" ] && echo "$p" && exit 0; done; head -1 "$(command -v bench)" | sed "s/^#!//"' | tail -1)
echo "bench python: ${BENCH_PY:-none}" >> "$OUT/evaluator.txt"
if [ -n "$BENCH_PY" ]; then
  docker compose -f pwd.yml exec -T -e SITE="$SITE" backend "$BENCH_PY" - <<'PY' >> "$OUT/evaluator.txt" 2>&1 || true
import os

import frappe

frappe.init(site=os.environ["SITE"])
frappe.connect()
frappe.set_user("Administrator")
s = frappe.get_doc("System Settings")
s.language = "en"
s.flags.ignore_mandatory = True
s.save()
frappe.db.commit()
print("system_settings saved via ORM; defaults language:",
      frappe.defaults.get_defaults().get("language"))
frappe.destroy()
PY
fi

docker compose -f pwd.yml exec -T backend bench --site "$SITE" clear-cache >> "$OUT/evaluator.txt" 2>&1 \
  && echo "clear-cache ok" >> "$OUT/evaluator.txt"

# Verify login once via HTTP API (no browser); one retry after a fresh reset.
LOGIN_CODE=$(curl -s -o "$OUT/login_check.out" -w '%{http_code}' \
  -d "usr=Administrator&pwd=${ADMIN_PASSWORD}" "http://localhost:8080/api/method/login" || true)
if [ "$LOGIN_CODE" != "200" ]; then
  docker compose -f pwd.yml exec -T -e SITE="$SITE" backend bash -s <<'EOF' >> "$OUT/evaluator.txt" 2>&1 || true
cd /home/frappe/frappe-bench
python3 - <<'PY'
import os

import frappe

frappe.init(site=os.environ["SITE"])
frappe.connect()
frappe.db.sql("UPDATE `tabUser` SET login_attempts=0, failed_login_count=0, last_login_attempts=NULL WHERE name='Administrator'")
frappe.db.commit()
print("LOCKOUT_RESET_RETRY")
frappe.destroy()
PY
EOF
  sleep 5
  LOGIN_CODE=$(curl -s -o "$OUT/login_check.out" -w '%{http_code}' \
    -d "usr=Administrator&pwd=${ADMIN_PASSWORD}" "http://localhost:8080/api/method/login" || true)
fi
echo "curl_login_http=$LOGIN_CODE body=$(head -c 100 "$OUT/login_check.out" 2>/dev/null)" | tee -a "$OUT/evaluator.txt"

docker compose -f pwd.yml ps | tee "$OUT/compose_ps.txt"
echo "=== df -h after startup ===" | tee -a "$OUT/df.log"
df -h / | tee -a "$OUT/df.log"
df -k / | awk 'NR==2{print "disk_free_after_startup_kb="$4}' >> "$OUT/manifest.env"
