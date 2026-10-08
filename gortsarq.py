# -*- coding: utf-8 -*-
import os
import re
import json
import time
import requests

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

STATE = "state-gortsarq.json"
INTERVAL = 35 * 60
SEED = 120
TEST = False

JINA = "https://r.jina.ai/"
BASE = "https://gortsarq.am"
HDRS = {"User-Agent": "curl/8.5.0"}

CATS = [
    "265c-2-ansharj-guyq",          # Անշարժ գույք
    "1796c-pahestamaser",           # Պահեստամասեր
    "1875c-kendaniner",             # Կենդանիներ
    "1904c-elektronika-hy",         # Էլեկտրոնիկա
    "2063c-tun-ev-aygi",            # Տուն և այգի
    "2116c-noradzevutyun-ev-och",   # Նորաձևություն և ոճ
    "2295c-mankakan-ashxarh",       # Մանկական աշխարհ
    "2328c-hobbi-hangist-ev-sport", # Հոբբի, հանգիստ և սպորտ
]

ITEM_RE = re.compile(r"""https://gortsarq\.am/ru/(\d+)p-[^)"'\s>]+""")
PHOTO_RE = re.compile(r"""https://gortsarq\.am/images/detailed/\d+/[^)"'\s>]+""")

BLOCKED = ("just a moment", "attention required", "enable javascript",
           "checking your browser", "cloudflare")

def is_blocked(text):
    t = (text or "").strip()
    return len(t) < 800 or any(m in t.lower() for m in BLOCKED)

def jina(sess, url):
    for attempt in range(4):
        try:
            r = sess.get(JINA + url, headers=HDRS, timeout=60)
            if r.status_code == 200 and not is_blocked(r.text):
                return r.text
            print(f" jina {r.status_code} / защита, попытка {attempt + 1}")
        except Exception as e:
            print(f" jina ошибка: {type(e).__name__}: {e}")
        time.sleep(8 * (attempt + 1))
    return ""

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
        print(" перевод недоступен:", type(e).__name__)
    return text

def has_cyr(s):
    return bool(re.search(r"[А-Яа-яЁё]", s or ""))

def latin_junk(t):
    t = (t or "").strip()
    if not t or has_cyr(t):
        return False
    return len(t.split()) > 2

def get_items(sess):
    found = {}
    for cat in CATS:
        md = jina(sess, f"{BASE}/ru/{cat}/")
        n = 0
        for m in ITEM_RE.finditer(md):
            iid = m.group(1)
            path = m.group(0)[len("https://gortsarq.am"):]
            if iid not in found:
                found[iid] = path
                n += 1
        print(f"[{cat}] ссылок: {n}")
        time.sleep(3)
    return found

def item_data(sess, path):
    md = jina(sess, BASE + path)
    if not md:
        return None

    title = ""
    m = re.search(r"^#\s+(.+)$", md, re.M)
    if m:
        title = m.group(1).strip()

    price = ""
    m = re.search(r"([\d][\d\s,\.]*)\s*(֏|\$|€)", md)
    if m:
        price = re.sub(r"[.,]00$", "", m.group(1).strip()) + " " + m.group(2)

    desc = ""
    m = re.search(r"Описание\s*\n+(.+?)\n+\d{2}\.\d{2}\.\d{4}", md, re.S)
    if m:
        desc = " ".join(m.group(1).split())

    place = ""
    m = re.search(r"Расположение\s*\n+(.+)", md)
    if m:
        place = m.group(1).strip()[:60]

    photos = []
    for m in PHOTO_RE.finditer(md):
        if m.group(0) not in photos:
            photos.append(m.group(0))

    return {"title": title, "price": price, "desc": desc,
            "place": place, "photos": photos[:10], "url": BASE + path}

def headline(sess, d):
    t = translate(sess, d["title"]).strip()
    if t and not latin_junk(t):
        return t
    alt = translate(sess, d["desc"][:300]).strip()
    if has_cyr(alt):
        return re.split(r"[.!?]\s", alt)[0].strip()[:90]
    return ""

def make_caption(sess, d):
    head = headline(sess, d)
    if not head:
        return ""
    lines = [head]
    if d["price"]:
        lines.append(d["price"])
    if d["place"]:
        lines.append(d["place"])
    if d["desc"]:
        lines.append(translate(sess, d["desc"][:700]))
    lines.append("Связаться: " + d["url"])
    return "\n\n".join(x for x in lines if x)[:1024]

def send(sess, d, caption):
    markup = {"inline_keyboard": [[{"text": "Связаться", "url": d["url"]}]]}
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

        if not r.ok:
            payload = {"chat_id": CHAT_ID, "photo": photos[0],
                       "caption": caption, "reply_markup": json.dumps(markup)}
            r1 = sess.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                           data=payload, timeout=40)
            print("telegram fallback:", r1.status_code, r1.text[:200])
            return r1.ok

        mid = None
        try:
            res = r.json().get("result") or []
            if res:
                mid = res[0]["message_id"]
        except Exception:
            mid = None

        payload = {"chat_id": CHAT_ID, "text": "Связаться с продавцом",
                   "reply_markup": json.dumps(markup)}
        if mid:
            payload["reply_parameters"] = json.dumps({"message_id": mid})
        r2 = sess.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                       data=payload, timeout=40)
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
    print("telegram:", r.status_code, r.text[:200])
    return r.ok

def load():
    if os.path.exists(STATE):
        return json.load(open(STATE, encoding="utf-8"))
    return {"seen": [], "queue": [], "last_publish": 0, "first_done": False}

def save(st):
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)

def main():
    st = load()
    st.setdefault("failed", {})
    sess = requests.Session()

    items = get_items(sess)
    print("всего найдено:", len(items))

    if TEST:
        for iid, path in list(items.items())[:1]:
            d = item_data(sess, path)
            print("фото:", len(d["photos"]), "заголовок:", d["title"])
            send(sess, d, make_caption(sess, d))
        return

    fresh = [(i, p) for i, p in items.items() if i not in st["seen"]]

    if not st["first_done"]:
        take = fresh[:SEED]
        for iid, path in take:
            st["seen"].append(iid)
            st["queue"].append(path)
        for iid, _ in fresh:
            if iid not in st["seen"]:
                st["seen"].append(iid)
        st["first_done"] = True
        print(f"первый запуск: в очередь {len(take)}")
    else:
        for iid, path in fresh:
            st["seen"].append(iid)
            st["queue"].append(path)
            print(f"новое: {iid}")

    st["seen"] = st["seen"][-5000:]
    now = time.time()
    print("очередь:", len(st["queue"]))

    if st["queue"] and now - st["last_publish"] >= INTERVAL:
        path = st["queue"].pop(0)
        ok = False
        try:
            d = item_data(sess, path)
            cap = make_caption(sess, d) if d else ""
            ok = bool(cap) and send(sess, d, cap)
        except Exception as e:
            print("ошибка публикации:", e)

        if ok:
            st["last_publish"] = now
        else:
            st["failed"][path] = st["failed"].get(path, 0) + 1
            if st["failed"][path] < 2:
                st["queue"].append(path)
                print(" вернём в конец очереди")
            else:
                print(" брошен: не удалось 2 раза")

    save(st)

main()
