#!/usr/bin/env bash
# Post-run evaluator check: read final DB state from outside the UI path.
# SQL count must be >= 1 for the record created by the UI smoke.
set -uo pipefail
WORKSPACE="${GITHUB_WORKSPACE:-$PWD}"
OUT="$WORKSPACE/smoke-out"
cd "$WORKSPACE/frappe_docker"

SERVICES=$(docker compose -f pwd.yml config --services)
DBSVC=$(echo "$SERVICES" | grep -E '^(mariadb|db)$' | head -1)
BKSVC=$(echo "$SERVICES" | grep -E '^backend$' | head -1)
DB=$(grep -m1 '^erpnext_db=' "$OUT/manifest.env" | cut -d= -f2)
echo "services: db=$DBSVC backend=$BKSVC db_name=$DB" | tee -a "$OUT/evaluator.txt"

cat > "$OUT/smoke_eval.sql" <<SQL
SELECT COUNT(*) FROM \`tabUOM\` WHERE uom_name = 'Case of 12 (SMOKE)';
SQL

COUNT=$(docker compose -f pwd.yml exec -T "$DBSVC" sh -c "exec mariadb -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -N $DB" \
  < "$OUT/smoke_eval.sql" 2>/dev/null | tail -1)
echo "EVAL_SQL_COUNT=${COUNT:-empty}" | tee -a "$OUT/evaluator.txt"

# Dump all System Settings singles: reveals the real setup-wizard completion flag(s).
docker compose -f pwd.yml exec -T "$DBSVC" sh -c \
  "exec mariadb -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -N -e \"SELECT field, value FROM tabSingles WHERE doctype='System Settings' ORDER BY field;\" $DB" \
  >> "$OUT/evaluator.txt" 2>&1 || true

EVAL_RC=1
if [ "${COUNT:-0}" -ge 1 ] 2>/dev/null; then
  echo "EVALUATOR_PASS" | tee -a "$OUT/evaluator.txt"
  EVAL_RC=0
else
  echo "EVALUATOR_FAIL" | tee -a "$OUT/evaluator.txt"
  EVAL_RC=4
fi

# Informational: frappe ORM read path inside the backend container
# (this is the access pattern the full evaluator will use at Gate 2+).
BENCH_PY=$(docker compose -f pwd.yml exec -T "$BKSVC" bash -c \
  'for p in /home/frappe/frappe-bench/env/bin/python /home/frappe/frappe-bench/env/bin/python3; do [ -x "$p" ] && echo "$p" && exit 0; done; head -1 "$(command -v bench)" | sed "s/^#!//"' | tail -1)
docker compose -f pwd.yml exec -T -u root backend mkdir -p /home/frappe/logs /home/frappe/frappe-bench/logs
docker compose -f pwd.yml exec -T -u root -e EVAL_SITE="$(grep -m1 '^erpnext_site=' "$OUT/manifest.env" | cut -d= -f2)" "$BKSVC" \
  "$BENCH_PY" -c "
import os, frappe
frappe.init(site=os.environ['EVAL_SITE'], sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
print('EVAL_ORM_COUNT', frappe.db.count('UOM', {'uom_name': ['like', '%SMOKE%']}))
frappe.destroy()
" >> "$OUT/evaluator.txt" 2>&1 || echo "EVAL_ORM_UNAVAILABLE (informational)" >> "$OUT/evaluator.txt"

exit $EVAL_RC
