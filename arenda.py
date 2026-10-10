# -*- coding: utf-8 -*-
# arenda.py — վարձույթի բոտ (@Marketplace_arm_bot → @arenda_armenia_arm)
import os
import re
import json
import time
import requests

from fetcher import jina

TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID_ARENDA", "")

STATE     = "state-arenda.json"
INTERVAL  = 15 * 60     # 15 րոպե հրապարակումների միջև
QUEUE_MAX = 250
TEST      = True        # True՝ մեկ ստուգող հրապարակում ու դադար

LIST_CATS   = ["56"]                                        # list.am՝ երկարաժամկետ վարձույթ
ESTATE_LIST = ["https://www.estate.am/ru/аренда-квартир-s4"]
MY_LIST     = ["https://myrealty.am/ru", "https://myrealty.am/ru?page=2"]

ORDER = ["list", "list", "list", "estate", "list", "list", "list", "myrealty"]

ITEM_RE   = re.compile(r"/ru/item/(\d+)")
ESTATE_RE = re.compile(r"https://www\.estate\.am/ru/[^\s\)\]\"']+-d(\d+)")
MY_RE     = re.compile(r"https://myrealty\.am/ru/snyat-kvartiru/[^\s\)\]\"']+/(\d+)")
PHOTO_RE  = re.compile(r"(?:https?:)?//[^\s\)\]\"']+\.(?:jpg|jpeg|png|webp)", re.I)
PRICE_RE  = re.compile(r"([\d][\d\s.,]{2,})\s*(֏|AMD|драм|\$|USD|€|EUR)", re.I)
TEL_RE    = re.compile(r"tel:([+\d][\d\s\-\(\)]{6,})")
BAD_IMG   = ("logo", "favicon", "icon", "sprite", "no-img", "avatar")

def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def has_cyr(s):
    return bool(re.search(r"[А-Яа-яЁё]", s or ""))

def latin_junk(t):
    t = (t or "").strip()
    if not t or has_cyr(t):
        return False
    return len(t.split()) > 2

def translate(sess, text):
    text = (text or "").strip()
    if not text:
        return text
    try:
        r = sess.get("https://translate.googleapis.com/translate_a/single",
                     params={"client": "gtx", "sl": "auto", "tl": "ru",
                             "dt": "t", "q": text[:2000]}, timeout=30)
        res = "".join(p[0] for p in r.json()[0] if p and p[0]).strip()
        if res:
            return res
    except Exception as e:
        print("  թարգմանությունը չկա՝", type(e).__name__)
    return text

def collect_photos(*texts):
    out = []
    for t in texts:
        for u in PHOTO_RE.findall(t or ""):
            if u.startswith("//"):
                u = "https:" + u
            if any(b in u.lower() for b in BAD_IMG):
                continue
            if u not in out:
                out.append(u)
    return out[:10]

def add(st, src, key, url):
    if key in st["seen"]:
        return 0
    st["seen"].append(key)
    st["queue"].append({"src": src, "key": key, "url": url})
    return 1

def collect(sess, st):
    for cat in LIST_CATS:
        md = jina(sess, "https://www.list.am/ru/category/" + cat) or ""
        ids = []
        for i in ITEM_RE.findall(md):
            if i not in ids:
                ids.append(i)
        n = sum(add(st, "list", "list:" + i,
                    "https://www.list.am/ru/item/" + i) for i in ids)
        print(f"list.am {cat}: գտնվեց {len(ids)}, նոր՝ {n}")
        time.sleep(8)

    for page in ESTATE_LIST:
        md = jina(sess, page) or ""
        items = {}
        for m in ESTATE_RE.finditer(md):
            items[m.group(1)] = m.group(0)
        n = sum(add(st, "estate", "estate:" + i, u) for i, u in items.items())
        print(f"estate.am: գտնվեց {len(items)}, նոր՝ {n}")
        time.sleep(8)

    for page in MY_LIST:
        md = jina(sess, page) or ""
        items = {}
        for m in MY_RE.finditer(md):
            items[m.group(1)] = m.group(0)
        n = sum(add(st, "myrealty", "my:" + i, u) for i, u in items.items())
        print(f"myrealty.am {page}: գտնվեց {len(items)}, նոր՝ {n}")
        time.sleep(8)

def item_data(sess, url):
    md = jina(sess, url) or ""
    for cut in ("Похожие объявления", "Похожие"):
        i = md.find(cut)
        if i > 0:
            md = md[:i]

    photo_list = collect_photos(md)
    html = ""
    if not photo_list:
        html = jina(sess, url, {"x-respond-with": "html"}) or ""
        photo_list = collect_photos(html)

    title = ""
    m = re.search(r"^#\s+(.+)$", md, re.M)
    if m:
        title = m.group(1).strip()

    price = ""
    m = PRICE_RE.search(md)
    if m:
        price = (m.group(1).strip() + " " + m.group(2)).strip()

    desc = ""
    m = re.search(r"Описание\s*\n+(.+?)\n\s*(?:Номер объявления|Похожие|Пожаловаться)", md, re.S)
    if m:
        desc = " ".join(m.group(1).split())

    place = ""
    m = re.search(r"\[([^\]]*›[^\]]*)\]", md)
    if m:
        place = m.group(1).strip()

    phone = ""
    m = TEL_RE.search(md + "\n" + html)
    if m:
        phone = " ".join(m.group(1).split())

    print(f"  {url}\n    md {len(md)}, նկար {len(photo_list)}, գին {price!r}, հեռ {bool(phone)}")
    return {"title": title, "price": price, "desc": desc, "place": place,
            "phone": phone, "photos": photo_list, "url": url}

