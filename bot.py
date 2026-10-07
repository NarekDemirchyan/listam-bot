# -*- coding: utf-8 -*-
import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup

TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

STATE    = "state.json"
INTERVAL = 40 * 60        # 40 րոպե հրապարակումների միջեւ
TEST     = True           # փորձարկման ռեժիմ, վերջում կդարձնենք False

SECTIONS = {"4": "Электроника", "133": "Дом и сад",
            "27": "Детский мир", "16": "Транспорт"}

BASE = "https://www.list.am"
HDRS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

def meta(soup, prop):
    tag = soup.find("meta", attrs={"property": prop})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return ""

def get_ids(sess):
    ids = []
    for cat in SECTIONS:
        try:
            html = sess.get(f"{BASE}/ru/category/{cat}",
                            headers=HDRS, timeout=30).text
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.select("a[href*='/item/']"):
                m = re.search(r"/item/(\d+)", a.get("href", ""))
                if m and m.group(1) not in ids:
                    ids.append(m.group(1))
            print(f"[{cat}] {SECTIONS[cat]}: всего {len(ids)}")
        except Exception as e:
            print(f"[{cat}] ошибка: {e}")
    return ids

def item_data(sess, iid):
    url = f"{BASE}/ru/item/{iid}"
    html = sess.get(url, headers=HDRS, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    title = meta(soup, "og:title")
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""

    photo = meta(soup, "og:image")

    desc = meta(soup, "og:description")
    if not desc:
        m = re.search(r"Описание\n(.+?)(?:\nПереведено|\nTranslated|\Z)",
                      text, re.S)
        if m:
            desc = m.group(1).strip()

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
    ids = get_ids(sess)
    print("всего ссылок:", len(ids), ids[:5])

    if TEST:
        if ids:
            d = item_data(sess, ids[0])
            print("TEST данные:", json.dumps(d, ensure_ascii=False)[:700])
            send(sess, d, ids[0])
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
            d = item_data(sess, iid)
            if send(sess, d, iid):
                st["last_publish"] = now
            else:
                st["queue"].insert(0, iid)
        except Exception as e:
            print("ошибка публикации:", e)
            st["queue"].insert(0, iid)

    save(st)

main()
