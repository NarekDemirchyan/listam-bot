# -*- coding: utf-8 -*-
import os, re, json, time, requests

TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID_AUTO", "")

STATE     = "state_auto.json"
INTERVAL  = 18 * 60      # как часто публиковать (сек)
SEED      = 30           # сколько объявлений поставить в очередь при первом запуске
MAX_QUEUE = 1000
TEST      = False

JINA = "https://r.jina.ai/"
BASE = "https://auto.am"
SITEMAPS = [f"{BASE}/sitemaps/offers-{i}.xml" for i in range(1, 11)]
HDRS = {"User-Agent": "curl/8.5.0"}

BLOCKED = ("just a moment", "attention required", "enable javascript",
           "checking your browser", "cloudflare")

def is_blocked(text):
    t = (text or "").strip()
    return len(t) < 800 or any(m in t.lower() for m in BLOCKED)

def jina(sess, url, extra=None):
    h = dict(HDRS)
    if extra:
        h.update(extra)
    for attempt in range(4):
        try:
            r = sess.get(JINA + url, headers=h, timeout=60)
            if r.status_code == 200 and not is_blocked(r.text):
                return r.text
            print(f"  jina {r.status_code} / защита, попытка {attempt + 1}")
        except Exception as e:
            print(f"  jina ошибка: {type(e).__name__}: {e}")
        time.sleep(10 * (attempt + 1))
    return ""

def fetch_sitemap(sess, url):
    """XML берём напрямую, при неудаче — через Jina."""
    try:
        r = sess.get(url, headers=HDRS, timeout=60)
        if r.status_code == 200 and "<urlset" in r.text:
            return r.text
    except Exception as e:
        print("  sitemap ошибка:", type(e).__name__)
    return jina(sess, url)

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
        print("  перевод недоступен:", type(e).__name__)
    return text

def has_cyr(s):
    return bool(re.search(r"[А-Яа-яЁё]", s or ""))

def get_ids(sess):
    ids = []
    for sm in SITEMAPS:
        xml = fetch_sitemap(sess, sm)
        for i in re.findall(r"auto\.am/(?:ru/|en/)?offer/(\d+)", xml):
            if i not in ids:
                ids.append(i)
        print(f"  {sm.rsplit('/', 1)[-1]}: всего {len(ids)} объявлений")
        time.sleep(5)
    return ids

def collect_photos(md, iid):
    urls = re.findall(
        rf"https://auto\.am/static/offers/{iid}/[ms]-[0-9a-f]+\.(?:webp|jpg|jpeg|png)",
        md, re.I)
    out = []
    for u in [x for x in urls if "/m-" in x] + [x for x in urls if "/m-" not in x]:
        if u not in out:
            out.append(u)
    return out[:10]

def field(md, name):
    m = re.search(rf"^{re.escape(name)}\s+([^\n\"]+?)(?:\s*\"|$)", md, re.M)
    return m.group(1).strip() if m else ""

