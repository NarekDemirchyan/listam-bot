# -*- coding: utf-8 -*-
"""Էջերի բերում և markdown/HTML փոխարկում։
Զննարկիչ (Playwright) → եթե պատը փակում է, պահուստ r.jina.ai։

jina() -> markdown կամ "" ձախողման դեպքում։
extra={"x-respond-with": "html"} -> չմշակված HTML։

PROXY_URL  - պրոքսի (ըստ ցանկության)։
JINA_KEY   - r.jina.ai բանալի (ըստ ցանկության, անվճար)։
"""

import os
import shutil
import subprocess
import time

from markdownify import markdownify

BLOCKED = ("just a moment", "attention required", "checking your browser",
           "cf-browser-verification", "cf_chl",
           "performing security verification")

STEALTH = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU','ru','hy','en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
"""

JINA = "https://r.jina.ai/"
_pw = None
_browser = None
_ctx = None
_xvfb_tried = False

def _proxies():
    p = os.environ.get("PROXY_URL", "").strip()
    if not p:
        return None
    return {"http": p, "https": p}

def _display():
    global _xvfb_tried
    if os.environ.get("DISPLAY"):
        return os.environ["DISPLAY"]
    if _xvfb_tried:
        return ""
    _xvfb_tried = True
    if shutil.which("Xvfb") is None:
        print("  Xvfb չկա, աշխատում է headless")
        return ""
    try:
        subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1366x900x24"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.environ["DISPLAY"] = ":99"
        time.sleep(1.5)
        print("  Xvfb միացավ, աշխատում է headed")
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
        proxy = None
        p = os.environ.get("PROXY_URL", "").strip()
        if p:
            from urllib.parse import urlparse
            u = urlparse(p)
            proxy = {"server": "{}://{}:{}".format(u.scheme, u.hostname, u.port)}
            if u.username:
                proxy["username"] = u.username
            if u.password:
                proxy["password"] = u.password
        display = _display()
        kw = {"headless": not bool(display), "args": args}
        if proxy:
            kw["proxy"] = proxy
        try:
            _browser = _pw.chromium.launch(**kw)
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

def _wait_ready(page, wait_seconds=45):
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

def _browser_get(url, want_html):
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
            print("  browser защита/пусто | title:", title[:80], "| len:", len(html))
            _drop_context()
            return ""
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
        return ""

def _jina_get(url, want_html):
    try:
        import requests
    except Exception:
        return ""
    headers = {}
    if want_html:
        headers["x-respond-with"] = "html"
    key = os.environ.get("JINA_KEY", "").strip()
    if key:
        headers["Authorization"] = "Bearer " + key
    try:
        r = requests.get(JINA + url, headers=headers, timeout=90,
                         proxies=_proxies())
        text = r.text or ""
        if r.status_code != 200:
            print("  jina статус:", r.status_code)
            return ""
    except Exception as e:
        print("  jina ошибка:", type(e).__name__, str(e)[:120])
        return ""
    low = text.lower()
    if len(text) < 1500 or any(m in low for m in BLOCKED):
        print("  jina защита/пусто | len:", len(text))
        return ""
    if want_html:
        return text
    lines = text.splitlines()
    title = ""
    start = 0
    for i, ln in enumerate(lines[:12]):
        if ln.strip().lower().startswith("title:"):
            title = ln.split(":", 1)[1].strip()
            start = i + 1
            break
    body = "\n".join(lines[start:]).lstrip("\n")
    if len(body) < 1000:
        return ""
    return "# " + title + "\n\n" + body

def jina(sess, url, extra=None):
    want_html = bool(extra and extra.get("x-respond-with") == "html")
    text = _browser_get(url, want_html)
    if text:
        return text
    text = _jina_get(url, want_html)
    if text:
        print("  բերված է պահուստով (jina):", url[:70])
        return text
    time.sleep(3)
    return ""
