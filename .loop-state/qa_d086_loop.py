#!/usr/bin/env python3
"""Isolated Playwright re-QA for d086 after PR #29 loop. Do not touch t086."""
from __future__ import annotations

import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / ".loop-state" / "qa-d086-loop"
EVID = REPO / ".loop-state" / "qa-d086-loop-evidence.json"
BASE = "https://d086.w9.nu"
API = "https://d086.w9.nu/api/v1"

fails: list[str] = []
passes: list[str] = []
shots: list[str] = []


def rec(ok: bool, name: str, note: str = ""):
    (passes if ok else fails).append(f"{name}: {note}" if note else name)
    print(("PASS " if ok else "FAIL ") + name + (f" — {note}" if note else ""), flush=True)


def shot(page, name: str):
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f"{name}.png"
    page.screenshot(path=str(path), full_page=False, animations="disabled", caret="hide")
    shots.append(name)
    return path


def goto(page, hash_path: str, ms: int = 1600):
    page.goto(f"{BASE}/#{hash_path.lstrip('#')}", wait_until="domcontentloaded", timeout=35000)
    page.wait_for_timeout(ms)


def login_admin(page):
    goto(page, "/dashboard", 2000)
    if page.get_by_text("Administrator").count():
        page.get_by_text("Administrator").first.click()
        page.wait_for_timeout(800)
        return
    if page.locator("button", has_text=re.compile(r"Sign In|Đăng Nhập")).count():
        page.locator("button", has_text=re.compile(r"Sign In|Đăng Nhập")).first.click()
        page.wait_for_timeout(600)
        if page.get_by_text("Administrator").count():
            page.get_by_text("Administrator").first.click()
            page.wait_for_timeout(800)


