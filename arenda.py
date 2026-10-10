# -*- coding: utf-8 -*-
# arenda.py — վարձույթի բոտ (@Marketplace_arm_bot → @arenda_armenia_arm)
import os, re, json, time, requests
from fetcher import jina

TOKEN    = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID  = os.environ.get("TELEGRAM_CHAT_ID_ARENDA", "")
JINA_KEY = os.environ.get("JINA_KEY", "")

STATE      = "state-arenda.json"
INTERVAL   = 15 * 60
QUEUE_MAX  = 250
TEST       = True
SPEC_ORDER = "value"      # "value" → «60 кв.м — Общая площадь» | "label" → «Общая площадь: 60 кв.м»

LIST_CATS   = ["56"]
ESTATE_LIST = ["https://www.estate.am/ru/аренда-квартир-s4"]
MY_LIST     = ["https://myrealty.am/ru", "https://myrealty.am/ru?page=2"]
ORDER = ["list", "list", "list", "estate", "list", "list", "list", "myrealty"]

ITEM_RE   = re.compile(r"/ru/item/(\d+)")
ESTATE_RE = re.compile(r"https://www\.estate\.am/ru/[^\s\)\]\"']+-d(\d+)")
MY_RE     = re.compile(r"https://myrealty\.am/ru/snyat-kvartiru/[^\s\)\]\"']+/(\d+)")
PHOTO_RE  = re.compile(r"(?:https?:)?//(?:img\.list\.am/[^\s\)\]\"']+|pic\.estate\.am/[^\s\)\]\"']+|myrealty\.am/images/[0-9a-f]{2}/[0-9a-f]{2}/[^\s\)\]\"']+)\.(?:jpg|jpeg|png|webp)", re.I)
PRICE_RE  = re.compile(r"([\d][\d\s.,]{2,})\s*(֏|AMD|драм|\$|USD|€|EUR|Месяц|ամիս)", re.I)
TEL_RE    = re.compile(r"tel:([+\d][\d\s\-\(\)]{6,})")
TITLE_RE  = re.compile(r"((?:Снять|Аренда|Сдается|Сдаётся|Վարձով)[^\n]{5,140}квартир[^\n]{0,90})")
AREA_RE   = re.compile(r"(\d{2,4})\s*(?:Кв\.?\s*м|քմ|ք\.մ)", re.I)
FLOOR_RE  = re.compile(r"(\d{1,3})\s*/\s*(\d{1,3})\s*(?:Этаж|этаж|հարկ)", re.I)
LABELS    = ("Общая площадь", "Жилая площадь", "Площадь кухни", "Площадь", "Высота потолков",
             "Высота потолка", "Этажей в доме", "Этажность", "Этаж", "Количество комнат",
             "Комнаты", "Комнат", "Количество санузлов", "Сан узлы", "Сан узел", "Год постройки",
             "Тип постройки", "Состояние", "Ремонт", "Мебель", "Балкон", "Отопление", "Лифт",
             "Интернет", "Комиссия с арендатора", "Комиссия", "Предоплата", "Статус доступности")
KEY       = {"общая площадь": "площадь", "жилая площадь": "площадь", "площадь кухни": "кухня",
             "площадь": "площадь", "высота потолков": "высота", "высота потолка": "высота",
             "этажей в доме": "этажей", "этажность": "этажей", "этаж": "этаж",
             "количество комнат": "комнат", "комнаты": "комнат", "комнат": "комнат",
             "количество санузлов": "санузел", "сан узлы": "санузел", "сан узел": "санузел",
             "год постройки": "год", "тип постройки": "тип", "состояние": "состояние",
             "ремонт": "состояние", "мебель": "мебель", "балкон": "балкон",
             "отопление": "отопление", "лифт": "лифт", "интернет": "интернет",
             "комиссия с арендатора": "комиссия", "комиссия": "комиссия",
             "предоплата": "предоплата", "статус доступности": "статус"}
NAMES     = {"площадь": "Общая площадь", "кухня": "Площадь кухни", "высота": "Высота потолков",
             "этажей": "Этажей в доме", "этаж": "Этаж", "комнат": "Количество комнат",
             "санузел": "Количество санузлов", "год": "Год постройки", "тип": "Тип постройки",
             "состояние": "Состояние", "мебель": "Мебель", "балкон": "Балкон",
             "отопление": "Отопление", "лифт": "Лифт", "интернет": "Интернет",
             "комиссия": "Комиссия", "предоплата": "Предоплата", "статус": "Статус доступности"}
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

def clean_text(t):
    t = re.sub(r"\s*\|\s*[^|]{0,40}$", "", t or "").strip()
    t = re.sub(r"[,|]?\s*\d{5,9}\s*$", "", t).strip()
    return t.strip(" ,|-–—")

