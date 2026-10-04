# -*- coding: utf-8 -*-
"""Deterministic ERPNext setup-wizard completer (shared by smoke and adapter).

The v16 wizard is an SPA at /setup-wizard whose internal step URL does not
change, so steps are identified by their visible required inputs. Fills, in
order: language/country/timezone/currency -> account -> organization -> finish.
"""
import re
import time


def _fill_input(page, fieldnames, value, label_hint=None):
    for fn in fieldnames:
        try:
            box = page.locator(f'input[data-fieldname="{fn}"]:visible').first
            if box.count():
                if (box.input_value() or "").strip():
                    return True
                box.fill(value)
                return True
        except Exception:
            continue
    if label_hint:
        try:
            box = page.locator(
                f'.control:has(label:has-text("{label_hint}")) input:visible').first
            if box.count():
                if (box.input_value() or "").strip():
                    return True
                box.fill(value)
                return True
        except Exception:
            pass
    return False


def _fill_password(page, fieldnames, value, label_hint=None):
    for fn in fieldnames:
        try:
            box = page.locator(f'input[type="password"][data-fieldname="{fn}"]:visible, '
                               f'input[type="password"]:visible').first
            if box.count():
                if (box.input_value() or "").strip():
                    return True
                box.fill(value)
                return True
        except Exception:
            continue
    if label_hint:
        try:
            box = page.locator(
                f'.control:has(label:has-text("{label_hint}")) input[type="password"]:visible').first
            if box.count() and not (box.input_value() or "").strip():
                box.fill(value)
                return True
        except Exception:
            pass
    return False


def _select(page, fieldnames, prefer, exact=None):
    for fn in fieldnames:
        try:
            box = page.locator(f'select[data-fieldname="{fn}"]:visible').first
            if box.count():
                if box.input_value():
                    return True
                if exact:
                    try:
                        box.select_option(value=exact)
                        return True
                    except Exception:
                        pass
                opts = box.locator("option").all_inner_texts()
                for pat in prefer:
                    m = next((o for o in opts if re.search(pat, o)), None)
                    if m:
                        box.select_option(label=m)
                        return True
        except Exception:
            continue
    return False


def _fill_link(page, fieldnames, value, label_hint=None):
    for fn in fieldnames:
        try:
            box = page.locator(f'input[data-fieldname="{fn}"]:visible').first
            if box.count():
                if (box.input_value() or "").strip():
                    return True
                box.fill(value)
                page.wait_for_timeout(900)
                opt = page.locator(f'.awesomplete li:has-text("{value}")').first
                try:
                    opt.wait_for(state="visible", timeout=4000)
                    opt.click()
                except Exception:
                    box.press("Enter")
                page.wait_for_timeout(400)
                return True
        except Exception:
            continue
    if label_hint:
        try:
            box = page.locator(
                f'.control:has(label:has-text("{label_hint}")) input:visible').first
            if box.count() and not (box.input_value() or "").strip():
                box.fill(value)
                page.wait_for_timeout(900)
                opt = page.locator(f'.awesomplete li:has-text("{value}")').first
                try:
                    opt.wait_for(state="visible", timeout=4000)
                    opt.click()
                except Exception:
                    box.press("Enter")
                return True
        except Exception:
            pass
    return False


def _at_desk(url):
    """v16: the desk lives at /desk (older /app also possible)."""
    return ("setup-wizard" not in url) and ("/app" in url or "/desk" in url)


def complete_setup_wizard(page, admin_password, log, shot=None):
    """Returns True when the desk (/app) is reached."""
    if "setup-wizard" not in page.url:
        page.goto(page.url.split("/app")[0] + "/setup-wizard",
                  wait_until="domcontentloaded", timeout=90000)
    deadline = time.time() + 240
    for step in range(14):
        try:
            page.wait_for_timeout(1500)
            url = page.url
            if _at_desk(url):
                log.append(f"step{step}: desk reached")
                return True
            log.append(f"step{step} url={url}")
            if shot:
                shot(page, f"wizard_step{step}.png")

            did = []
            if _fill_link(page, ["country"], "China", "Your Country"):
                did.append("country")
            if _select(page, ["timezone", "time_zone"], [r"Shanghai", r"Hong_Kong"]):
                did.append("timezone")
            if _select(page, ["currency"], [], exact="CNY"):
                did.append("currency")
            if _fill_input(page, ["full_name", "fname"], "Administrator", "Full Name"):
                did.append("full_name")
            if _fill_input(page, ["email", "email_address"], "admin@example.com", "Email"):
                did.append("email")
            if _fill_password(page, ["password", "pwd"], admin_password, "Password"):
                did.append("password")
            # v16 survey step: generic fill of every empty visible select
            try:
                for box in page.locator("select:visible").all():
                    try:
                        if not (box.input_value() or "").strip():
                            opts = box.locator("option").all_inner_texts()
                            choice = next(
                                (o for o in opts if o.strip() and not o.strip().startswith("Select")),
                                None)
                            if choice:
                                box.select_option(label=choice)
                                did.append("survey")
                    except Exception:
                        continue
            except Exception:
                pass
            # tick module checkboxes relevant to the synthetic manufacturer
            for lbl in ("Manufacturing", "Stock", "Accounting"):
                try:
                    cb = page.locator(
                        f'.checkbox:has-text("{lbl}") input, label:has-text("{lbl}") input').first
                    if cb.count() and not cb.is_checked():
                        cb.check()
                        did.append("check:" + lbl)
                except Exception:
                    pass
            if _fill_input(page, ["company_name"], "Wizard Setup Co", "Company Name"):
                did.append("company_name")
            if _fill_input(page, ["company_abbr", "abbr"], "WSC", "Abbr"):
                did.append("abbr")
            log.append(f"step{step} filled={did}")

            clicked = False
            for label in ("Complete Setup", "Next", "Continue", "Finish", "Start", "Go", "Let's go", "Go to"):
                try:
                    btn = page.locator(f'button:has-text("{label}")').first
                    btn.wait_for(state="visible", timeout=4000)
                    btn.click(timeout=5000)
                    clicked = True
                    log.append(f"clicked {label}")
                    if label in ("Complete Setup", "Finish"):
                        # the backend now creates company/modules; this takes minutes
                        try:
                            page.wait_for_url(
                                lambda u: _at_desk(u), timeout=300000)
                            log.append("desk reached after setup")
                            return True
                        except Exception:
                            log.append("timeout waiting for desk after setup")
                    page.wait_for_timeout(2500)
                    break
                except Exception:
                    continue
            if not clicked:
                # a blocking modal may be up; close it and retry once
                try:
                    x = page.locator('.modal.show .btn-close, .modal.show button[data-dismiss="modal"]').first
                    if x.count() and x.is_visible():
                        x.click(timeout=2000)
                        log.append("closed modal")
                        page.wait_for_timeout(800)
                except Exception:
                    pass
            if time.time() > deadline:
                break
        except Exception as e:
            log.append(f"step{step} error: {str(e)[:120]}")
            page.wait_for_timeout(1500)
    return _at_desk(page.url)
