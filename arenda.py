# -*- coding: utf-8 -*-
# arenda.py — վարձույթի բոտ (@Marketplace_arm_bot → @arenda_armenia_arm)
import os, re, json, time, requests
from fetcher import jina

TOKEN    = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID  = os.environ.get("TELEGRAM_CHAT_ID_ARENDA", "")
JINA_KEY = os.environ.get("JINA_KEY", "")

STATE     = "state-arenda.json"
INTERVAL  = 15 * 60
QUEUE_MAX = 250
TEST      = True

LIST_CATS   = ["56"]
ESTATE_LIST = ["https://www.estate.am/ru/аренда-квартир-s4"]
MY_LIST     = ["https://myrealty.am/ru", "https://myrealty.am/ru?page=2"]
ORDER = ["list", "list", "list", "estate", "list", "list", "list", "myrealty"]

ITEM_RE   = re.compile(r"/ru/item/(\d+)")
ESTATE_RE = re.compile(r"https://www\.estate\.am/ru/[^\s\)\]\"']+-d(\d+)")
MY_RE     = re.compile(r"https://myrealty\.am/ru/snyat-kvartiru/[^\s\)\]\"']+/(\d+)")
PHOTO_RE  = re.compile(r"(?:https?:)?//(?:img\.list\.am/[a-z]+/\d+/[0-9a-f]+|pic\.estate\.am/[^\s\)\]\"']+|myrealty\.am/images/[0-9a-f]{2}/[0-9a-f]{2}/[^\s\)\]\"']+)\.(?:jpg|jpeg|png|webp)", re.I)
PRICE_RE  = re.compile(r"([\d][\d\s.,]{2,})\s*(֏|AMD|драм|\$|USD|€|EUR|Месяц|ամիս)", re.I)
TEL_RE    = re.compile(r"tel:([+\d][\d\s\-\(\)]{6,})")
TITLE_RE  = re.compile(r"((?:Снять|Аренда|Сдается|Сдаётся|Վարձով)[^\n]{5,140}квартир[^\n]{0,90})")
AREA_RE   = re.compile(r"(\d{2,4})\s*(?:Кв\.?\s*м|քմ|ք\.մ)")
FLOOR_RE  = re.compile(r"(\d{1,3})\s*/\s*(\d{1,3})\s*(?:Этаж|этаж|հարկ)")
LABELS    = ("Сан узел", "Тип постройки", "Высота потолка", "Состояние", "Мебель",
             "Балкон", "Отопление", "Год постройки", "Площадь", "Комнат")
GENERIC   = ("КВАРТИРЫ", "ОСОБНЯКИ", "ДОМА", "АРЕНДА", "ОФИСЫ", "ПРОДАЖА", "НОВОСТРОЙКИ")

def fetch(sess, url, extra=None):
    md = jina(sess, url, extra) or ""
    if len(md) > 800:
        return md
    if JINA_KEY:
        try:
            r = sess.get("https://r.jina.ai/" + url, timeout=60,
                         headers={"Authorization": "Bearer " + JINA_KEY,
                                  "User-Agent": "curl/8.5.0"})
            t = r.text or ""
            if r.status_code == 200 and len(t) > 800 and "just a moment" not in t.lower():
                print("  jina-ընթերցիչ՝", len(t), url[:70])
                return t
            print("  jina-ընթերցիչ ձախողվեց՝", r.status_code, len(t))
        except Exception as e:
            print("  jina սխալ՝", type(e).__name__)
    return md

def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def has_cyr(s):
    return bool(re.search(r"[А-Яа-яЁё]", s or ""))

def latin_junk(t):
    t = (t or "").strip()
    if not t or has_cyr(t):
        return False
    return len(t.split()) > 2

def is_generic(t):
    t = (t or "").strip()
    return (not t) or (t.upper() in GENERIC) or (t.isupper() and len(t.split()) <= 2)

