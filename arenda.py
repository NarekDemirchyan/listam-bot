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

LIST_CATS   = ["56"]
ESTATE_LIST = ["https://www.estate.am/ru/аренда-квартир-s4"]
MY_LIST     = ["https://myrealty.am/ru", "https://myrealty.am/ru?page=2"]
ORDER = ["list", "list", "list", "estate", "list", "list", "list", "myrealty"]

CARD = [("комнат", "🏢 Комнат"), ("площадь", "📐 Площадь"), ("этаж", "🏙 Этаж"),
        ("состояние", "🛋 Состояние"), ("отопление", "🔥 Отопление"),
        ("кондиционер", "❄️ Кондиционер"), ("балкон", "🏞 Балкон"), ("дети", "👫 С детьми"),
        ("животные", "🐶 Животные"), ("парковка", "🚗 Парковка"), ("срок", "📅 Срок аренды"),
        ("цена", "💰 Цена"), ("залог", "🔑 Залог"), ("коммунальные", "🧾 Коммунальные"),
        ("статус", "📅 Свободна"), ("комиссия", "🤝 Комиссия")]

ITEM_RE   = re.compile(r"/ru/item/(\d+)")
ESTATE_RE = re.compile(r"https://www\.estate\.am/ru/[^\s\)\]\"']+-d(\d+)")
MY_RE     = re.compile(r"https://myrealty\.am/ru/snyat-kvartiru/[^\s\)\]\"']+/(\d+)")
PHOTO_RE  = re.compile(r"(?:https?:)?//(?:img\.list\.am/[^\s\)\]\"']+|pic\.estate\.am/[^\s\)\]\"']+|myrealty\.am/images/[0-9a-f]{2}/[0-9a-f]{2}/[^\s\)\]\"']+)\.(?:jpg|jpeg|png|webp)", re.I)
PRICE_RE  = re.compile(r"([\d][\d\s.,]{2,})\s*(֏|AMD|драм|\$|USD|€|EUR|Месяц|ամիս)", re.I)
TEL_RE    = re.compile(r"tel:([+\d][\d\s\-\(\)]{6,})")
OG_RE     = re.compile(r'<meta[^>]+(?:property|name)=["\']og:(title|description)["\'][^>]*content=["\']([^"\']*)', re.I)
TITLE_RE  = re.compile(r"((?:Снять|Аренда|Сдается|Сдаётся|Վարձով)[^\n]{5,140}квартир[^\n]{0,90})")
AREA_RE   = re.compile(r"(\d{2,4})\s*(?:Кв\.?\s*м|քմ|ք\.մ)", re.I)
FLOOR_RE  = re.compile(r"(\d{1,3})\s*/\s*(\d{1,3})\s*(?:Этаж|этаж|հարկ)", re.I)
BAD_DESC  = re.compile(r"breadcrumb|chevron|\.svg|!\[|\]\(|https?://", re.I)
HOURS_RE  = re.compile(r"(?:Пн|Вт|Ср|Чт|Пт|Сб|Вс|Понедельник|Вторник|Среда|Четверг|Пятница|Суббота|Воскресенье)"
                       r"[^\nА-Яа-я]{0,12}\d{1,2}[:.]\d{2}\s*[-–—]\s*\d{1,2}[:.]\d{2}", re.I)
WORK_RE   = re.compile(r"(?:График работы|Часы работы|Рабочие часы)[^\n]{0,80}", re.I)
ZALOG_RE  = r"Предоплата\s*\n+\s*(1 месяц|2 месяца|3 месяца|\d+\s*месяц(?:а|ев)?|1 ամիս|2 ամիս|[Бб]ез предоплаты)"
LABELS    = ("Общая площадь", "Жилая площадь", "Площадь кухни", "Площадь", "Высота потолков",
             "Высота потолка", "Этажей в доме", "Этажность", "Этаж", "Количество комнат",
             "Комнаты", "Комнат", "Количество санузлов", "Сан узлы", "Сан узел", "Год постройки",
             "Тип здания", "Тип постройки", "Состояние", "Ремонт", "Мебель", "Балкон", "Отопление",
             "Лифт", "Интернет", "Комиссия с арендатора", "Комиссия", "Предоплата",
             "Статус доступности")
