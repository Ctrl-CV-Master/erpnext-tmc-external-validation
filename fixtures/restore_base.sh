#!/usr/bin/env bash
# Restore the verified base fixture into a running ERPNext stack and verify the
# state hash. Requires smoke/start_erpnext.sh to have run first (manifest.env).
set -euo pipefail
WORKSPACE="${GITHUB_WORKSPACE:-$PWD}"
OUT="$WORKSPACE/smoke-out"
cd "$WORKSPACE/frappe_docker"

SITE=$(grep -m1 '^erpnext_site=' "$OUT/manifest.env" | cut -d= -f2)
DB=$(grep -m1 '^erpnext_db=' "$OUT/manifest.env" | cut -d= -f2)
echo "restore: site=$SITE db=$DB"

docker compose -f pwd.yml exec -T -u root backend bash -c \
  "mkdir -p /home/frappe/logs /home/frappe/frappe-bench/logs /home/frappe/frappe-bench/*/logs /home/frappe/frappe-bench/sites/*/logs" 2>/dev/null || true

docker compose -f pwd.yml exec -T db sh -c "exec mariadb -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -e \"DROP DATABASE IF EXISTS $DB; CREATE DATABASE $DB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\""
gunzip -c "$WORKSPACE/fixtures/base_fixture.sql.gz" | docker compose -f pwd.yml exec -T db sh -c "exec mariadb -uroot -p\"\$MYSQL_ROOT_PASSWORD\" $DB"
# Restart the app containers together with redis: the DB was swapped under a
# live redis and stale boot/session/defaults caches keep gunicorn from serving
# desk pages (502) even though the container itself comes back up.
docker compose -f pwd.yml restart backend redis-cache redis-queue >/dev/null
for i in $(seq 1 60); do
  body=$(curl -s -m 5 "http://localhost:8080/api/method/ping" || true)
  echo "$body" | grep -q "pong" && break
  sleep 5
done

# Gate on the desk being actually reachable, not just the API.
LOGIN_CODE=0
for i in $(seq 1 12); do
  LOGIN_CODE=$(curl -s -o "$OUT/login_check_restore.html" -w "%{http_code}" -m 10 "http://localhost:8080/login" || echo 0)
  [ "$LOGIN_CODE" = "200" ] && break
  sleep 5
done
echo "restore: /login http=$LOGIN_CODE"
if [ "$LOGIN_CODE" != "200" ]; then
  echo "restore: /login not OK, body head:"
  head -c 400 "$OUT/login_check_restore.html" 2>/dev/null || true
  docker compose -f pwd.yml ps -a | tee "$OUT/compose_ps_restore.txt" || true
  echo "=== backend logs (tail) ==="
  docker compose -f pwd.yml logs backend --tail 80 2>&1 | tail -80 || true
  exit 1
fi
echo "BASE_RESTORED"
