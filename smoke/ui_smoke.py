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
    res = {"ui_ok": False, "errors": [], "wizard_completed": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
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
            page.goto(BASE + "/app/uom/new", wait_until="domcontentloaded", timeout=90000)
            try:
                page.locator('input[data-fieldname="uom_name"]').first.wait_for(
                    state="visible", timeout=20000)
            except Exception:
                page.goto(BASE + "/desk/uom/new", wait_until="domcontentloaded", timeout=90000)
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
            shot(page, "uom_failed.png")

        save(res)
        print(("SMOKE_UI_OK " if res["ui_ok"] else "SMOKE_UI_FAIL ") + json.dumps(res, ensure_ascii=False))
        browser.close()
        sys.exit(0 if res["ui_ok"] else 3)


main()