def item_data(sess, iid):
    md = jina(sess, f"{BASE}/ru/offer/{iid}")
    cut = md.find("Подчеркнутое объявление")
    if cut > 0:
        md = md[:cut]

    title = ""
    m = re.search(r"^Title:\s*(.+?)(?:\s*\|\s*Auto\.am)?\s*$", md, re.M)
    if m:
        title = m.group(1).strip()

    usd = re.search(r"([\d][\d\s]*)\s*\$", md)
    amd = re.search(r"([\d][\d\s]*)\s*֏", md)
    price = " · ".join(x for x in [
        f"{usd.group(1).strip()} $" if usd else "",
        f"{amd.group(1).strip()} ֏" if amd else ""] if x)

    specs = " · ".join(x for x in (
        ("Пробег " + field(md, "Пробег")) if field(md, "Пробег") else "",
        field(md, "Тип кузова"),
        field(md, "Двигатель"),
        field(md, "Коробка передач"),
        ("руль " + field(md, "Руль").lower()) if field(md, "Руль") else "",
        field(md, "Цвет"),
    ) if x)

    where = ""
    m = re.search(r"(\d{2}\.\d{2}\.\d{4})\s+([А-ЯЁ][^\n]{2,60})", md)
    if m:
        where = f"{m.group(1)} · {m.group(2).strip()}"

    desc = ""
    m = re.search(r"Дополнительно\s*\n+(.+?)(?:\n\s*(?:Продавец|Похожие)\b|\Z)",
                  md, re.S)
    if m:
        parts, seen = [], set()
        for p in m.group(1).split("\n"):
            p = " ".join(p.split())
            if p and p not in seen:
                seen.add(p)
                parts.append(p)
        desc = " ".join(parts)[:900]

    phone = ""
    m = re.search(r"tel:(\+?\d+)", md)
    if m:
        phone = "+" + re.sub(r"\D", "", m.group(1))
        if phone.startswith("+374") and len(phone) == 12:
            phone = f"{phone[:4]} {phone[4:6]} {phone[6:]}"

    photos = collect_photos(md, iid)
    print(f"  {iid}: фото {len(photos)}, цена «{price}», тел {phone or '—'}")

    return {"title": title, "price": price, "specs": specs, "where": where,
            "desc": desc, "phone": phone, "photos": photos,
            "url": f"{BASE}/ru/offer/{iid}"}

def make_caption(sess, d):
    lines = []
    if d["title"]:
        lines.append(d["title"])
    if d["price"]:
        lines.append(d["price"])
    if d["specs"]:
        lines.append(d["specs"])
    if d["where"]:
        lines.append(d["where"])
    desc = d["desc"]
    if desc and not has_cyr(desc):
        desc = translate(sess, desc)
    if desc:
        lines.append(desc)
    if d["phone"]:
        lines.append("Телефон: " + d["phone"])
    return "\n\n".join(x for x in lines if x).strip()[:1024]

def send(sess, d, caption):
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
        if r.ok:
            return True
    if photos:
        r = sess.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                      data={"chat_id": CHAT_ID, "photo": photos[0],
                            "caption": caption}, timeout=40)
    else:
        r = sess.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": caption}, timeout=40)
    print("telegram:", r.status_code, r.text[:200])
    return r.ok

def load():
    if os.path.exists(STATE):
        return json.load(open(STATE, encoding="utf-8"))
    return {"seen": [], "queue": [], "last_publish": 0}

def save(st):
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)

def main():
    st = load()
    st.setdefault("failed", {})
    sess = requests.Session()

    ids = get_ids(sess)
    print("всего объявлений в sitemap:", len(ids))

    if TEST:
        if ids:
            d = item_data(sess, ids[0])
            send(sess, d, make_caption(sess, d))
        return

    if not st["seen"]:
        st["seen"] = ids[:]
        st["queue"] = ids[:SEED]
        save(st)
        print(f"первый запуск: в очередь {len(st['queue'])}, публикаций нет")
        return

    for iid in ids:
        if iid not in st["seen"]:
            st["seen"].append(iid)
            st["queue"].append(iid)

    st["seen"] = st["seen"][-20000:]
    st["queue"] = st["queue"][-MAX_QUEUE:]
    now = time.time()
    print("очередь:", len(st["queue"]))

    if st["queue"] and now - st["last_publish"] >= INTERVAL:
        for _ in range(3):
            if not st["queue"]:
                break
            iid = st["queue"].pop(0)
            ok = False
            try:
                d = item_data(sess, iid)
                cap = make_caption(sess, d)
                ok = bool(cap) and send(sess, d, cap)
            except Exception as e:
                print("ошибка публикации:", e)
            if ok:
                st["last_publish"] = now
                print("опубликовано:", iid)
                break
            st["failed"][iid] = st["failed"].get(iid, 0) + 1
            if st["failed"][iid] < 2:
                st["queue"].append(iid)
                print("  вернём в конец очереди:", iid)
            else:
                print("  брошен", iid)

    save(st)

main()
