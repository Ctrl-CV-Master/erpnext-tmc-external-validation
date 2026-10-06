# -*- coding: utf-8 -*-
"""ERPNext cross-system validation: method layer.

Three method controllers (TMC-AE / R2 ATG-adapted / R3 Task-State-adapted) share
one browser adapter and one LLM interface; ONLY control logic differs.

Task condition model (from tasks_144.jsonl):
  conditions[i] = {
    "id": "C0",
    "doctype": "Work Order",
    "route": "/app/work-order/new",          # form route for a create condition
    "kind": "create" | "edit",
    "match": {...},                           # for edit: how to find the record
    "fields": {"production_item": "PREP-A", "qty": 50},
    "invalidates": ["C1"],                    # Gamma: native ERPNext recal links
    "hint": "human-readable instruction fragment"
  }

Mechanisms (mirror of the frozen hospital-MES kernel, adapted to UI semantics):
  A  initial state read (UI list/record lookups)
  B  direct target confirmation (UI readback of the saved record)
  C  Gamma invalidation before write (q: 1 -> ?)
  D  post-write recalibration readback (affected | full | none)
  E  remaining-task reconstruction every chunk
  F  adaptive recovery entry (min runnable index)
  G  adaptive chunk length (3 -> 1 after an adverse chunk)

Budgets (protocol): 80 browser actions / run; LLM calls <= 2n+16; retry <= 3.
"""
from __future__ import annotations

import json
import time

BROWSER_BUDGET = 80
CHUNK_BIG = 3
CHUNK_SMALL = 1
STALL_LIMIT = 3
MAX_ATTEMPTS = 5

VARIANTS = {
    "TMC": dict(direct_confirm="read", gamma=True, recal="affected", adaptive_entry=True,
                order="index"),
    "R2":  dict(direct_confirm="read", gamma=True, recal="affected", adaptive_entry=False,
                order="topo"),
    "R3":  dict(direct_confirm="read", gamma=False, recal="full", adaptive_entry=False,
                order="index"),
}

REASON_INITIAL = "initial_read"
REASON_DIRECT = "direct_target_confirmation"
REASON_INVAL = "write_impact_invalidation"
REASON_RECAL = "post_write_readback"
REASON_RECOVERY = "recovery"


def _values_match(got, want):
    try:
        if isinstance(want, (int, float)) and got not in (None, ""):
            return abs(float(got) - float(want)) < 1e-4
    except (TypeError, ValueError):
        pass
    return str(got).strip() == str(want).strip()