def similar(a, b):
    a = re.sub(r"\W+", "", (a or "").lower())[:60]
    b = re.sub(r"\W+", "", (b or "").lower())[:60]
    return bool(a) and (a == b or a in b or b in a)

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
    lines = []
    for l in md.split("\n"):
        l = re.sub(r"^[|*#>\s\-–—]+", "", l.strip())
        lines.append(re.sub(r"[|\s]+$", "", l).strip())
    out, keys = [], set()
    for i, line in enumerate(lines):
        if not line or len(line) > 90:
            continue
        for lab in sorted(LABELS, key=len, reverse=True):
            low, ll = line.lower(), lab.lower()
            if low.startswith(ll):
                val = line[len(lab):]
            elif low.endswith(ll):
                val = line[:-len(lab)]
            else:
                continue
            val = val.strip(" :|–—-*").strip()
            if not val and i + 1 < len(lines):
                val = lines[i + 1].strip(" :|–—-*").strip()
            k = KEY.get(ll, "")
            if val and k and k not in keys and len(val) <= 45:
                num = re.search(r"\d+(?:[.,]\d+)?", val)
                if k in ("санузел", "комнат", "этажей", "год", "высота") and num:
                    val = num.group(0) + (" մ" if k == "высота" else "")
                keys.add(k)
                out.append((k, val))
            break
    return out[:12]

def find_desc(md):
    paras = [p.strip() for p in re.split(r"\n\s*\n", md)]
    st_i = None
    for i, p in enumerate(paras):
        if re.match(r"^#*\s*Описание\b", p):
            st_i = i + 1
            break
    chunks = []
    if st_i is not None:
        for p in paras[st_i:st_i + 4]:
            if not p:
                continue
            if re.match(r"^(Похожие|Номер объявления|Пожаловаться|Переведено|"
                        r"Информация о недвижимости|Контакты|Телефон|Комиссия|Предоплата|Цена|Оплата)", p):
                break
            if len(p) < 40 or re.match(r"^#+\s", p):
                if chunks:
                    break
                continue
            chunks.append(p)
            if len(" ".join(chunks)) > 600:
                break
    if not chunks:
        longs = [p for p in paras if 150 <= len(p) <= 1000 and len(p.split()) >= 15
                 and not re.search(r"http|©|list\.am|myrealty", p, re.I)]
        if longs:
            chunks = [max(longs, key=len)]
    return " ".join(" ".join(chunks).split())

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
    html = fetch(sess, url, {"x-respond-with": "html"})
    photo_list = collect_photos(md, html)

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
        title = clean_text(m.group(1))
    if is_generic(title):
        m = TITLE_RE.search(md)
        if m:
            title = clean_text(m.group(1))
    if is_generic(title):
        rooms = re.search(r"/(\d+)-komnatnaya/", url)
        base = "Аренда"
        if rooms:
            base += " " + rooms.group(1) + "-комнатной квартиры"
        if place:
            base += ", " + place
        title = clean_text(base)

    specs, keys = [], set()
    def add_spec(k, val):
        if k not in keys and k in NAMES and val:
            keys.add(k)
            specs.append((k, val))
    m = AREA_RE.search(md)
    if m:
        add_spec("площадь", m.group(1) + " кв.м")
    m = FLOOR_RE.search(md)
    if m:
        add_spec("этаж", m.group(1) + "/" + m.group(2))
    for k, val in features(md):
        add_spec(k, val)

    feats = []
    for k, val in specs:
        name = NAMES[k]
        feats.append((val + " — " + name) if SPEC_ORDER == "value" else (name + ": " + val))

    price = ""
    m = PRICE_RE.search(md)
    if m:
        num, cur = m.group(1).strip(), m.group(2)
        price = (num + " $/мес") if cur.lower() in ("месяц", "ամիս") else (num + " " + cur).strip()

    desc = clean_text(find_desc(md))
    if desc and similar(desc, title):
        desc = ""

    phone = ""
    m = TEL_RE.search(md + "\n" + html)
    if m:
        phone = " ".join(m.group(1).split())

    print(f"  {url}\n    md {len(md)}, html {len(html)}, նկար {len(photo_list)}, վերնագիր {title!r}, գին {price!r}, {feats}")
    return {"title": title, "price": price, "desc": desc, "place": place,
            "feats": feats, "phone": phone, "photos": photo_list, "url": url}

def make_caption(sess, d):
    head = translate(sess, d["title"]).strip()
    if not head or latin_junk(head):
        alt = translate(sess, d["desc"][:300]).strip()
        head = re.split(r"[.!?]\s", alt)[0].strip()[:90] if alt else ""
    if not head:
        head = "Объявление об аренде"
    lines = ["<b>" + esc(head) + "</b>"]
    if d["feats"]:
        lines.append("\n".join(esc(x) for x in d["feats"]))
    if d["desc"]:
        lines.append(esc(translate(sess, d["desc"][:600])))
    if d["price"]:
        lines.append("<b>" + esc(d["price"]) + "</b>")
    if d["phone"]:
        lines.append("Тел: <code>" + esc(d["phone"]) + "</code>")
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
            print("caption՝", cap[:500])
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