KEY       = {"общая площадь": "площадь", "жилая площадь": "площадь", "площадь кухни": "кухня",
             "площадь": "площадь", "высота потолков": "высота", "высота потолка": "высота",
             "этажей в доме": "этажей", "этажность": "этажей", "этаж": "этаж",
             "количество комнат": "комнат", "комнаты": "комнат", "комнат": "комнат",
             "количество санузлов": "санузел", "сан узлы": "санузел", "сан узел": "санузел",
             "год постройки": "год", "тип здания": "тип", "тип постройки": "тип",
             "состояние": "состояние", "ремонт": "состояние", "мебель": "мебель",
             "балкон": "балкон", "отопление": "отопление", "лифт": "лифт", "интернет": "интернет",
             "комиссия с арендатора": "комиссия", "комиссия": "комиссия",
             "предоплата": "залог", "статус доступности": "статус"}
NAMES     = {"площадь": "Площадь", "кухня": "Площадь кухни", "высота": "Высота потолков",
             "этажей": "Этажей в доме", "этаж": "Этаж", "комнат": "Комнат",
             "санузел": "Санузлов", "год": "Год постройки", "тип": "Тип постройки",
             "состояние": "Состояние", "мебель": "Мебель", "балкон": "Балкон",
             "отопление": "Отопление", "лифт": "Лифт", "интернет": "Интернет",
             "комиссия": "Комиссия", "залог": "Залог", "статус": "Свободна",
             "дети": "Дети", "животные": "Животные", "парковка": "Парковка",
             "кондиционер": "Кондиционер", "коммунальные": "Коммунальные", "срок": "Срок аренды",
             "район": "Район"}
NUM_KEYS  = ("площадь", "этаж", "этажей", "комнат", "санузел", "год", "высота")
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

def clean_title(t):
    t = clean_text(t)
    t = re.sub(r"\s*[-–|]\s*[^-–|]*(?:List\.am|Аренда квартир|Long-term|Долгосрочная)[^-–|]*$", "", t, flags=re.I)
    return t.strip(" ,|-–—")

def clean_desc_text(t):
    t = WORK_RE.sub(" ", t or "")
    t = HOURS_RE.sub(" ", t)
    t = re.sub(r"\s*Переведено с армянского\s*", " ", t, flags=re.I)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip(" ,|;–—-")

def similar(a, b):
    a = re.sub(r"\W+", "", (a or "").lower())[:60]
    b = re.sub(r"\W+", "", (b or "").lower())[:60]
    return bool(a) and (a == b or a in b or b in a)

def fmt_phone(p):
    d = re.sub(r"\D", "", p or "")
    if d.startswith("374") and len(d) == 11:
        return "+374 " + d[3:5] + " " + d[5:8] + " " + d[8:]
    if len(d) == 8:
        return "+374 " + d[0:2] + " " + d[2:5] + " " + d[5:]
    return (p or "").strip()

def low1(s):
    s = (s or "").strip()
    return s[:1].lower() + s[1:] if s else s

def meta(html, name):
    for k, v in OG_RE.findall(html or ""):
        if k.lower() == name:
            return v.strip()
    return ""

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

def is_label(s):
    low = (s or "").strip().lower()
    return any(low == lab.lower() for lab in LABELS)

def k_num(lab):
    return KEY.get((lab or "").lower(), "") in NUM_KEYS

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
            if not val:
                nxt = next((x for x in lines[i + 1:i + 3] if x and not is_label(x)), "")
                prv = next((x for x in reversed(lines[max(0, i - 3):i]) if x and not is_label(x)), "")
                if k_num(lab) and not re.search(r"\d", nxt) and re.search(r"\d", prv):
                    val = prv
                else:
                    val = nxt or prv
            k = KEY.get(ll, "")
            if val and k and k not in keys and len(val) <= 45:
                num = re.search(r"\d+(?:[.,]\d+)?", val)
                if k in NUM_KEYS and num:
                    val = num.group(0) + (" м" if k == "высота" else "")
                keys.add(k)
                out.append((k, val))
            break
    return out[:14]

