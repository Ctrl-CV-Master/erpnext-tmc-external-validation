"""Gate-1 smoke: login to ERPNext via Playwright, complete the setup wizard if it
appears (recording it), then create one record through the Web UI.

On wizard completion we rely on run_evaluator.sh dumping all System Settings
singles so the real wizard-completion flag(s) become visible for baking into
start_erpnext.sh.
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


def complete_wizard(page, res):
    """Deterministically complete the setup wizard at /setup-wizard (the page the
    post-login server redirect lands on; /desk/* wizard URLs are SPA-internal only)."""
    log = res.setdefault("wizard_log", [])
    page.goto(BASE + "/setup-wizard", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(2500)
    for step in range(6):
        shot(page, f"wizard_step{step}.png")
        url = page.url
        log.append(f"step{step} url={url}")
        if "/app" in url and "/setup-wizard" not in url:
            log.append("wizard finished")
            return True
        # language/timezone/currency step
        try:
            tz = page.locator('select[data-fieldname="timezone"], select:visible').first
            if tz.count():
                try:
                    tz.select_option(label=re.compile("Asia/Shanghai"))
                except Exception:
                    opts = tz.locator("option").all_inner_texts()
                    match = next((o for o in opts if "Shanghai" in o or "Hong_Kong" in o), None)
                    if match:
                        tz.select_option(label=match)
        except Exception as e:
            log.append(f"tz select: {str(e)[:80]}")
        try:
            cur = page.locator('select[data-fieldname="currency"]').first
            if cur.count():
                cur.select_option(value="CNY")
        except Exception:
            pass
        # organization-ish text inputs, if this is that step
        for key, val in (("company_name", "Wizard Setup Co"), ("company_abbr", "WSC")):
            try:
                box = page.locator(f'input[data-fieldname="{key}"]:visible').first
                if box.count():
                    box.fill(val)
            except Exception:
                pass
        # click Next / Complete / Continue
        clicked = False
        for label in ("Complete Setup", "Next", "Continue", "Setup", "Finish"):
            try:
                btn = page.locator(f'button:has-text("{label}")').first
                if btn.count() and btn.is_visible():
                    btn.click(timeout=5000)
                    clicked = True
                    log.append(f"clicked {label}")
                    page.wait_for_timeout(2500)
                    break
            except Exception:
                continue
        if not clicked:
            # maybe a "skip" path exists
            for label in ("Skip", "Not now"):
                try:
                    lnk = page.locator(f'a:has-text("{label}"), button:has-text("{label}")').first
                    if lnk.count() and lnk.is_visible():
                        lnk.click(timeout=5000)
                        log.append(f"clicked {label}")
                        page.wait_for_timeout(2500)
                        clicked = True
                        break
                except Exception:
                    continue
        if not clicked:
            log.append("no button found; stopping wizard loop")
            shot(page, "wizard_stuck.png")
            return "/app" in page.url
    return "/app" in page.url


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
            page.wait_for_url(lambda u: ("/app" in u) or ("/setup-wizard" in u), timeout=60000)
            res["login"] = "ok"
        except Exception as e:
            res["errors"].append("login: " + str(e)[:250])
            shot(page, "login_failed.png")
            save(res)
            print("SMOKE_UI_FAIL " + json.dumps(res, ensure_ascii=False))
            sys.exit(2)

        if "/setup-wizard" in page.url:
            res["wizard_completed"] = complete_wizard(page, res)
            if not res["wizard_completed"]:
                shot(page, "wizard_incomplete.png")
                save(res)
                print("SMOKE_UI_FAIL " + json.dumps(res, ensure_ascii=False))
                sys.exit(3)

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
