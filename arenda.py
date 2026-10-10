# -*- coding: utf-8 -*-
# Ստուգիչ (probe). Ոչինչ չի հրապարակում, միայն տպում է, թե ինչ է գտնում։
import re, time, requests
from fetcher import jina

BASE_LIST  = "https://www.list.am"
LIST_CATS  = ["/ru/category/56"]
ESTATE_RSS = "https://www.estate.am/ru/аренда-квартир-s4.rss"
BASE_MY    = "https://myrealty.am"
MY_PAGES   = ["/ru/"]

ITEM_RE = re.compile(r"/ru/item/(\d+)")

def main():
    sess = requests.Session()

    print("=== list.am ===")
    for cat in LIST_CATS:
        md = jina(sess, BASE_LIST + cat) or ""
        ids, seen = [], set()
        for m in ITEM_RE.finditer(md):
            if m.group(1) not in seen:
                seen.add(m.group(1))
                ids.append(m.group(1))
        print(f"{cat}: {len(ids)} հայտարարություն, երկարությունը՝ {len(md)}")
        print("  օրինակ:", ids[:3])
        print("  նմուշ:", md[:200].replace("\n", " "))
        time.sleep(3)

    print("=== estate.am ===")
    xml = jina(sess, ESTATE_RSS) or ""
    items = re.findall(r"<item>(.*?)</item>", xml, re.S)
    print(f"RSS: {len(items)} item, երկարությունը՝ {len(xml)}")
    for b in items[:3]:
        t = re.search(r"<title>\s*(.*?)\s*</title>", b, re.S)
        l = re.search(r"<link>\s*(.*?)\s*</link>", b, re.S)
        print("  -", (t.group(1)[:80] if t else "?"), "|", (l.group(1)[:80] if l else "?"))

    print("=== myrealty.am ===")
    for page in MY_PAGES:
        md = jina(sess, BASE_MY + page) or ""
        links = []
        for m in re.finditer(r"https://myrealty\.am/[^\s\)\"']+", md):
            u = m.group(0).rstrip(".,)")
            if u not in links:
                links.append(u)
        print(f"{page}: {len(links)} հղում, երկարությունը՝ {len(md)}")
        print("  օրինակ:", links[:3])
        print("  նմուշ:", md[:200].replace("\n", " "))

main()