def spec_pairs(md):
    out = []

    def grab(key, rx):
        m = re.search(rx, md, re.S | re.I)
        if m:
            v = " ".join(m.group(1).split())
            if v and len(v) <= 45:
                out.append((key, v))

    grab("площадь", r"([\d]{2,4}(?:[.,]\d+)?\s*кв\.?\s*м\.?)\s*\n+\s*(?:Общая площадь|Площадь)")
    grab("этаж", r"(\d{1,3})\s*\n+\s*Этаж\s*\n+\s*\d{1,3}\s*\n+\s*Этажей в доме")
    grab("этажей", r"\d{1,3}\s*\n+\s*Этаж\s*\n+\s*(\d{1,3})\s*\n+\s*Этажей в доме")
    grab("высота", r"([\d.,]+\s*м)\s*\n+\s*Высота потолков?")
    grab("комнат", r"(\d{1,3})\s*\n+\s*Количество комнат")
    grab("санузел", r"(\d{1,3})\s*\n+\s*Количество санузлов")
    grab("залог", ZALOG_RE)
    grab("комиссия", r"([\d.,]+\s*%)\s*\n+\s*Комиссия с арендатора")
    grab("статус", r"(Свободно сейчас|Сдано|Забронировано)\s*\n+\s*Статус доступности")
    grab("мебель", r"Мебель\s*\n+\s*(С мебелью|Без мебели|Частично)")
    grab("состояние", r"Ремонт\s*\n+\s*(Евроремонт|Новый ремонт|Капитальный ремонт|Косметический ремонт|Без ремонта|Дизайнерский)")
    grab("балкон", r"Балкон\s*\n+\s*(Открытый|Закрытый|Есть|Нет)")
    grab("тип", r"Тип (?:здания|постройки)\s*\n+\s*(.{2,30})")
    grab("район", r"Регион\s*\n+\s*(.{2,45})")
    grab("отопление", r"Отопление\s*\n+\s*(.{2,30})")
    grab("срок", r"Срок аренды\s*\n+\s*(.{2,30})")
    grab("дети", r"Можно с детьми\s*\n+\s*(Да|Нет|По договорённости|По договоренности)")
    grab("животные", r"Можно с животными\s*\n+\s*(Да|Нет|По договорённости|По договоренности)")
    grab("коммунальные", r"Коммунальные платежи\s*\n+\s*(Включены|Не включены)")
    grab("парковка", r"Парковка\s*\n+\s*(Да|Есть|Нет)")
    grab("кондиционер", r"Кондиционер\s*\n+\s*(Да|Есть|Нет)")
    return out

def md_text(t):
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t or "")
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"\*\*|__", "", t)
    return re.sub(r"[ \t]+", " ", t).strip()