class Episode:
    def __init__(self, task, method, env, glm, run_id):
        self.task = task
        self.method = method
        self.sw = VARIANTS[method]
        self.env = env
        self.glm = glm
        self.run_id = run_id
        self.conds = task["conditions"]
        self.n = len(self.conds)
        self.true_valid = {i: False for i in range(self.n)}
        self.q = {i: None for i in range(self.n)}
        self.attempts = {i: 0 for i in range(self.n)}
        self.given_up = set()
        self.events = []
        self.trajectory = []
        self.names = {}
        self.t0 = time.time()
        self.cursor = 0
        self.prev_entry = None
        self.stall = 0
        self.last_chunk_dirty = False
        self.terminated = None
        self.c = dict(write_attempts=0, read_ops=0, query_ops=0, wrong_place=0,
                      dup_writes=0, llm_calls=0, invalidated=0, recalibrated=0,
                      entry_backward=0, new_completed=0, recovery_ops=0)

    # ---------------- event log ----------------
    def _ev(self, i, old, new, reason, source, action_id):
        self.events.append({
            "ts": round(time.time() - self.t0, 3), "run_id": self.run_id,
            "condition_id": self.conds[i]["id"],
            "old_state": old, "new_state": new, "reason": reason,
            "source": source, "action_id": action_id})

    def _setq(self, i, new, reason, source, action_id):
        old = self.q[i]
        if old != new:
            self.q[i] = new
            self._ev(i, "pending" if old is None else old, new, reason, source, action_id)
            return True
        return False

    # ---------------- UI truth reads ----------------
    def _read_condition(self, i, reason, source, action_id, count=True):
        """UI readback of condition i's persisted truth. Sets q and returns it."""
        if count:
            self.c["read_ops"] += 1
        cond = self.conds[i]
        name = self.names.get(i)
        got = None
        if name:
            got = self.env.read_record(cond["doctype"], name)
        elif cond["kind"] == "edit":
            got = None
        valid = False
        if got is not None:
            valid = all(_values_match(got.get(k), v) for k, v in cond["fields"].items())
            # submit-requiring conditions: the reward's docstatus expectation
            # is part of the condition truth, not just of the evaluator
            expect_ds = cond.get("expect_docstatus")
            if valid and expect_ds is not None:
                valid = _values_match(got.get("docstatus"), expect_ds)
        self._setq(i, "1" if valid else "0", reason, source, action_id)
        return "1" if valid else "0"

    # ---------------- Gamma ----------------
    def _gamma_mark(self, i, action_id):
        marked = []
        if not self.sw["gamma"]:
            return marked
        for j_str in self.conds[i].get("invalidates", []):
            for j, c in enumerate(self.conds):
                if c["id"] == j_str and self.q.get(j) == "1":
                    if self._setq(j, "?", REASON_INVAL,
                                  "state_layer:gamma_invalidation", action_id):
                        self.c["invalidated"] += 1
                        marked.append(j)
        return marked

    def _recal(self, marked, action_id):
        mode = self.sw["recal"]
        if mode == "none":
            return
        if mode == "affected":
            targets = list(marked)
        else:
            targets = [j for j in range(self.n) if self.q[j] is not None]
        for j in targets:
            self.c["recalibrated"] += 1
            self._read_condition(j, REASON_RECAL, "state_layer:post_write_recal", action_id)

    # ---------------- entry / order ----------------
    def _order(self, runnable):
        if self.sw["order"] == "topo":
            # dependency order: conditions that are invalidated by others come last
            dep_of = {c["id"]: [x for x in c.get("invalidates", [])] for c in self.conds}
            id_to_idx = {c["id"]: i for i, c in enumerate(self.conds)}
            return sorted(runnable, key=lambda i: len(dep_of.get(self.conds[i]["id"], [])))
        return sorted(runnable)

    def _select_entry(self):
        runnable = [i for i in range(self.n)
                    if i not in self.given_up and self.q[i] != "1"]
        if not runnable:
            return None
        ordered = self._order(runnable)
        if self.sw["adaptive_entry"]:
            e = ordered[0]
        else:
            cand = [i for i in ordered if i >= self.cursor]
            e = cand[0] if cand else None
        if e is not None and self.prev_entry is not None and e != self.prev_entry \
                and self.attempts[e] > 0 and self.q[e] != "1":
            self.c["entry_backward"] += 1
            self.c["recovery_ops"] += 1
            self._ev(e, "entry=%s" % self.prev_entry, "entry=%d" % e,
                     REASON_RECOVERY, "state_layer:recovery_entry", "entry")
        self.prev_entry = e
        return e

    # ---------------- LLM: form-fill planning ----------------
    def _plan_fill(self, i):
        """One LLM call: condition spec + observation -> primitive action list."""
        self.c["llm_calls"] += 1
        cond = self.conds[i]
        obs = self.env.observe()
        self.env.last_obs_meta = {
            "rows": len(obs.get("list_rows") or []),
            "links": len(obs.get("row_links") or []),
            "fields": len(obs.get("fields") or []),
            "bytes": len(json.dumps(obs, ensure_ascii=False)),
            "url": obs.get("url", ""),
            "page_text": obs.get("page_text", ""),
            "console": " || ".join(obs.get("console_tail") or [])[:120],
            "perf": str(obs.get("perf") or "")[:150],
        }
        sys_prompt = (
            "You operate ERPNext's web UI through primitives. Return ONLY JSON: "
            "{\"actions\": [...]} where each action is EXACTLY one of:\n"
            '{"type":"navigate","url":"/app/<doctype>/<name>"} (record/list URL; '
            "use row_links hrefs from the observation for existing records)\n"
            '{"type":"fill","fieldname":"<data-fieldname>","value":"<text|number>"}\n'
            '{"type":"select","fieldname":"<data-fieldname>","value":"<exact label>"}\n'
            '{"type":"click","text":"<visible button/link/row text>"}\n'
            '{"type":"set_checkbox","fieldname":"<data-fieldname>","value":true}\n'
            '{"type":"save"}\n'
            '{"type":"key","key":"Enter"}\n'
            "Fill ALL required fields for the condition, then include one save "
            "action. Use exact values given; do not invent data. For Link fields "
            "use the select primitive with the exact target value. To open an "
            "existing record: use its row_links href from the observation. To "
            "submit a document: click Submit, then click Yes in the confirmation "
            "dialog. Plan each attempt as a COMPLETE sequence (locate -> open -> "
            "edit -> save [+ submit]). Do not repeat a navigation you already "
            "made; if a list shows the target row, open it immediately.")
        user = json.dumps({
            "condition": {"doctype": cond["doctype"], "fields": cond["fields"],
                          "hint": cond.get("hint"),
                          "expect_docstatus": cond.get("expect_docstatus")},
            "route": cond.get("route"),
            "observation": obs}, ensure_ascii=False)
        raw = self.glm.chat([
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user}], temperature=0.0, force_json=True)
        try:
            return json.loads(raw).get("actions", [])
        except Exception:
            try:
                return json.loads(raw[raw.index("{"): raw.rindex("}") + 1]).get("actions", [])
            except Exception:
                return []

    # ---------------- one condition ----------------
    def _run_item(self, i):
        cond = self.conds[i]
        dirty = False
        while self.terminated is None:
            if self.q[i] == "1" or i in self.given_up:
                return dirty
            if self.attempts[i] >= MAX_ATTEMPTS:
                self.given_up.add(i)
                return dirty
            if self.env.actions_used >= BROWSER_BUDGET:
                self.terminated = "budget"
                return dirty
            self.attempts[i] += 1
            self.c["write_attempts"] += 1
            action_id = "c%d:a%d" % (i, self.attempts[i])

            marked = self._gamma_mark(i, action_id)

            if cond.get("kind", "create") == "create":
                self.env.open_form(cond["doctype"])
            else:
                self.env.act({"type": "navigate",
                              "url": cond.get("route") or self.env.prefix})
            actions = self._plan_fill(i)
            outcome = "ok"
            name = None
            if not actions:
                outcome = "plan_failed"
            for act in actions:
                if self.env.actions_used >= BROWSER_BUDGET:
                    self.terminated = "budget"
                    break
                r = self.env.act(act)
                self.trajectory.append({
                    "ts": round(time.time() - self.t0, 3), "cond": cond["id"],
                    "attempt": self.attempts[i], "action": act, "result": r.__dict__})
                if act.get("type") == "save":
                    outcome = "ok" if r.saved else ("error" if r.toast else "unconfirmed")
                    name = r.name
            if self.terminated is not None:
                return dirty
            if outcome == "ok":
                self.names[i] = name or self.names.get(i)
                self._read_condition(i, REASON_DIRECT,
                                     "state_layer:direct_target_confirm", action_id)
            else:
                self._setq(i, "0", REASON_DIRECT, "ui_save_failed", action_id)
            self._recal(marked, action_id)
            dirty = True
            if self.q[i] != "1":
                self.last_chunk_dirty = True
            if self.q[i] == "1":
                self.c["new_completed"] += 1
                return dirty
            if outcome == "plan_failed" and self.attempts[i] >= MAX_ATTEMPTS:
                self.given_up.add(i)
                return dirty
        return dirty

    # ---------------- main loop ----------------
    def run(self):
        self.names = {}
        # A: initial state read (conditions pre-created by the fixture)
        for i, cond in enumerate(self.conds):
            if cond.get("pre_existing"):
                self.c["query_ops"] += 1
                self._read_condition(i, REASON_INITIAL, "state_layer:initial_state_read", "init",
                                     count=False)
        self.entry_first = self._select_entry()
        while self.terminated is None:
            runnable = [i for i in range(self.n)
                        if i not in self.given_up and self.q[i] != "1"]
            if not runnable:
                self.terminated = "complete"
                break
            entry = self._select_entry()
            if entry is None:
                self.stall += 1
                if self.stall >= STALL_LIMIT:
                    self.terminated = "stall"
                    break
                continue
            k = CHUNK_SMALL if self.last_chunk_dirty else CHUNK_BIG
            chunk = [i for i in self._order(runnable) if i >= entry][:k] \
                if self.sw["order"] == "index" else \
                [i for i in self._order(runnable)][:k]
            if not chunk:
                self.stall += 1
                if self.stall >= STALL_LIMIT:
                    self.terminated = "stall"
                    break
                continue
            if not self.sw["adaptive_entry"]:
                self.cursor = max(self.cursor, max(chunk) + 1)
            for i in chunk:
                self._run_item(i)
                if self.terminated is not None:
                    break
            if all(self.q[i] == "1" for i in range(self.n)):
                self.terminated = "complete"
                break
            if self.env.actions_used >= BROWSER_BUDGET:
                self.terminated = "budget"
                break
            if self.glm.calls > 2 * self.n + 16:
                self.terminated = "budget_llm"
                break
        for i in range(self.n):
            if self.q[i] != "1":
                self._ev(i, "pending" if self.q[i] is None else self.q[i],
                         "pending" if self.q[i] is None else self.q[i],
                         "final_check", "state_layer:final_check", "final")
        return self.evaluate()

    # ---------------- evaluation (UI-side summary; ORM evaluator is authoritative) ---
    def evaluate(self):
        confirmed = sum(1 for i in range(self.n) if self.q[i] == "1")
        return {
            "method": self.method,
            "conditions_total": self.n,
            "conditions_confirmed": confirmed,
            "browser_actions": self.env.actions_used,
            "llm_usage": self.glm.usage(),
            "write_attempts": self.c["write_attempts"],
            "read_ops": self.c["read_ops"],
            "query_ops": self.c["query_ops"],
            "gamma_invalidations": self.c["invalidated"],
            "recalibrations": self.c["recalibrated"],
            "recovery_entry_changes": self.c["entry_backward"],
            "terminated": self.terminated,
            "wall_clock_s": round(time.time() - self.t0, 1),
            "events": self.events,
        }