def clean_title(t):
    t = re.sub(r"\s*\|\s*[^|]{0,40}$", "", t or "").strip()
    t = re.sub(r"[,|]?\s*\d{5,9}\s*$", "", t).strip()
    return t.strip(" ,|-–—")

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
            u = re.sub(r"_\d+x\d+(?=\.(?:jpe?g|png|webp)$)", "", u)
            if u not in out:
                out.append(u)
    return out[:10]

def features(md):
    lines = [l.strip().lstrip("#* ").strip() for l in md.split("\n")]
    out = []
    for i, line in enumerate(lines):
        for lab in LABELS:
            if line == lab or line.startswith(lab):
                val = line[len(lab):].strip(" :|–—-").strip()
                if not val and i + 1 < len(lines):
                    val = lines[i + 1].strip(" |–—-").strip()
                if val and 1 <= len(val) <= 45 and lab not in " | ".join(out):
                    out.append(lab + ": " + val)
                break
    return out[:8]

def add(st, src, key, url, found):
    found.append((src, key, url))
    if key in st["seen"]:
        return 0
    st["seen"].append(key)
    st["queue"].append({"src": src, "key": key, "url": url})
    return 1

def collect(sess, st):
    found = []
    for cat in LIST_CATS:
        md = fetch(sess, "https://www.list.am/ru/category/" + cat)
        ids = []
        for i in ITEM_RE.findall(md):
            if i not in ids:
                ids.append(i)
        n = sum(add(st, "list", "list:" + i,
                    "https://www.list.am/ru/item/" + i, found) for i in ids)
        print(f"list.am {cat}: գտնվեց {len(ids)}, նոր՝ {n}")
        time.sleep(8)
    for page in ESTATE_LIST:
        md = fetch(sess, page)
        items = {}
        for m in ESTATE_RE.finditer(md):
            items[m.group(1)] = m.group(0)
        n = sum(add(st, "estate", "estate:" + i, u, found) for i, u in items.items())
        print(f"estate.am: գտնվեց {len(items)}, նոր՝ {n}")
        time.sleep(8)
    for page in MY_LIST:
        md = fetch(sess, page)
        items = {}
        for m in MY_RE.finditer(md):
            items[m.group(1)] = m.group(0)
        n = sum(add(st, "myrealty", "my:" + i, u, found) for i, u in items.items())
        print(f"myrealty.am {page}: գտնվեց {len(items)}, նոր՝ {n}")
        time.sleep(8)
    return found

def item_data(sess, url):
    md = fetch(sess, url)
    for cut in ("Похожие объявления", "Похожие"):
        i = md.find(cut)
        if i > 0:
            md = md[:i]
    photo_list = collect_photos(md)
    html = ""
    if not photo_list:
        html = fetch(sess, url, {"x-respond-with": "html"})
        photo_list = collect_photos(html)

    place = ""
    m = re.search(r"\[([^\]]*›[^\]]*)\]", md)
    if m:
        place = m.group(1).strip()
    if not place:
        for line in md.split("\n"):
            line = line.strip().lstrip("#* ").strip()
            if "Ереван" in line and "," in line and 5 < len(line) < 90 and "http" not in line:
                place = line
                break

    title = ""
    m = re.search(r"^#\s+(.+)$", md, re.M)
    if m:
        title = clean_title(m.group(1))
    if is_generic(title):
        m = TITLE_RE.search(md)
        if m:
            title = clean_title(m.group(1))
    if is_generic(title):
        rooms = re.search(r"/(\d+)-komnatnaya/", url)
        base = "Аренда"
        if rooms:
            base += " " + rooms.group(1) + "-комнатной квартиры"
        if place:
            base += ", " + place
        title = clean_title(base)

    feats = []
    m = AREA_RE.search(md)
    if m:
        feats.append(m.group(1) + " кв.м")
    m = FLOOR_RE.search(md)
    if m:
        feats.append("этаж " + m.group(1) + "/" + m.group(2))
    for f in features(md):
        if f.split(":")[0] not in " | ".join(feats):
            feats.append(f)

    price = ""
    m = PRICE_RE.search(md)
    if m:
        num, cur = m.group(1).strip(), m.group(2)
        price = (num + " $/мес") if cur.lower() in ("месяц", "ամիս") else (num + " " + cur).strip()

    desc = ""
    m = re.search(r"Описание\s*\n+(.+?)\n\s*(?:Номер объявления|Похожие|Пожаловаться)", md, re.S)
    if m:
        desc = " ".join(m.group(1).split())

    phone = ""
    m = TEL_RE.search(md + "\n" + html)
    if m:
        phone = " ".join(m.group(1).split())

    print(f"  {url}\n    md {len(md)}, նկար {len(photo_list)}, վերնագիր {title!r}, գին {price!r}, {feats}")
    return {"title": title, "price": price, "desc": desc, "place": place,
            "feats": feats, "phone": phone, "photos": photo_list, "url": url}

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
    if d["feats"]:
        lines.append(" · ".join(esc(x) for x in d["feats"]))
    if d["place"] and d["place"] not in head:
        lines.append(esc(d["place"]))
    if d["desc"]:
        lines.append(esc(translate(sess, d["desc"][:600])))
    if d["phone"]:
        lines.append("Телефон: <code>" + esc(d["phone"]) + "</code>")
    return "\n\n".join(x for x in lines if x)[:1024]