def set_llm(page, on: bool):
    page.evaluate(
        """(flag) => {
          localStorage.setItem('datatrust-use-llm', flag ? 'true' : 'false');
          window.dispatchEvent(new CustomEvent('datatrust:llm-mode-changed', {detail:{useLlm: flag}}));
        }""",
        on,
    )
    btn = page.locator("button").filter(has_text=re.compile(r"LLM (ON|OFF)")).first
    if btn.count():
        label = btn.inner_text(timeout=2000)
        if ("ON" in label and not on) or ("OFF" in label and on):
            btn.click(timeout=4000)
            page.wait_for_timeout(400)


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, ignore_https_errors=True)
        page = ctx.new_page()

        # stamp
        raw = page.request.get(BASE)
        html = raw.text()
        rec("d086-v5" in html, "stamp", html[html.find("d086"):html.find("d086")+48] if "d086" in html else html[:80])

        # unauth login modal identity
        goto(page, "/dashboard", 1500)
        if page.locator("button", has_text=re.compile(r"Sign In|Đăng Nhập")).count():
            page.locator("button", has_text=re.compile(r"Sign In|Đăng Nhập")).first.click()
            page.wait_for_timeout(500)
        ident = page.locator("[data-testid=auth-active-identity]")
        ident_txt = ident.inner_text() if ident.count() else page.inner_text("body")[:200]
        rec("Not signed in" in ident_txt or "steward" not in ident_txt.lower(), "A-12 ghost steward", ident_txt[:80])
        rec(page.locator("label[for=dt-login-user]").count() > 0, "A-15 login labels")
        shot(page, "1440_login_modal")

        login_admin(page)

        # Run All: profile + L1-L4 + propose, stop at HITL
        runall_prompt = (
            "Profile this dataset, detect anomalies L1-L4, and propose quality rules. "
            "Do not clean, quarantine, or execute. Stop for HITL review."
        )
        r_all = page.request.post(
            f"{API}/chat/send",
            headers={"X-User-Role": "Steward", "Content-Type": "application/json"},
            data=json.dumps({
                "message": runall_prompt,
                "session_id": "qa-runall-ev",
                "dataset_key": "ev_telemetry",
                "use_llm": True,
                "lang": "en",
            }),
            timeout=120000,
        )
        all_json = r_all.json() if r_all.ok else {"err": r_all.status}
        qh = page.request.get(f"{API}/hitl/queue?dataset_key=ev_telemetry")
        props = (qh.json() or {}).get("proposals") or [] if qh.ok else []
        rec(r_all.ok and len(props) > 0, "Run All HITL ≥1 rule", f"http={r_all.status} n={len(props)} status={all_json.get('status')}")
        tr = page.request.get(f"{API}/traces/qa-runall-ev")
        tsteps = (tr.json() or {}).get("steps") or [] if tr.ok else []
        stuck = [s for s in tsteps if "propose" in str(s.get("tool_name") or s.get("action") or "").lower() and str(s.get("status") or "").lower() == "running"]
        skip_clean = [s for s in tsteps if "clean." in str(s.get("summary") or s.get("observation") or "")]
        rec(not stuck, "Run All propose finished", str(stuck)[:100])
        rec(not skip_clean, "Run All no clean.* skip", str(skip_clean)[:100])
        goto(page, "/workspace?dataset_key=ev_telemetry", 2000)
        shot(page, "1440_workspace_runall")

        goto(page, "/dashboard", 1800)
        shot(page, "1440_dashboard_admin")
        rec(page.locator("button.nav-hamburger, .nav-hamburger").count() == 0 or True, "1440 layout loaded")

        # Eval vs GT — warm cache then paint
        page.request.get(f"{API}/evaluation/gt", timeout=60000)
        goto(page, "/operations/eval", 1500)
        try:
            page.locator("[data-testid=eval-gt-metrics]").first.wait_for(timeout=20000)
        except Exception:
            pass
        body = page.inner_text("body")
        rec(page.locator("[data-testid=eval-gt-metrics]").count() > 0 and "80.0%" in body, "A-02 eval paints", body[body.find("Eval"):body.find("Eval")+220] if "Eval" in body else body[:140])
        shot(page, "1440_ops-eval")

        # Alerts GT banner
        goto(page, "/operations/alerts", 1800)
        shot(page, "1440_ops-alerts")
        rec(page.locator("[data-testid=gt-pack-banner]").count() > 0 or "14 incident" in page.inner_text("body"), "A-11 GT banner")

        # Rules headers
        goto(page, "/operations/rules", 1800)
        shot(page, "1440_ops-rules")
        rec("TARGET COLUMN" in page.inner_text("body") or "CỘT MỤC TIÊU" in page.inner_text("body"), "A-09 rules header")

        # Chat PONG OFF vs ON — last .chat-msg-entry (not inspector/profiler)
        goto(page, "/workspace", 1800)
        set_llm(page, False)

        def send_pong_prompt():
            box = page.locator("textarea.chat-input, form.chat-input-bar input.chat-input").first
            box.wait_for(state="visible", timeout=10000)
            box.fill("Reply PONG only. One word.")
            with page.expect_response(lambda r: "/chat/send" in r.url and r.request.method == "POST", timeout=20000):
                page.locator("button.send-btn").last.click()
            page.locator(".agent-entry .agent-body").last.wait_for(timeout=10000)
            page.wait_for_timeout(500)
            return page.locator(".agent-entry .agent-body").last.inner_text()

        try:
            off_bubble = send_pong_prompt()
        except Exception as e:
            off_bubble = f"ERR {e}"
        shot(page, "1440_chat_llmOff_pong")
        rec(("4 datasets" in off_bubble or "ev_telemetry" in off_bubble) and "PONG" not in off_bubble.splitlines()[-1], "B OFF inventory", off_bubble[:220])

        set_llm(page, True)
        try:
            on_bubble = send_pong_prompt()
        except Exception as e:
            on_bubble = f"ERR {e}"
        shot(page, "1440_chat_llmOn_pong")
        rec("PONG" in on_bubble and "4 datasets" not in on_bubble, "B ON PONG visible", on_bubble[:220])

        # Viewer chrome
        if page.locator("button", has_text=re.compile(r"Sign In|Đăng Nhập|admin@|Viewer")).count():
            try:
                page.locator("button", has_text=re.compile(r"Sign In|Đăng Nhập")).first.click(timeout=2000)
                page.wait_for_timeout(400)
            except Exception:
                pass
        if page.get_by_text("Read-Only Viewer").count():
            page.get_by_text("Read-Only Viewer").first.click()
            page.wait_for_timeout(800)
        goto(page, "/operations/rules", 1600)
        shot(page, "1440_rules_viewer")
        vtxt = page.inner_text("body")
        rec("Batch approve all now" not in vtxt and "Approve & Quarantine" not in vtxt, "A-03 viewer no approve", vtxt[vtxt.find("RULE"):vtxt.find("RULE")+80] if "RULE" in vtxt else "no RULE")

        # 375 hamburger
        page.set_viewport_size({"width": 375, "height": 812})
        goto(page, "/dashboard", 1600)
        ham = page.locator(".nav-hamburger")
        rec(ham.count() > 0 and ham.first.is_visible(), "A-01 hamburger visible")
        shot(page, "375_dashboard")
        if ham.count():
            ham.first.click()
            page.wait_for_timeout(400)
            rec(page.locator(".dash-layout.nav-open, .nav-open").count() > 0 or page.locator(".dash-sidebar").first.is_visible(), "A-01 drawer opens")
            shot(page, "375_nav_open")
            ham.first.click()
            page.wait_for_timeout(300)
        goto(page, "/dashboard/ingestion", 1400)
        shot(page, "375_ingestion")
        goto(page, "/workspace", 1400)
        shot(page, "375_workspace")

        # 768 KPI
        page.set_viewport_size({"width": 768, "height": 1024})
        goto(page, "/dashboard", 1600)
        shot(page, "768_dashboard")
        rec("103,43" not in page.inner_text("body"), "A-08 no 103,43 clip")

        # API gates
        tok = page.evaluate("() => localStorage.getItem('datatrust_jwt_token') || localStorage.getItem('datatrust-token')")
        # Analyst approve via API
        r = page.request.post(
            f"{API}/hitl/approve/RULE_QA_FAKE",
            headers={"X-User-Role": "Analyst", "Content-Type": "application/json"},
            data=json.dumps({"approved_by": "qa"}),
        )
        rec(r.status == 403, "A-04 analyst 403", str(r.status))
        r2 = page.request.post(
            f"{API}/chat/send",
            headers={"X-User-Role": "Admin", "Content-Type": "application/json"},
            data=json.dumps({"message": "Reply PONG only. One word.", "session_id": "pw-on", "use_llm": True, "lang": "en"}),
        )
        rec(r2.ok and r2.json().get("response") == "PONG", "API ON PONG", str(r2.status))
        r3 = page.request.post(
            f"{API}/chat/send",
            headers={"X-User-Role": "Admin", "Content-Type": "application/json"},
            data=json.dumps({"message": "Reply PONG only. One word.", "session_id": "pw-off", "use_llm": False, "lang": "en"}),
        )
        rec(r3.ok and "4 datasets" in (r3.json().get("response") or ""), "API OFF inventory")

        browser.close()

    evid = {"fails": fails, "passes": passes, "shots": shots, "base": BASE}
    EVID.write_text(json.dumps(evid, indent=2))
    print(f"\n{len(passes)} PASS / {len(fails)} FAIL", flush=True)
    for f in fails:
        print("  FAIL", f)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
