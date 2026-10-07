# -*- coding: utf-8 -*-
import re
import requests

UA_BROWSER = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0.0.0 Safari/537.36")

TARGET = "https://www.list.am/ru/category/4"

TESTS = [
    ("jina / браузерный UA", "https://r.jina.ai/" + TARGET,
     {"User-Agent": UA_BROWSER, "Accept": "text/plain"}),
    ("jina / без UA", "https://r.jina.ai/" + TARGET, {}),
    ("jina / curl UA", "https://r.jina.ai/" + TARGET,
     {"User-Agent": "curl/8.5.0"}),
    ("codetabs", "https://api.codetabs.com/v1/proxy?quest=" + TARGET,
     {"User-Agent": UA_BROWSER}),
    ("allorigins", "https://api.allorigins.win/raw?url=" + TARGET,
     {"User-Agent": UA_BROWSER}),
    ("corsproxy", "https://corsproxy.io/?url=" + TARGET,
     {"User-Agent": UA_BROWSER}),
    ("прямой запрос", TARGET, {"User-Agent": UA_BROWSER}),
    ("listam + Googlebot", TARGET,
     {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; "
                    "+http://www.google.com/bot.html)"}),
]

for name, url, hdr in TESTS:
    try:
        r = requests.get(url, headers=hdr, timeout=45)
        t = re.search(r"<title>(.*?)</title>", r.text, re.S)
        title = " ".join(t.group(1).split())[:60] if t else ""
        items = len(set(re.findall(r"/ru/item/(\d+)", r.text)))
        print(f"{name}: status={r.status_code} len={len(r.text)} "
              f"items={items} title={title}")
    except Exception as e:
        print(f"{name}: ошибка {type(e).__name__}: {e}")