def make_caption(sess, d):
    head = translate(sess, d["title"]).strip()
    if not head or latin_junk(head):
        alt = translate(sess, d["desc"][:300]).strip()
        head = re.split(r"[.!?]\s", alt)[0].strip()[:90] if alt else ""
    if not head:
        head = "Объявление об аренде"
    lines = ["<b>" + esc(head) + "</b>", "Аренда | Ереван и области"]
    if d["price"]:
        lines.append("<b>" + esc(d["price"]) + "</b>")
    if d["place"]:
        lines.append(esc(d["place"]))
    if d["desc"]:
        lines.append(esc(translate(sess, d["desc"][:600])))
    if d["phone"]:
        lines.append("Телефон: <code>" + esc(d["phone"]) + "</code>")
    return "\n\n".join(x for x in lines if x)[:1024]

def send(sess, d, caption):
    markup = {"inline_keyboard": [[{"text": "Связаться", "url": d["url"]}]]}
    photo_list = d["photos"]

    if len(photo_list) >= 2:
        media = [{"type": "photo", "media": photo_list[0], "caption": caption,
                  "parse_mode": "HTML"}]
        for p in photo_list[1:10]:
            media.append({"type": "photo", "media": p})
        r = sess.post(f"https://api.telegram.org/bot{TOKEN}/sendMediaGroup",
                      data={"chat_id": CHAT_ID,
                            "media": json.dumps(media, ensure_ascii=False)},
                      timeout=60)
        print("ալբոմ՝", r.status_code, r.text[:200])
        if not r.ok:
            r1 = sess.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                           data={"chat_id": CHAT_ID, "photo": photo_list[0],
                                 "caption": caption, "parse_mode": "HTML",
                                 "reply_markup": json.dumps(markup)}, timeout=40)
            print("մեկ նկարով՝", r1.status_code, r1.text[:200])
            return r1.ok
        mid = None
        try:
            res = r.json().get("result") or []
            if res:
                mid = res[0]["message_id"]
        except Exception:
            mid = None
        payload = {"chat_id": CHAT_ID, "text": "Связаться с арендодателем",
                   "reply_markup": json.dumps(markup)}
        if mid:
            payload["reply_parameters"] = json.dumps({"message_id": mid})
        r2 = sess.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                       data=payload, timeout=40)
        print("կոճակ՝", r2.status_code, r2.text[:200])
        return r.ok

    payload = {"chat_id": CHAT_ID, "parse_mode": "HTML",
               "reply_markup": json.dumps(markup)}
    if photo_list:
        payload["photo"] = photo_list[0]
        payload["caption"] = caption
        method = "sendPhoto"
    else:
        payload["text"] = caption
        method = "sendMessage"
    r = sess.post(f"https://api.telegram.org/bot{TOKEN}/{method}",
                  data=payload, timeout=40)
    print("ուղարկում՝", r.status_code, r.text[:300])
    return r.ok

def load():
    if os.path.exists(STATE):
        return json.load(open(STATE, encoding="utf-8"))
    return {"seen": [], "queue": [], "last_publish": 0, "turn": 0,
            "published": {}, "failed": {}}

def save(st):
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)

def main():
    st = load()
    for k, v in (("seen", []), ("queue", []), ("published", {}),
                 ("failed", {}), ("turn", 0)):
        st.setdefault(k, v)
    st.setdefault("last_publish", 0)
    sess = requests.Session()
    now = time.time()

    collect(sess, st)
    while len(st["queue"]) > QUEUE_MAX:
        st["queue"].pop(0)
    print("հերթում՝", len(st["queue"]))

    if TEST:
        if st["queue"]:
            it = st["queue"].pop(0)
            d = item_data(sess, it["url"])
            cap = make_caption(sess, d)
            print("caption՝", cap[:300])
            if send(sess, d, cap):
                st["published"][it["key"]] = now
                st["last_publish"] = now
        save(st)
        return

    if st["queue"] and now - st["last_publish"] >= INTERVAL:
        want = ORDER[st["turn"] % len(ORDER)]
        for _ in range(3):
            if not st["queue"]:
                break
            idx = next((k for k, it in enumerate(st["queue"])
                        if it["src"] == want), 0)
            it = st["queue"].pop(idx)
            ok = False
            try:
                d = item_data(sess, it["url"])
                cap = make_caption(sess, d)
                ok = bool(cap) and send(sess, d, cap)
            except Exception as e:
                print("հրապարակման սխալ՝", e)
            if ok:
                st["last_publish"] = now
                st["turn"] = (st["turn"] + 1) % len(ORDER)
                st["published"][it["key"]] = now
                print("հրապարակվեց՝", it["key"])
                break
            st["failed"][it["key"]] = st["failed"].get(it["key"], 0) + 1
            if st["failed"][it["key"]] < 2:
                st["queue"].append(it)
                print("  հերթի վերջը՝", it["key"])
            else:
                print("  դեն նետվեց՝", it["key"])

    if len(st["published"]) > 50000:
        keys = list(st["published"])[-20000:]
        st["published"] = {k: st["published"][k] for k in keys}

    save(st)

main()
