#!/usr/bin/env bash
# Post-run evaluator check: read final DB state from outside the UI path.
# SQL count must be >= 1 for the record created by the UI smoke.
set -uo pipefail
WORKSPACE="${GITHUB_WORKSPACE:-$PWD}"
OUT="$WORKSPACE/smoke-out"
cd "$WORKSPACE/frappe_docker"
mkdir -p "$OUT"

SERVICES=$(docker compose -f pwd.yml config --services)
DBSVC=$(echo "$SERVICES" | grep -E '^(mariadb|db)$' | head -1)
BKSVC=$(echo "$SERVICES" | grep -E '^backend$' | head -1)
echo "services: db=$DBSVC backend=$BKSVC" | tee -a "$OUT/evaluator.txt"

SITE=$(docker compose -f pwd.yml exec -T "$BKSVC" bash -c \
  "ls /home/frappe/frappe-bench/sites | grep -Ev '^(apps|assets|common_site_config.json|sites.txt)$' | head -1" \
  | tr -d '\r\n')
echo "site=$SITE" >> "$OUT/evaluator.txt"

cat > "$OUT/smoke_eval.sql" <<SQL
SELECT COUNT(*) FROM \`tabUOM\` WHERE uom_name = 'Case of 12 (SMOKE)';
SQL

COUNT=$(docker compose -f pwd.yml exec -T "$DBSVC" sh -c "exec mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -N $SITE" \
  < "$OUT/smoke_eval.sql" 2>/dev/null | tail -1)
echo "EVAL_SQL_COUNT=${COUNT:-empty}" | tee -a "$OUT/evaluator.txt"

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
docker compose -f pwd.yml exec -T -e EVAL_SITE="$SITE" "$BKSVC" bash -s <<'EOF' >> "$OUT/evaluator.txt" 2>&1 \
  || echo "EVAL_ORM_UNAVAILABLE (informational)" >> "$OUT/evaluator.txt"
cd /home/frappe/frappe-bench
python3 - <<'PY'
import os
import frappe

frappe.init(site=os.environ["EVAL_SITE"])
frappe.connect()
print("EVAL_ORM_COUNT", frappe.db.count("UOM", {"uom_name": ["like", "%SMOKE%"]}))
frappe.destroy()
PY
EOF

exit $EVAL_RC
