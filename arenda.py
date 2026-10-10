# -*- coding: utf-8 -*-
# Ստուգիչ 2. Տպում է հայտարարությունների էջերի իրական կառուցվածքը։
import re, time, requests
from fetcher import jina

BASE_LIST = "https://www.list.am"
EST_LIST  = "https://www.estate.am/ru/аренда-квартир-s4"
EST_RSS   = EST_LIST + ".rss"
MY_LIST   = "https://myrealty.am/ru"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
ITEM_RE = re.compile(r"/ru/item/(\d+)")
EST_RE  = re.compile(r"https://www\.estate\.am/ru/[^\s\)\]\"]+-d(\d+)")
MY_RE   = re.compile(r"https://myrealty\.am/ru/[^\s\)\]\"]+/\d+")

def main():
    sess = requests.Session()

    print("=== list.am: մեկ հայտարարության էջ ===")
    md = jina(sess, BASE_LIST + "/ru/category/56") or ""
    ids = ITEM_RE.findall(md)
    print("category 56 հղումներ՝", len(ids))
    if ids:
        url = BASE_LIST + "/ru/item/" + ids[0]
        print("բացում եմ՝", url)
        page = jina(sess, url) or ""
        print("երկարությունը՝", len(page))
        print("ՆՄՈՒՇ (1500 նշան):")
        print(page[:1500].replace("\n", " | "))
        photos = re.findall(r"https?://[^\s\)\]\"']+\.(?:jpg|jpeg|png|webp)", page)
        print("նկարներ՝", len(photos), photos[:4])
        print("tel՝", re.findall(r"tel:\+?[\d\s\-\(\)]{6,}", page)[:3])
    time.sleep(3)

    print("=== estate.am: ցուցակի էջ ===")
    lst = jina(sess, EST_LIST) or ""
    print("հայտարարության հղումներ՝", len(EST_RE.findall(lst)), EST_RE.findall(lst)[:3])
    print("ՆՄՈՒՇ (900 նշան):")
    print(lst[:900].replace("\n", " | "))

    print("=== estate.am: RSS ուղիղ XML-ով ===")
    try:
        r = sess.get(EST_RSS, headers={"User-Agent": UA}, timeout=30)
        print("կոդ՝", r.status_code, "| երկարությունը՝", len(r.text),
              "| <item> քանակը՝", r.text.count("<item"))
        print("ՆՄՈՒՇ (600 նշան):", r.text[:600].replace("\n", " | "))
    except Exception as e:
        print("սխալ՝", type(e).__name__, str(e)[:120])
    time.sleep(3)

    print("=== myrealty.am: ցուցակ ===")
    my = jina(sess, MY_LIST) or ""
    links = []
    for m in MY_RE.finditer(my):
        if m.group(0) not in links:
            links.append(m.group(0))
    print("հայտարարության հղումներ՝", len(links), links[:3])
    print("ՆՄՈՒՇ (900 նշան):")
    print(my[:900].replace("\n", " | "))

main()
