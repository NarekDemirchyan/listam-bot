# -*- coding: utf-8 -*-
import os
import re
import json
import time
import requests

TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

STATE    = "state.json"
INTERVAL = 30 * 60
TEST     = False

JINA = "https://r.jina.ai/"
BASE = "https://www.list.am"
HDRS = {"User-Agent": "curl/8.5.0"}

SECTIONS = {"4": "Электроника", "133": "Дом и сад",
            "27": "Детский мир"}

PHOTO_RE = re.compile(
    r"https://img\.list\.am/(f|n|g|r)/\d+/(\d+)\.(?:webp|jpg|jpeg|png)")

def jina(sess, url, extra=None):
    h = dict(HDRS)
    if extra:
        h.update(extra)
    for attempt in range(5):
        try:
            r = sess.get(JINA + url, headers=h, timeout=90)
            if r.status_code == 200 and r.text.strip():
                return r.text
            print(f"  jina {r.status_code}, попытка {attempt + 1}")
        except Exception as e:
            print(f"  jina ошибка: {type(e).__name__}: {e}")
        time.sleep(10)
    return ""

def collect_photos(text):
    """Уникальные фото; при наличии берём полный размер (f)."""
    out = {}
    for m in PHOTO_RE.finditer(text):
        kind, pid, url = m.group(1), m.group(2), m.group(0)
        if pid not in out or kind == "f":
            out[pid] = url
    return list(out.values())[:10]

def translate(sess, text):
    text = (text or "").strip()
    if not text:
        return text
    try:
        r = sess.get("https://translate.googleapis.com/translate_a/single",
                     params={"client": "gtx", "sl": "auto", "tl": "ru",
                             "dt": "t", "q": text[:2000]}, timeout=30)
        data = r.json()
        res = "".join(p[0] for p in data[0] if p and p[0]).strip()
        if res:
            return res
    except Exception as e:
        print("  перевод недоступен:", type(e).__name__)
    return text

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
        time.sleep(15)
    return ids

def item_data(sess, iid):
    md = jina(sess, f"{BASE}/ru/item/{iid}")
    cut = md.find("Похожие объявления")
    if cut > 0:
        md = md[:cut]

    html = jina(sess, f"{BASE}/ru/item/{iid}", {"x-respond-with": "html"})
    cut2 = html.find("Похожие")
    if cut2 > 0:
        html = html[:cut2]

    title = ""
    m = re.search(r"^#\s+(.+)$", md, re.M)
    if m:
        title = m.group(1).strip()

    price = ""
    m = re.search(r"([\d][\d\s,]*)\s*֏", md)
    if m:
        price = m.group(1).strip() + " ֏"

    desc = ""
    m = re.search(r"Описание\s*\n+(.+?)\n\s*Номер объявления", md, re.S)
    if m:
        desc = " ".join(m.group(1).split())

    place = ""
    m = re.search(r"\[([^\]]*›[^\]]*)\]", md)
    if m:
        place = m.group(1).strip()

    photos = collect_photos(md + "\n" + html)

    return {"title": title, "price": price, "desc": desc,
            "place": place, "photos": photos}

def make_caption(sess, d):
    lines = [translate(sess, d["title"])]
    if d["price"]:
        lines.append(d["price"])
    if d["place"]:
        lines.append(d["place"])
    if d["desc"]:
        lines.append(translate(sess, d["desc"][:700]))
    return "\n\n".join(x for x in lines if x)[:1024]

def send(sess, d, iid, caption):
    url = f"{BASE}/ru/item/{iid}"
    markup = {"inline_keyboard": [[{"text": "Связаться", "url": url}]]}
    photos = d["photos"]

    if len(photos) >= 2:
        media = [{"type": "photo", "media": photos[0], "caption": caption}]
        for p in photos[1:10]:
            media.append({"type": "photo", "media": p})
        r = sess.post(f"https://api.telegram.org/bot{TOKEN}/sendMediaGroup",
                      data={"chat_id": CHAT_ID,
                            "media": json.dumps(media, ensure_ascii=False)},
                      timeout=60)
        print("telegram album:", r.status_code, r.text[:200])
        r2 = sess.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                       data={"chat_id": CHAT_ID,
                             "text": "Связаться с продавцом",
                             "reply_markup": json.dumps(markup)}, timeout=40)
        print("telegram кнопка:", r2.status_code, r2.text[:200])
        return r.ok and r2.ok

    payload = {"chat_id": CHAT_ID, "reply_markup": json.dumps(markup)}
    if photos:
        payload["photo"] = photos[0]
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
            print("фото найдено:", len(d["photos"]))
            print("TEST данные:", json.dumps(
                {k: v for k, v in d.items()}, ensure_ascii=False)[:800])
            send(sess, d, ids[0], make_caption(sess, d))
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
            if d["title"] and send(sess, d, iid, make_caption(sess, d)):
                st["last_publish"] = now
            else:
                st["queue"].insert(0, iid)
        except Exception as e:
            print("ошибка публикации:", e)
            st["queue"].insert(0, iid)

    save(st)

main()
