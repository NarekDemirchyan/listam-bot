# -*- coding: utf-8 -*-
# Ստուգիչ 3. Իրական նմուշները գրում է probe.txt-ի մեջ։
import re, time, requests
from fetcher import jina

BASE_LIST = "https://www.list.am"
EST_LIST  = "https://www.estate.am/ru/аренда-квартир-s4"
EST_RSS   = EST_LIST + ".rss"
MY_LIST   = "https://myrealty.am/ru"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

out = []
def add(title, text):
    out.append("\n##### " + title + " #####\n" + (text or ""))

def win(text, pattern, before=1400, after=400):
    m = re.search(pattern, text or "")
    if not m:
        return "ՉԳՏՎԵՑ"
    i = m.start()
    return text[max(0, i - before): i + after]

def main():
    sess = requests.Session()

    lst = jina(sess, BASE_LIST + "/ru/category/56") or ""
    add("LISTAM-ՑՈՒՑԱԿ", win(lst, r"/ru/item/\d+"))
    time.sleep(3)

    est = jina(sess, EST_LIST) or ""
    add("ESTATE-ՑՈՒՑԱԿ", win(est, r"https://www\.estate\.am/ru/[^\s\)\]\"]+-d\d+"))
    time.sleep(2)

    try:
        r = sess.get(EST_RSS, headers={"User-Agent": UA}, timeout=30)
        add("ESTATE-RSS", f"HTTP {r.status_code}, <item>={r.text.count('<item')}\n" + r.text[:1500])
    except Exception as e:
        add("ESTATE-RSS-ՍԽԱԼ", f"{type(e).__name__}: {e}")
    time.sleep(2)

    my = jina(sess, MY_LIST) or ""
    add("MYREALTY-ՑՈՒՑԱԿ", win(my, r"/ru/snyat-kvartiru/[^\s\)\]\"]+"))

    open("probe.txt", "w", encoding="utf-8").write("".join(out))

main()
