# -*- coding: utf-8 -*-
"""Էջերի բերում և markdown/HTML փոխարկում (Playwright, Cloudflare-ի դեմ)։
jina() -> markdown տեքստ կամ "" ձախողման դեպքում։
extra={"x-respond-with": "html"} -> չմշակված HTML։"""

import os
import shutil
import subprocess
import time

from markdownify import markdownify

BLOCKED = ("just a moment", "attention required", "checking your browser",
           "cf-browser-verification", "cf_chl", "enable javascript",
           "performing security verification")

STEALTH = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU','ru','hy','en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
"""

_pw = None
_browser = None
_ctx = None
_xvfb_tried = False

def _display():
    global _xvfb_tried
    if os.environ.get("DISPLAY"):
        return os.environ["DISPLAY"]
    if _xvfb_tried:
        return ""
    _xvfb_tried = True
    if shutil.which("Xvfb") is None:
        return ""
    try:
        subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1366x900x24"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.environ["DISPLAY"] = ":99"
        time.sleep(1.5)
        return ":99"
    except Exception:
        return ""

def _start():
    global _pw, _browser
    if _browser is None:
        from playwright.sync_api import sync_playwright
        _pw = sync_playwright().start()
        args = ["--disable-blink-features=AutomationControlled",
                "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        display = _display()
        try:
            _browser = _pw.chromium.launch(headless=not bool(display), args=args)
        except Exception:
            _browser = _pw.chromium.launch(headless=True, args=args)
    return _browser

def _context():
    global _ctx
    if _ctx is None:
        _ctx = _start().new_context(locale="ru-RU", timezone_id="Asia/Yerevan",
                                    viewport={"width": 1366, "height": 900})
        _ctx.add_init_script(STEALTH)
        page = _ctx.new_page()
        try:
            page.goto("https://www.list.am/ru/", wait_until="domcontentloaded",
                      timeout=60000)
            page.wait_for_timeout(2500)
        except Exception:
            pass
        page.close()
    return _ctx

def _drop_context():
    global _ctx
    try:
        if _ctx:
            _ctx.close()
    except Exception:
        pass
    _ctx = None

def _title(page):
    try:
        t = page.locator("h1")
        if t.count():
            return " ".join(t.first.inner_text().split())
    except Exception:
        pass
    return " ".join(page.title().split())

def _wait_ready(page, wait_seconds=25):
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        try:
            html = page.content() or ""
        except Exception:
            html = ""
        if len(html) > 3000 and not any(m in html.lower() for m in BLOCKED):
            return html
        page.wait_for_timeout(2500)
    try:
        page.reload(wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)
        return page.content() or ""
    except Exception:
        return ""

def jina(sess, url, extra=None):
    want_html = bool(extra and extra.get("x-respond-with") == "html")
    for attempt in range(2):
        page = None
        try:
            page = _context().new_page()
            page.set_default_timeout(60000)
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            html = _wait_ready(page)
            for _ in range(3):
                page.mouse.wheel(0, 4000)
                page.wait_for_timeout(1000)
            html = page.content() or html
            title = _title(page)
            page.close()
            if len(html) < 3000 or any(m in html.lower() for m in BLOCKED):
                print("  browser защита/пусто, попытка", attempt + 1)
                _drop_context()
                time.sleep(5)
                continue
            if want_html:
                return html
            md = markdownify(html, heading_style="ATX",
                             strip=["script", "style", "noscript", "svg"])
            return "# " + title + "\n\n" + md
        except Exception as e:
            print("  browser ошибка:", type(e).__name__, str(e)[:150])
            try:
                if page:
                    page.close()
            except Exception:
                pass
            time.sleep(5)
    return ""
