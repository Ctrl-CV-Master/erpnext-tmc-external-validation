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


from wizard import complete_setup_wizard  # noqa: E402


class ERPNextEnv:
    def __init__(self, base=BASE, admin_password="admin", headless=True, budget=80):
        self.base = base
        self.budget = budget
        self.actions_used = 0
        self.llm_calls = 0
        self.trajectory = []
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=headless)
        self.ctx = self.browser.new_context(viewport={"width": 1440, "height": 900},
                                            locale="en-US")
        self.page = self.ctx.new_page()
        self.prefix = "/app"
        self._login(admin_password)

    # ---------------- internals ----------------
    def _login(self, password):
        last_err = None
        for attempt in (1, 2):
            try:
                self.page.goto(self.base + "/login", wait_until="domcontentloaded",
                               timeout=90000)
                self.page.wait_for_selector("#login_email", timeout=45000)
                break
            except Exception as e:
                last_err = e
                if attempt == 2:
                    raise
                try:
                    self.page.reload(wait_until="domcontentloaded", timeout=90000)
                except Exception:
                    pass
        self.page.fill("#login_email", "Administrator")
        self.page.fill("#login_password", password)
        self.page.click("button.btn-login")
        self.page.wait_for_url(
            lambda url: ("/app" in url) or ("/desk" in url), timeout=90000)
        from urllib.parse import urlparse
        path = urlparse(self.page.url).path or "/"
        self.prefix = "/desk" if path.startswith("/desk") else "/app"
        if "setup-wizard" in self.page.url:
            # Harness bootstrap (not counted against the agent's action budget).
            self.wizard_log = []
            complete_setup_wizard(self.page, password, self.wizard_log,
                                  shot=lambda pg, n: pg.screenshot(path=n))
            self.page.goto(self.base + self.prefix, wait_until="domcontentloaded",
                           timeout=90000)
        self._wait_settled()
        self._dismiss_onboarding()

    def _dismiss_onboarding(self):
        for sel in ('button:has-text("Skip All")',
                    '.onboarding-step-wrapper button.close',
                    '#page-desktop .btn-close'):
            try:
                el = self.page.locator(sel).first
                if el.count() and el.is_visible():
                    el.click(timeout=3000)
                    self.page.wait_for_timeout(600)
                    return
            except Exception:
                continue

    def open_form(self, doctype):
        """Open a new-document form. Prefer the /new route: it renders the full
        form directly (v15 list "Add <DocType>" opens a quick-entry dialog over
        the list whose filter inputs share data-fieldnames with form fields and
        shadow them). Falls back to list -> Add button when the route does not
        render a form."""
        slug = doctype.lower().replace(" ", "-")
        self.page.goto(self.base + f"{self.prefix}/{slug}/new",
                       wait_until="domcontentloaded", timeout=60000)
        self._wait_settled()
        self._dismiss_onboarding()
        try:
            if self.page.evaluate(
                    "() => !!(window.cur_frm && cur_frm.doc)"):
                return
        except Exception:
            pass
        try:
            self.page.goto(self.base + f"{self.prefix}/{slug}",
                           wait_until="domcontentloaded", timeout=60000)
            self._wait_settled()
            self._dismiss_onboarding()
            add = self.page.locator(f'button:has-text("Add {doctype}")').first
            add.wait_for(state="visible", timeout=10000)
            add.click(timeout=8000)
            self._wait_settled()
            return
        except Exception:
            pass
        self.page.goto(self.base + f"{self.prefix}/{slug}/new",
                       wait_until="domcontentloaded", timeout=60000)
        self._wait_settled()
        self._dismiss_onboarding()

    def _fix_url(self, url):
        """v16 moved the desk from /app to /desk; rewrite task-given /app routes."""
        if url.startswith("/app") and self.prefix == "/desk":
            return self.base + "/desk" + url[len("/app"):]
        return (self.base + url) if url.startswith("/") else url

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
        # list views render rows asynchronously after networkidle; give them a
        # window or the observation shows an empty list and agents loop on
        # re-navigation
        try:
            self.page.wait_for_selector(".list-row", timeout=6000)
            self.page.wait_for_timeout(500)
        except Exception:
            pass
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
                const row_links = [];
                document.querySelectorAll('.list-row a[href*="/app/"]').forEach(a => {
                    if (row_links.length < 20) row_links.push({
                        text: (a.innerText || '').trim().slice(0, 80),
                        href: a.getAttribute('href')});
                });
                return {title: document.title, fields: fields.slice(0, 40),
                        buttons: buttons.slice(0, 12), list_rows, row_links};
            }"""
        )
        return {"url": url, "toasts": self._toasts(), **data}

    # ---------------- actions ----------------
    def act(self, action):
        if self.actions_used >= self.budget:
            return ActionResult(False, "action budget exhausted")
        self.actions_used += 1
        result = self._act_impl(action)
        meta = getattr(self, "last_obs_meta", None)
        if meta:
            result.message = (result.message or "") + (
                f" [obs {meta.get('rows', 0)}r/{meta.get('links', 0)}l"
                f" {meta.get('fields', 0)}f {meta.get('bytes', 0)}b]")
        return result

    def _act_impl(self, action):
        kind = action.get("type")
        try:
            if kind == "navigate":
                # GLM planners name the target inconsistently; accept the
                # common aliases
                url = (action.get("url") or action.get("to") or action.get("href")
                       or action.get("target") or action.get("value"))
                if not url:
                    return ActionResult(
                        False, "navigate failed: no url (keys="
                        + str(sorted(k for k in action.keys() if k != "type")) + ")")
                url = self._fix_url(str(url))
                self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
                self._wait_settled()
                return ActionResult(True, "navigated to " + self.page.url)
            if kind == "fill":
                try:
                    self._fill_field(action["fieldname"], str(action["value"]))
                except Exception as e:
                    return ActionResult(False, "fill failed: " + str(e)[:160]
                                        + " | fields: " + self._field_visibility_dump()[:300])
                self._wait_settled()
                note = getattr(self, "_last_expand_note", "")
                fill_note = getattr(self, "_last_fill_note", "")
                self._last_expand_note = ""
                self._last_fill_note = ""
                where = self.page.url.rsplit("/", 1)[-1][:36]
                extra = (note + " " + fill_note).strip()
                return ActionResult(True, f"filled {action['fieldname']}{extra} @{where}")
            if kind == "set_checkbox":
                self._fill_field(action["fieldname"], action.get("value", 1))
                self._wait_settled()
                return ActionResult(True, f"set {action['fieldname']}={action.get('value')}")
            if kind == "select":
                self._select_field(action["fieldname"], str(action["value"]))
                self._wait_settled()
                return ActionResult(True, f"selected {action['fieldname']}={action['value']}")
            if kind == "click":
                if action.get("selector"):
                    self.page.locator(action["selector"]).first.click(timeout=15000)
                else:
                    # accept the key names GLM planners actually emit
                    text = (action.get("text") or action.get("target")
                            or action.get("label") or action.get("value"))
                    clicked = False
                    last = None
                    # cascade: buttons first, then links, then list rows/cells
                    for sel in (f'button:has-text("{text}")',
                                f'a:has-text("{text}")',
                                f'.list-row:has-text("{text}")',
                                f'td:has-text("{text}")'):
                        try:
                            self.page.locator(sel).first.click(timeout=2500)
                            clicked = True
                            break
                        except Exception as e:
                            last = e
                    if not clicked:
                        raise RuntimeError(f"no clickable '{text}': {str(last)[:90]}")
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

    def _expand_collapsed_sections(self):
        """v15 forms keep some sections (e.g. Work Order warehouses) collapsed;
        click their heads so the fields become reachable. Returns count."""
        try:
            return self.page.evaluate(
                """() => {
                let n = 0;
                document.querySelectorAll('.form-layout .form-section').forEach(sec => {
                  const body = sec.querySelector('.section-body');
                  if (body && getComputedStyle(body).display === 'none') {
                    const head = sec.querySelector('.section-head');
                    if (head) { head.click(); n++; }
                  }
                });
                return n;
              }""")
        except Exception:
            return 0

    def _field_visibility_dump(self):
        try:
            return self.page.evaluate(
                """() => {
                const out = [];
                document.querySelectorAll('.form-layout [data-fieldname]').forEach(e => {
                  const r = e.getBoundingClientRect();
                  out.push((e.getAttribute('data-fieldname') || '?') +
                           (r.width > 0 && r.height > 0 ? ':V' : ':H'));
                });
                return out.slice(0, 60).join(' ');
              }""")
        except Exception:
            return "dump failed"

    def _reveal_field(self, fieldname):
        """Expand collapsed sections and activate the tab that holds fieldname.
        Returns a short status string for the trajectory."""
        expanded = self._expand_collapsed_sections()
        status = self.page.evaluate(
            """(fn) => {
            const el = document.querySelector('[data-fieldname="' + fn + '"]');
            if (!el) return 'absent';
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) return 'visible';
            const pane = el.closest('.tab-pane');
            if (pane && pane.id) {
              const link = document.querySelector(
                '.nav-link[href="#' + pane.id + '"], [data-target="#' + pane.id + '"]');
              if (link) { link.click(); return 'tab-activated'; }
            }
            return 'hidden';
          }""", fieldname)
        return f"expanded={expanded} reveal={status}"

    def _field_model_value(self, fieldname):
        """Committed model value from cur_frm (form) or cur_dialog (quick
        entry), or {'has_frm': False} when neither is present."""
        try:
            return self.page.evaluate(
                """(fn) => {
                if (window.cur_frm && cur_frm.doc) return {has_frm: true, value: cur_frm.doc[fn]};
                if (window.cur_dialog && cur_dialog.get_value) {
                  try { return {has_frm: true, value: cur_dialog.get_value(fn)}; } catch(e) {}
                }
                return {has_frm: false};
              }""", fieldname)
        except Exception:
            return {"has_frm": False}

    @staticmethod
    def _model_matches(got, want):
        if got is None:
            return False
        try:
            if isinstance(want, (int, float)):
                return abs(float(got) - float(want)) < 1e-6
        except (TypeError, ValueError):
            pass
        return str(got).strip() == str(want).strip()

    def _fill_field(self, fieldname, value):
        """Fill a form field with layered fallbacks; records the path used:
        checkbox -> input fill (+model verify -> link select -> rich text
        editor contenteditable -> frappe set_value). A missing input/textarea
        (iframe-rendered editors like TinyMCE) is not fatal: the chain falls
        through to the editor paths."""
        el = self.page.locator(f'[data-fieldname="{fieldname}"] input:visible, '
                               f'[data-fieldname="{fieldname}"] textarea:visible').first
        input_ok = True
        try:
            el.wait_for(state="visible", timeout=4000)
        except Exception:
            note = self._reveal_field(fieldname)
            try:
                el.wait_for(state="visible", timeout=8000)
                self._last_expand_note = f" ({note})"
            except Exception:
                input_ok = False

        if input_ok and el.evaluate("el => el.type || ''") == "checkbox":
            el.set_checked(bool(value) and str(value) not in ("0", "false", "False"))
            self.page.wait_for_timeout(300)
            self._last_fill_note = "checkbox"
            return

        if input_ok:
            el.fill(value)
            el.press("Tab")
            self.page.wait_for_timeout(400)
            if self._model_matches_field(fieldname, value, el):
                return

        if input_ok:
            # link/select did not commit: awesomplete selection path
            el.fill(value)
            self.page.wait_for_timeout(700)
            tag = (el.evaluate("el => el.tagName.toLowerCase()")
                  if el.count() else "input")
            if tag == "select":
                el.select_option(label=value)
            else:
                opt = self.page.locator(
                    f'.frappe-control[data-fieldname="{fieldname}"] .awesomplete li, '
                    f'[data-fieldname="{fieldname}"] .awesomplete li').first
                try:
                    opt.wait_for(state="visible", timeout=4000)
                    opt.click()
                except Exception:
                    el.press("Enter")
            self.page.wait_for_timeout(500)
            if self._model_matches_field(fieldname, value, el):
                self._last_fill_note = "via-link-select"
                return

        # rich text editor (contenteditable) — description-like fields
        ce = self.page.locator(
            f'[data-fieldname="{fieldname}"] [contenteditable="true"]').first
        if ce.count():
            ce.click()
            ce.fill(str(value))
            self.page.wait_for_timeout(400)
            if self._model_matches_field(fieldname, value, el):
                self._last_fill_note = "via-contenteditable"
                return

        # last resort: frappe model-level set (used when the widget renders in
        # an iframe, e.g. TinyMCE text editors, or when a quick-entry dialog's
        # input text did not bind). Applies to cur_frm, else cur_dialog.
        applied = self.page.evaluate(
            """(a) => {
            if (window.cur_frm && cur_frm.doc) { cur_frm.set_value(a.f, a.v); return true; }
            if (window.cur_dialog && cur_dialog.set_value) {
              try { cur_dialog.set_value(a.f, a.v); return true; } catch(e) {}
            }
            return false;
          }""", {"f": fieldname, "v": str(value)})
        if not applied:
            raise RuntimeError(
                f"no form open for '{fieldname}' (page is not an editable document form)")
        self.page.wait_for_timeout(400)
        self._last_fill_note = "via-set_value"

    def _model_matches_field(self, fieldname, value, el):
        mv = self._field_model_value(fieldname)
        if mv.get("has_frm"):
            return self._model_matches(mv.get("value"), value)
        # quick-entry dialogs have no cur_frm: the input value itself is the
        # authoritative state there
        try:
            return self._model_matches(el.input_value(), value)
        except Exception:
            return True

    def _select_field(self, fieldname, value):
        box = self.page.locator(f'[data-fieldname="{fieldname}"] input:visible, '
                                f'[data-fieldname="{fieldname}"] select:visible').first
        try:
            box.wait_for(state="visible", timeout=4000)
        except Exception:
            self._reveal_field(fieldname)
            box.wait_for(state="visible", timeout=12000)
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
        # Click the first Save control that actually receives the click.
        # v15 opens a quick-entry dialog for /app/<dt>/new on simple doctypes:
        # the list head "Add <dt>" stays .primary-action but is covered by the
        # modal overlay, so candidates must be tried with short actionability
        # timeouts, modal-first, rather than one long-wait locator.
        clicked = None
        last_err = None
        for sel in ('.modal.show button.btn-primary:visible',
                    '.primary-action:visible',
                    '.btn-primary-action:visible',
                    'button[data-label="Save"]:visible',
                    'button.btn-primary:has-text("Save"):visible'):
            loc = self.page.locator(sel).first
            try:
                loc.click(timeout=2500)
                clicked = sel
                break
            except Exception as e:
                last_err = str(e)[:100]
                continue
        if clicked is None:
            head = self.page.evaluate(
                "() => Array.from(document.querySelectorAll("
                "'.page-head button, .modal.show button'))"
                ".map(b => (b.className || '') + '|' + (b.innerText || '').trim())"
                ".join(' ;; ')")
            return ActionResult(False, "save failed: no clickable Save control ("
                                + str(last_err) + "); head: " + str(head)[:140])
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
        """Open an existing record through the UI and read its persisted field values.
        Reads hidden-tab fields too: the value lives in the input regardless of
        which v15 tab pane is active (observe() stays visibility-faithful for
        agent observations; this is the harness's own persisted-truth readback)."""
        if self.actions_used >= self.budget:
            return None
        self.actions_used += 1
        url = self._fix_url(f"/app/{quote(str(doctype).lower().replace(' ', '-'))}/{quote(str(name))}")
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            self._wait_settled()
            try:
                self.page.wait_for_selector(".form-layout [data-fieldname]", timeout=15000)
            except Exception:
                pass
            fields = self.page.evaluate(
                """() => {
                    const out = [];
                    document.querySelectorAll('.form-layout [data-fieldname]').forEach(el => {
                        const fn = el.getAttribute('data-fieldname');
                        if (!fn || fn.indexOf('__') === 0) return;
                        const input = el.querySelector('input, textarea, select');
                        let value = null;
                        if (input) value = input.value;
                        else {
                            const txt = el.querySelector('.control-value');
                            if (txt) value = txt.innerText.trim();
                        }
                        if (value !== null && value !== '') out.push({fieldname: fn, value: value});
                    });
                    return out;
                }""")
            return {f["fieldname"]: f["value"] for f in fields}
        except Exception:
            return None

    def record_exists_ui(self, doctype, name):
        """Existence check through the UI list route."""
        if self.actions_used >= self.budget:
            return False
        self.actions_used += 1
        try:
            self.page.goto(self._fix_url(
                f"/app/{quote(str(doctype).lower().replace(' ', '-'))}/{quote(str(name))}"),
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
