# -*- coding: utf-8 -*-
"""ERPNext Web-UI environment adapter (Playwright + Chromium headless).

Agent-facing interface (all methods drive the browser ONLY through this adapter):
  env.observe()            -> compact semantic snapshot of the current page
  env.act(action)          -> one primitive action; returns ActionResult
  env.read_record(dt,name) -> UI readback of persisted field values
  env.actions_used         -> budget counter (protocol cap: 80)

Primitives: navigate / click / fill / select / key / scroll / save / wait.
No DB, no ORM, no REST writes — the agent can only touch ERPNext through the UI.
"""
from __future__ import annotations

import time
from urllib.parse import quote

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8080"


class ActionResult:
    def __init__(self, ok, message, toast=None, saved=None, name=None):
        self.ok = ok
        self.message = message
        self.toast = toast
        self.saved = saved
        self.name = name


class ERPNextEnv:
    def __init__(self, base=BASE, admin_password="admin", headless=True, budget=80):
        self.base = base
        self.budget = budget
        self.actions_used = 0
        self.llm_calls = 0
        self.trajectory = []
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=headless)
        self.ctx = self.browser.new_context(viewport={"width": 1440, "height": 900})
        self.page = self.ctx.new_page()
        self._login(admin_password)

    # ---------------- internals ----------------
    def _login(self, password):
        self.page.goto(self.base + "/login", wait_until="domcontentloaded", timeout=90000)
        self.page.wait_for_selector("#login_email", timeout=60000)
        self.page.fill("#login_email", "Administrator")
        self.page.fill("#login_password", password)
        self.page.click("button.btn-login")
        self.page.wait_for_url(
            lambda url: ("/app" in url) or ("setup-wizard" in url), timeout=90000)
        if "setup-wizard" in self.page.url:
            # v16 SPA wizard route: /desk/setup-wizard. Complete it deterministically
            # (harness bootstrap, not counted against the agent's action budget).
            self._complete_setup_wizard()

    def _complete_setup_wizard(self):
        deadline = time.time() + 180
        for step in range(8):
            url = self.page.url
            if "/app" in url and "setup-wizard" not in url:
                return True
            if time.time() > deadline:
                return False
            for sel, val in (('select[data-fieldname="timezone"]', "Asia/Shanghai"),
                             ('select[data-fieldname="currency"]', "CNY")):
                try:
                    box = self.page.locator(sel).first
                    if box.count():
                        try:
                            box.select_option(value=val)
                        except Exception:
                            opts = box.locator("option").all_inner_texts()
                            match = next((o for o in opts if val in o), None)
                            if match:
                                box.select_option(label=match)
                except Exception:
                    pass
            for key, val in (("company_name", "Wizard Setup Co"), ("company_abbr", "WSC")):
                try:
                    box = self.page.locator(f'input[data-fieldname="{key}"]:visible').first
                    if box.count():
                        box.fill(val)
                except Exception:
                    pass
            clicked = False
            for label in ("Complete Setup", "Next", "Continue", "Finish"):
                try:
                    btn = self.page.locator(f'button:has-text("{label}")').first
                    if btn.count() and btn.is_visible():
                        btn.click(timeout=5000)
                        clicked = True
                        self.page.wait_for_timeout(2500)
                        break
                except Exception:
                    continue
            if not clicked:
                self.page.wait_for_timeout(1500)
        return "/app" in self.page.url

    def _wait_settled(self, ms=800):
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        self.page.wait_for_timeout(ms)

    def _toasts(self):
        out = []
        for sel in (".msgprint", ".alert", ".toast-message", ".indicator-pill"):
            for el in self.page.locator(sel).all():
                try:
                    t = el.inner_text().strip()
                    if t:
                        out.append(t[:200])
                except Exception:
                    pass
        return out[:5]

    # ---------------- observation ----------------
    def observe(self):
        self._wait_settled()
        url = self.page.url
        data = self.page.evaluate(
            """() => {
                const fields = [];
                document.querySelectorAll('[data-fieldname]').forEach(el => {
                    if (!el.offsetParent) return;
                    const fn = el.getAttribute('data-fieldname');
                    if (!fn || ['__newname'].includes(fn)) return;
                    const label = el.querySelector('label.control-label');
                    const input = el.querySelector('input, textarea, select');
                    let value = null, kind = null;
                    if (input) {
                        kind = input.tagName.toLowerCase();
                        value = input.value;
                    } else {
                        const txt = el.querySelector('.control-value');
                        if (txt) { kind = 'static'; value = txt.innerText.trim(); }
                    }
                    if (label || input) fields.push({
                        fieldname: fn,
                        label: label ? label.innerText.trim() : null,
                        kind: kind, value: value
                    });
                });
                const buttons = [];
                document.querySelectorAll('button.btn, .btn').forEach(b => {
                    if (!b.offsetParent) return;
                    const t = (b.innerText || '').trim();
                    if (t && t.length < 40 && !buttons.includes(t)) buttons.push(t);
                });
                const list_rows = [];
                document.querySelectorAll('.list-row').forEach(r => {
                    if (list_rows.length < 20) list_rows.push(r.innerText.replace(/\\s+/g, ' ').trim().slice(0, 160));
                });
                return {title: document.title, fields: fields.slice(0, 40),
                        buttons: buttons.slice(0, 12), list_rows};
            }"""
        )
        return {"url": url, "toasts": self._toasts(), **data}

    # ---------------- actions ----------------
    def act(self, action):
        if self.actions_used >= self.budget:
            return ActionResult(False, "action budget exhausted")
        self.actions_used += 1
        kind = action.get("type")
        try:
            if kind == "navigate":
                url = action["url"]
                if url.startswith("/"):
                    url = self.base + url
                self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
                self._wait_settled()
                return ActionResult(True, "navigated to " + self.page.url)
            if kind == "fill":
                self._fill_field(action["fieldname"], str(action["value"]))
                self._wait_settled()
                return ActionResult(True, f"filled {action['fieldname']}")
            if kind == "select":
                self._select_field(action["fieldname"], str(action["value"]))
                self._wait_settled()
                return ActionResult(True, f"selected {action['fieldname']}={action['value']}")
            if kind == "click":
                text = action.get("text")
                sel = action.get("selector") or f'button:has-text("{text}")'
                self.page.locator(sel).first.click(timeout=15000)
                self._wait_settled()
                return ActionResult(True, f"clicked {text or sel}")
            if kind == "save":
                return self._save()
            if kind == "key":
                self.page.keyboard.press(action["key"])
                self._wait_settled()
                return ActionResult(True, f"pressed {action['key']}")
            if kind == "scroll":
                self.page.mouse.wheel(0, action.get("dy", 600))
                return ActionResult(True, "scrolled")
            if kind == "wait":
                self.page.wait_for_timeout(int(action.get("ms", 1000)))
                return ActionResult(True, "waited")
            return ActionResult(False, f"unknown action type {kind}")
        except Exception as e:
            return ActionResult(False, f"{kind} failed: {str(e)[:180]}")

    def _fill_field(self, fieldname, value):
        el = self.page.locator(f'[data-fieldname="{fieldname}"] input:visible, '
                               f'[data-fieldname="{fieldname}"] textarea:visible').first
        el.wait_for(state="visible", timeout=15000)
        el.fill(value)
        el.press("Tab")

    def _select_field(self, fieldname, value):
        box = self.page.locator(f'[data-fieldname="{fieldname}"] input:visible, '
                                f'[data-fieldname="{fieldname}"] select:visible').first
        box.wait_for(state="visible", timeout=15000)
        tag = box.evaluate("el => el.tagName.toLowerCase()")
        if tag == "select":
            box.select_option(label=value)
            return
        box.fill(value)
        self.page.wait_for_timeout(600)
        opt = self.page.locator(f'[data-fieldname="{fieldname}"] .awesomplete li, '
                                f'.awesomplete li:has-text("{value}")').first
        try:
            opt.wait_for(state="visible", timeout=5000)
            opt.click()
        except Exception:
            box.press("Enter")

    def _save(self):
        btn = self.page.locator('.primary-action:visible, button.btn-primary:has-text("Save"):visible').first
        btn.click(timeout=15000)
        try:
            self.page.wait_for_selector(
                '.indicator-pill:has-text("Saved"), .msgprint, .modal.show', timeout=30000)
        except Exception:
            pass
        self._wait_settled()
        toasts = self._toasts()
        saved = any("Saved" in t for t in toasts)
        err = next((t for t in toasts if "rror" in t or "not save" in t or "Mandatory" in t), None)
        name = None
        parts = self.page.url.rstrip("/").split("/")
        if len(parts) >= 2 and "/new" not in self.page.url:
            name = parts[-1]
        if err:
            return ActionResult(False, "save failed", toast=err, saved=False, name=name)
        return ActionResult(True, "save issued", toast=toasts[0] if toasts else None,
                            saved=saved or "/new" not in self.page.url, name=name)

    # ---------------- UI readback (persisted truth, via UI only) ----------------
    def read_record(self, doctype, name):
        """Open an existing record through the UI and read its persisted field values."""
        if self.actions_used >= self.budget:
            return None
        self.actions_used += 1
        url = f"{self.base}/app/{quote(str(doctype).lower().replace(' ', '-'))}/{quote(str(name))}"
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            obs = self.observe()
            return {f["fieldname"]: f["value"] for f in obs["fields"] if f["value"] not in (None, "")}
        except Exception:
            return None

    def record_exists_ui(self, doctype, name):
        """Existence check through the UI list route."""
        if self.actions_used >= self.budget:
            return False
        self.actions_used += 1
        try:
            self.page.goto(f"{self.base}/app/{quote(str(doctype).lower().replace(' ', '-'))}/{quote(str(name))}",
                           wait_until="domcontentloaded", timeout=60000)
            self._wait_settled(500)
            return "404" not in self.page.title() and "Not Found" not in self.page.title()
        except Exception:
            return False

    def close(self):
        try:
            self.browser.close()
            self._pw.stop()
        except Exception:
            pass
