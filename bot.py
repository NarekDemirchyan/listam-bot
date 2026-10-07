# -*- coding: utf-8 -*-
import os
import re
import json
import time
import requests

TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

STATE    = "state.json"
INTERVAL = 40 * 60
TEST     = True

JINA = "https://r.jina.ai/"
BASE = "https://www.list.am"
HDRS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "text/plain",
}

SECTIONS = {"4": "Электроника", "133": "Дом и сад",
            "27": "Детский мир", "16": "Транспорт"}

def jina(sess, url):
    r = sess.get(JINA + url, headers=HDRS, timeout=90)
    if r.status_code != 200:
        print("  jina:", r.status_code, r.text[:200])
    return r.text

def get_ids(sess):
    ids = []
    for cat in SECTIONS:
        md = jina(sess, f"{BASE}/ru/category/{cat}")
        found = re.findall(r"/ru/item/(\d+)", md)
        uniq = []
        for i in found:
            if i not in uniq:
                uniq.append(i)
        print(f"[{cat}] {SECTIONS[cat]}: {len(uniq)} объявлений")
        for i in uniq:
            if i not in ids:
                ids.append(i)
        time.sleep(2)
    return ids

def item_data(sess, iid):
    md = jina(sess, f"{BASE}/ru/item/{iid}")
    cut = md.find("Похожие объявления")
    if cut > 0:
        md = md[:cut]

    title = ""
    m = re.search(r"^#\s+(.+)$", md, re.M)
    if m:
        title = m.group(1).strip()

    price = ""
    m = re.search(r"([\d][\d\s,]*)\s*֏", md)
    if m:
        price = m.group(1).strip() + " ֏"

    photo = ""
    m = re.search(r"\((https://img\.list\.am/[fgr]/[^)\s]+\.(?:webp|jpg|jpeg|png))\)", md)
    if m:
        photo = m.group(1)

    desc = ""
    m = re.search(r"Описание\s*\n+(.+?)\n\s*Номер объявления", md, re.S)
    if m:
        desc = " ".join(m.group(1).split())

    place = ""
    m = re.search(r"\[([^\]]*›[^\]]*)\]", md)
    if m:
        place = m.group(1).strip()

    return {"title": title, "price": price, "photo": photo,
            "desc": desc, "place": place}

def send(sess, d, iid):
    lines = [d["title"]]
    if d["price"]:
        lines.append(d["price"])
    if d["place"]:
        lines.append(d["place"])
    if d["desc"]:
        lines.append(d["desc"][:600])
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
            print("TEST данные:", json.dumps(d, ensure_ascii=False)[:800])
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