def find_desc(md):
    paras = [md_text(p) for p in re.split(r"\n\s*\n", md)]
    chunks = []
    for i, p in enumerate(paras):
        m = re.match(r"^\s*[#*>\s\-–—]*Описание\b\s*[:\-–—]?\s*(.*)$", p, re.S)
        if not m:
            continue
        tail = m.group(1).strip()
        if tail:
            chunks.append(tail)
        for q in paras[i + 1:i + 5]:
            q = q.strip()
            if not q:
                continue
            if re.match(r"^(Похожие|Номер объявления|Пожаловаться|Переведено|История цены|"
                        r"Информация о недвижимости|Контакты|Телефон|Комиссия|Предоплата|Цена|Оплата)", q):
                break
            if len(q) < 40 or re.match(r"^#+\s", q) or BAD_DESC.search(q):
                if chunks:
                    break
                continue
            chunks.append(q)
            if len(" ".join(chunks)) > 700:
                break
        break
    if not chunks:
        longs = [p for p in paras if 150 <= len(p) <= 1200 and len(p.split()) >= 20
                 and not BAD_DESC.search(p) and not re.match(r"^[\W\d\s]+$", p)]
        if longs:
            chunks = [max(longs, key=len)]
    desc = clean_desc_text(" ".join(" ".join(chunks).split()))
    if len(desc.split()) < 8 or BAD_DESC.search(desc):
        return ""
    return desc

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
    md_cut = md
    for cut in ("Похожие объявления", "Выберите ваш язык", "Пожаловаться", "archive-index"):
        i = md_cut.find(cut)
        if i > 0:
            md_cut = md_cut[:i]
    html = fetch(sess, url, {"x-respond-with": "html"})
    photo_list = collect_photos(md_cut, html)

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
        t = clean_title(meta(html, "title"))
        if t:
            title = t
    if is_generic(title):
        m = TITLE_RE.search(md)
        if m:
            title = clean_title(m.group(1))
    if is_generic(title):
        title = "Аренда квартиры" + (", " + place if place else "")

    specs, keys = [], set()
    def add_spec(k, val):
        if k not in keys and k in NAMES and val:
            keys.add(k)
            specs.append((k, val))
    m = AREA_RE.search(md)
    if m:
        add_spec("площадь", m.group(1) + " м²")
    m = FLOOR_RE.search(md)
    if m:
        add_spec("этаж", m.group(1) + "/" + m.group(2))
    for k, val in spec_pairs(md):
        add_spec(k, val)
    for k, val in features(md):
        add_spec(k, val)
    vals = dict(specs)
    if not place and vals.get("район"):
        place = vals.pop("район")

    price = ""
    m = PRICE_RE.search(md)
    if m:
        num, cur = m.group(1).strip(), m.group(2)
        price = (num + " ֏" if cur.lower() in ("месяц", "ամիս") else (num + " " + cur).strip())

    desc = find_desc(md)
    if not desc:
        desc = clean_desc_text(md_text(meta(html, "description")))
        if len(desc.split()) < 8:
            desc = ""
    if desc and similar(desc, title):
        desc = ""

    phone = ""
    m = TEL_RE.search(md + "\n" + html)
    if m:
        phone = fmt_phone(" ".join(m.group(1).split()))

    print(f"  {url}\n    md {len(md)}, html {len(html)}, նկար {len(photo_list)}, վերնագիր {title!r}, "
          f"գին {price!r}, քարտ {vals}, հեռախոս {'այո' if phone else 'ոչ'}, նկարագրություն {len(desc)}")
    return {"title": title, "price": price, "desc": desc, "place": place,
            "specs": vals, "phone": phone, "photos": photo_list, "url": url}

def card_block(d):
    v = d["specs"]
    card = []
    if d["place"]:
        card.append("📍 Район: " + esc(d["place"]))
    for key, label in CARD:
        if key == "этаж":
            val = v.get("этаж")
            tot = v.get("этажей")
            if val and "/" not in val and tot:
                val = val + "/" + tot
            elif not val:
                val = tot
        elif key == "состояние":
            parts = [low1(v.get("состояние")), low1(v.get("мебель"))]
            parts = [x for x in parts if x]
            val = ", ".join(parts) if parts else None
        elif key == "цена":
            val = (d["price"] + " / месяц") if d["price"] else None
        elif key == "статус":
            val = v.get("статус")
            if val and "свободно" in val.lower():
                val = "да"
        else:
            val = v.get(key)
        if val:
            card.append(label + ": " + esc(val))
    return "\n".join(card)

def make_caption(sess, d):
    head = translate(sess, d["title"]).strip()
    if not head or latin_junk(head):
        head = "Объявление об аренде"
    lines = ["<b>" + esc(head) + "</b>"]
    block = card_block(d)
    if block:
        lines.append(block)
    tail = ""
    if d["phone"]:
        tail = "По всем вопросам обращайтесь:\n📞 " + esc(d["phone"])
    cap = "\n\n".join(lines)
    room = 1024 - len(cap) - (len(tail) + 2 if tail else 0) - 2
    if d["desc"] and room > 80:
        txt = esc(translate(sess, d["desc"]))
        cap += "\n\n" + txt[:room]
    if tail:
        cap += "\n\n" + tail
    return cap[:1024]

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
                if not d["photos"] and not d["specs"] and not d["price"]:
                    print("  դատարկ էջ՝", it["key"])
                else:
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
