# -*- coding: utf-8 -*-
import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

STATE    = "state.json"
INTERVAL = 40 * 60
TEST     = True

SECTIONS = {"4": "Электроника", "133": "Дом и сад",
            "27": "Детский мир", "16": "Транспорт"}

BASE = "https://www.list.am"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36")

ARGS = ["--disable-blink-features=AutomationControlled", "--no-sandbox"]

def open_page(page, url, tries=45):
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        print("  goto ошибка:", e)
    for i in range(tries):
        try:
            title = page.title()
            html = page.content()
        except Exception:
            title, html = "", ""
        if "item/" in html and "Just a moment" not in title:
            print(f"  ok за {i} c, title={title[:60]}")
            return html
        page.wait_for_timeout(1000)
    print("  не дождались:", page.title()[:60])
    return page.content()

def get_ids(page):
    ids = []
    for cat in SECTIONS:
        html = open_page(page, f"{BASE}/ru/category/{cat}")
        soup = BeautifulSoup(html, "html.parser")
        links = soup.select("a[href*='/item/']")
        print(f"[{cat}] {SECTIONS[cat]}: item-ссылок={len(links)}")
        for a in links:
            m = re.search(r"/item/(\d+)", a.get("href", ""))
            if m and m.group(1) not in ids:
                ids.append(m.group(1))
    return ids

def meta(soup, prop):
    tag = soup.find("meta", attrs={"property": prop})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return ""

def item_data(page, iid):
    html = open_page(page, f"{BASE}/ru/item/{iid}")
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    title = meta(soup, "og:title")
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""

    photo = meta(soup, "og:image")
    desc = meta(soup, "og:description")

    price = ""
    m = re.search(r"([\d][\d\s.,]*)\s*(֏|\$|₽)", text)
    if m:
        price = f"{m.group(1).strip()} {m.group(2)}"

    return {"title": title, "photo": photo, "price": price, "desc": desc}

def send(sess, d, iid):
    lines = [d["title"]]
    if d["price"]:
        lines.append(d["price"])
    if d["desc"]:
        lines.append(d["desc"])
    caption = "\n\n".join(x for x in lines if x)[:1024]

    markup = {"inline_keyboard": [[{
        "text": "Связаться",
        "url": f"{BASE}/ru/item/{iid}"}]]}

    payload = {"chat_id": CHAT_ID, "reply_markup": json.dumps(markup)}
    if d["photo"]:
        payload["photo"] = d["photo"]
        payload["caption"] = caption
        method = "sendPhoto"
    else:
        payload["text"] = caption
        method = "sendMessage"

    r = sess.post(f"https://api.telegram.org/bot{TOKEN}/{method}",
                  data=payload, timeout=40)
    print("telegram:", r.status_code, r.text[:300])
    return r.ok

def load():
    if os.path.exists(STATE):
        return json.load(open(STATE, encoding="utf-8"))
    return {"seen": [], "queue": [], "last_publish": 0}

def save(st):
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)

def main():
    st = load()
    sess = requests.Session()

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=True, args=ARGS)
        except Exception as e:
            print("chrome не запустился:", e)
            browser = p.chromium.launch(headless=True, args=ARGS)

        ctx = browser.new_context(user_agent=UA, locale="ru-RU",
                                  viewport={"width": 1366, "height": 900})
        page = ctx.new_page()

        ids = get_ids(page)
        print("всего ссылок:", len(ids), ids[:5])

        if TEST:
            if ids:
                d = item_data(page, ids[0])
                print("TEST данные:", json.dumps(d, ensure_ascii=False)[:700])
                send(sess, d, ids[0])
            browser.close()
            return

        first = not st["seen"]
        for iid in ids:
            if first:
                st["seen"].append(iid)
                continue
            if iid not in st["seen"]:
                st["seen"].append(iid)
                st["queue"].append(iid)

        st["seen"] = st["seen"][-5000:]
        now = time.time()
        print("очередь:", len(st["queue"]))

        if st["queue"] and now - st["last_publish"] >= INTERVAL:
            iid = st["queue"].pop(0)
            try:
                d = item_data(page, iid)
                if send(sess, d, iid):
                    st["last_publish"] = now
                else:
                    st["queue"].insert(0, iid)
            except Exception as e:
                print("ошибка публикации:", e)
                st["queue"].insert(0, iid)

        browser.close()

    save(st)

main()
