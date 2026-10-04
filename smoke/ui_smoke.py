"""Gate-1 smoke: login to ERPNext via Playwright and create one record through the Web UI.

Proves: Chromium headless works, ERPNext UI works, and a scripted UI action
persists a record that the evaluator can later read back from the database.
Login tries the configured ADMIN_PASSWORD first, then known pwd.yml defaults.
"""
import json
import os
import re
import sys

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
    res = {"ui_ok": False, "errors": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        res["browser_version"] = browser.version

        logged = False
        tried = []
        for pw in [ADMIN_PASSWORD, "admin", "admin123"]:
            if pw in tried:
                continue
            tried.append(pw)
            label = "custom" if pw == ADMIN_PASSWORD else pw
            try:
                page.goto(BASE + "/login", wait_until="domcontentloaded", timeout=90000)
                page.wait_for_selector("#login_email", timeout=60000)
                page.fill("#login_email", "Administrator")
                page.fill("#login_password", pw)
                page.click("button.btn-login")
                page.wait_for_url(re.compile(r"/app|/setup-wizard"), timeout=45000)
                if "/setup-wizard" in page.url:
                    shot(page, "setup_wizard_%d.png" % len(tried))
                    res["errors"].append("login[%s]: setup wizard appeared (setup_complete not applied)" % label)
                    continue
                logged = True
                res["login"] = "ok (password: %s)" % label
                break
            except Exception as e:
                res["errors"].append("login[%s]: %s" % (label, str(e)[:150]))
                shot(page, "login_attempt_%d.png" % len(tried))
        if not logged:
            shot(page, "login_failed.png")
            save(res)
            print("SMOKE_UI_FAIL " + json.dumps(res, ensure_ascii=False))
            sys.exit(2)

        try:
            page.goto(BASE + "/app/uom/new", wait_until="domcontentloaded", timeout=90000)
            inp = page.locator('input[data-fieldname="uom_name"]')
            inp.wait_for(state="visible", timeout=90000)
            inp.fill(UOM_NAME)
            page.get_by_role("button", name="Save", exact=True).click()
            page.wait_for_selector("span.indicator-pill:has-text('Saved')", timeout=90000)
            page.wait_for_timeout(2000)
            res["final_url"] = page.url
            res["ui_ok"] = ("/app/uom/" in page.url) and (not page.url.rstrip("/").endswith("/new"))
            shot(page, "ui_saved.png")
        except Exception as e:
            res["errors"].append("uom: " + str(e)[:300])
            shot(page, "uom_failed.png")

        save(res)
        print(("SMOKE_UI_OK " if res["ui_ok"] else "SMOKE_UI_FAIL ") + json.dumps(res, ensure_ascii=False))
        browser.close()
        sys.exit(0 if res["ui_ok"] else 3)


main()