def send(sess, d, caption):
    photo_list = d["photos"]
    markup = None
    if not d["phone"]:
        markup = {"inline_keyboard": [[{"text": "Открыть объявление", "url": d["url"]}]]}
    if len(photo_list) >= 2:
        first = {"type": "photo", "media": photo_list[0],
                 "caption": caption, "parse_mode": "HTML"}
        if markup:
            first["reply_markup"] = markup
        media = [first]
        for p in photo_list[1:10]:
            media.append({"type": "photo", "media": p})
        r = sess.post(f"https://api.telegram.org/bot{TOKEN}/sendMediaGroup",
                      data={"chat_id": CHAT_ID,
                            "media": json.dumps(media, ensure_ascii=False)}, timeout=60)
        print("ալբոմ՝", r.status_code, r.text[:200])
        if not r.ok:
            payload = {"chat_id": CHAT_ID, "photo": photo_list[0],
                       "caption": caption, "parse_mode": "HTML"}
            if markup:
                payload["reply_markup"] = json.dumps(markup)
            r1 = sess.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                           data=payload, timeout=40)
            print("մեկ նկարով՝", r1.status_code, r1.text[:200])
            return r1.ok
        return r.ok
    payload = {"chat_id": CHAT_ID, "parse_mode": "HTML"}
    if markup:
        payload["reply_markup"] = json.dumps(markup)
    if photo_list:
        payload["photo"] = photo_list[0]
        payload["caption"] = caption
        method = "sendPhoto"
    else:
        payload["text"] = caption
        method = "sendMessage"
    r = sess.post(f"https://api.telegram.org/bot{TOKEN}/{method}", data=payload, timeout=40)
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
    for k, v in (("seen", []), ("queue", []), ("published", {}), ("failed", {}), ("turn", 0)):
        st.setdefault(k, v)
    st.setdefault("last_publish", 0)
    sess = requests.Session()
    now = time.time()

    found = collect(sess, st)
    while len(st["queue"]) > QUEUE_MAX:
        st["queue"].pop(0)
    print("հերթում՝", len(st["queue"]))

    if TEST:
        pick = st["queue"].pop(0) if st["queue"] else None
        if pick is None and found:
            s, k, u = found[0]
            pick = {"src": s, "key": k, "url": u}
        if pick:
            d = item_data(sess, pick["url"])
            cap = make_caption(sess, d)
            print("caption՝", cap[:400])
            if send(sess, d, cap):
                st["published"][pick["key"]] = now
                st["last_publish"] = now
        save(st)
        return

    if st["queue"] and now - st["last_publish"] >= INTERVAL:
        want = ORDER[st["turn"] % len(ORDER)]
        for _ in range(3):
            if not st["queue"]:
                break
            idx = next((k for k, it in enumerate(st["queue"]) if it["src"] == want), 0)
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
