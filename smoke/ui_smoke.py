"""Gate-1 smoke: login to ERPNext via Playwright, complete the setup wizard if it
appears (recording it), then create one record through the Web UI.

On wizard completion we rely on run_evaluator.sh dumping all System Settings
singles so the real wizard-completion flag(s) become visible for baking into
start_erpnext.sh.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "adapter"))
from wizard import complete_setup_wizard  # noqa: E402

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8080"
OUT = os.environ.get("SMOKE_OUT", "smoke-out")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
UOM_NAME = "Case of 12 (SMOKE)"


def shot(page, name):
    try:
        page.screenshot(path=os.path.join(OUT, name))
    except Exception:
        pass


def save(res):
    with open(os.path.join(OUT, "ui_result.json"), "w") as f:
        json.dump(res, f, indent=2)


def main():
    res = {"ui_ok": False, "errors": [], "wizard_completed": False, "console": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # locale is required: on a locale-less Linux runner Chromium reports
        # navigator.languages[0] as "en-US@posix" and the v15 desk
        # (frappe.ui.keys.AltShortcutGroup -> Intl.Locale) crashes on it.
        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                  locale="en-US")
        page = ctx.new_page()
        page.on("pageerror", lambda e: res["console"].append(
            "pageerror: " + str(e)[:300] + " | stack: "
            + (getattr(e, "stack", "") or "")[:700])
            if "pageerror: " + str(e)[:300] not in str(res["console"]) else None)
        page.on("console", lambda m: res["console"].append(f"console.{m.type}: {m.text[:300]}")
                if m.type in ("error", "warning") else None)
        res["browser_version"] = browser.version
        try:
            page.goto(BASE + "/login", wait_until="domcontentloaded", timeout=90000)
            page.wait_for_selector("#login_email", timeout=60000)
            page.fill("#login_email", "Administrator")
            page.fill("#login_password", ADMIN_PASSWORD)
            page.click("button.btn-login")
            page.wait_for_url(lambda u: ("/app" in u) or ("/desk" in u) or ("setup-wizard" in u), timeout=60000)
            res["login"] = "ok"
        except Exception as e:
            res["errors"].append("login: " + str(e)[:250])
            shot(page, "login_failed.png")
            save(res)
            print("SMOKE_UI_FAIL " + json.dumps(res, ensure_ascii=False))
            sys.exit(2)

        if "/setup-wizard" in page.url:
            res["wizard_completed"] = complete_setup_wizard(
                page, ADMIN_PASSWORD, res.setdefault("wizard_log", []),
                shot=lambda pg, n: shot(pg, n))
            if not res["wizard_completed"]:
                shot(page, "wizard_incomplete.png")
                save(res)
                print("SMOKE_UI_FAIL " + json.dumps(res, ensure_ascii=False))
                sys.exit(3)

        try:
            page.goto(BASE + "/app/uom", wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(1500)
            for sel in ('button:has-text("Skip All")',):
                try:
                    el = page.locator(sel).first
                    if el.count() and el.is_visible():
                        el.click(timeout=3000)
                        page.wait_for_timeout(600)
                except Exception:
                    pass
            add = page.locator('button:has-text("Add UOM")').first
            try:
                add.wait_for(state="visible", timeout=15000)
                add.click(timeout=8000)
                page.wait_for_timeout(1500)
            except Exception:
                for route in ("/app/uom/new", "/desk/uom/new"):
                    page.goto(BASE + route, wait_until="domcontentloaded", timeout=90000)
                    if page.locator('input[data-fieldname="uom_name"]').count():
                        break
            inp = page.locator('input[data-fieldname="uom_name"]')
            inp.wait_for(state="visible", timeout=60000)
            inp.fill(UOM_NAME)
            page.get_by_role("button", name="Save", exact=True).click()
            page.wait_for_selector("span.indicator-pill:has-text('Saved')", timeout=90000)
            page.wait_for_timeout(2000)
            res["final_url"] = page.url
            res["ui_ok"] = ("/uom/" in page.url) and (not page.url.rstrip("/").endswith("/new"))
            shot(page, "ui_saved.png")
        except Exception as e:
            res["errors"].append("uom: " + str(e)[:300])
            try:
                res["body_text"] = page.evaluate(
                    "() => document.body.innerText.replace(/\s+/g, ' ').slice(0, 1200)")
                res["buttons"] = page.evaluate(
                    "() => Array.from(document.querySelectorAll('button')).slice(0,30).map(b => b.innerText.trim()).filter(t => t)")
                res["url_final"] = page.url
                res["frames"] = [f.url for f in page.frames]
                res["boot"] = page.evaluate(
                    "() => { try { return {lang: frappe.boot.lang, syslang: frappe.boot.sysdefaults && frappe.boot.sysdefaults.language, ready: !!frappe.boot.ready, user: frappe.session && frappe.session.user, sysdefaults: frappe.boot.sysdefaults, user_lang: frappe.boot.user && frappe.boot.user.language, session_lang: frappe.session && frappe.session.lang}; } catch(e) { return 'boot error: ' + e.message; } }")
                res["locale_probe"] = page.evaluate(
                    """() => {
                    const out = {};
                    if (typeof frappe === 'undefined' || !frappe.boot) return out;
                    const cands = {
                      user_lang: frappe.boot.user && frappe.boot.user.language,
                      sys_lang: frappe.boot.sysdefaults && frappe.boot.sysdefaults.language,
                      boot_lang: frappe.boot.lang,
                      session_lang: frappe.session && frappe.session.lang,
                      nav_lang: (navigator.languages || [navigator.language])[0],
                      html_lang: document.documentElement.lang
                    };
                    for (const [k, v] of Object.entries(cands)) {
                      out[k] = (v === undefined || v === null) ? '<unset>' : v;
                      try { new Intl.DateTimeFormat(v || undefined); out[k + '_ok'] = 'ok'; }
                      catch (e) { out[k + '_ok'] = 'THROWS: ' + e.message; }
                    }
                    return out;
                  }""")
                res["form_input_count"] = page.evaluate(
                    "() => document.querySelectorAll('[data-fieldname]').length")
                res["boot_workspaces"] = page.evaluate(
                    "() => { try { return Object.keys(frappe.boot.workspaces || {}); } catch(e) { return 'err: ' + e.message; } }")
                res["sidebar_links"] = page.evaluate(
                    """() => Array.from(document.querySelectorAll('.sidebar-item, a.sidebar-link'))
                        .slice(0, 40).map(a => (a.getAttribute('href') || a.innerText || '').trim().slice(0, 60))
                        .filter(t => t)""")
            except Exception as e:
                res["diag_error"] = str(e)[:200]
            shot(page, "uom_failed.png")

        save(res)
        print(("SMOKE_UI_OK " if res["ui_ok"] else "SMOKE_UI_FAIL ") + json.dumps(res, ensure_ascii=False))
        browser.close()
        sys.exit(0 if res["ui_ok"] else 3)


main()
