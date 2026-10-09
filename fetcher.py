# -*- coding: utf-8 -*-
"""Ընթերցիչ առանց Jina-ի. էջը բացում է իսկական Chrome-ով (Playwright) ու վերադարձնում
markdown, կամ ուղիղ HTML, եթե extra-ում x-respond-with=html է։ Ստորագրությունը նույնն է,
ինչ հին jina()-ը, դրա համար բոտի մնացած կոդը մնում է անփոփոխ։"""
from markdownify import markdownify

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_pw = None
_browser = None

def _start():
    global _pw, _browser
    if _browser is None:
        from playwright.sync_api import sync_playwright
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
    return _browser

def jina(sess, url, extra=None):
    want_html = bool(extra and extra.get("x-respond-with") == "html")
    for attempt in range(2):
        ctx = None
        try:
            ctx = _start().new_context(user_agent=UA, locale="ru-RU",
                                       viewport={"width": 1366, "height": 900})
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            html = page.content()
            for _ in range(12):
                if "just a moment" not in html.lower() and len(html) > 3000:
                    break
                page.wait_for_timeout(2000)
                html = page.content()
            title = page.title()
            ctx.close()
            if len(html) < 3000:
                print("  browser пусто, попытка", attempt + 1)
                continue
            if want_html:
                return html
            md = markdownify(html, heading_style="ATX",
                             strip=["script", "style", "noscript", "svg"])
            return "# " + title.strip() + "\n\n" + md
        except Exception as e:
            print("  browser ошибка:", type(e).__name__, str(e)[:150])
            try:
                if ctx:
                    ctx.close()
            except Exception:
                pass
    return ""
