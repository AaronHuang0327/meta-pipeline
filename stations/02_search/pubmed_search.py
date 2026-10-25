#!/usr/bin/env python3
"""
pubmed_search.py — 用 NCBI E-utilities 跑 PubMed 檢索並匯出 CSV

用法：
  python pubmed_search.py --query '("extensor tendon"[tiab]) AND ("relative motion"[tiab])' --out records_pubmed.csv
  python pubmed_search.py --query-file query.txt --out records_pubmed.csv --email you@example.com

教學重點：
  * 分兩步，跟你在 PubMed 網頁上做的事一樣：
      esearch  → 把語法丟過去，拿回「總筆數」與一個 history 鑰匙（WebEnv + QueryKey）
      efetch   → 拿鑰匙分批（每批 200）要詳細資料，直到拿滿總筆數
  * NCBI 限制：一次 ESearch 最多只能取回 10,000 筆（2022 年起，history 也一樣）。
    超過時本程式會自動依「發表日期」把查詢切段（先對半切年份，再切月、日），
    每段都 ≤ 10,000 再逐段下載，最後把 PMID 聯集起來，與整體總筆數核對。
    這是 NCBI 官方建議的做法之一（另一個是 EDirect）。
  * 抓完會核對「總筆數 == 實際拿到筆數」，對不上就中止並警告——檢索不完整是 SR 的致命傷。
  * NCBI 要求帶 email；有 API key 速率更高（每秒 10 次 vs 3 次）。
  * 本沙盒無法連 NCBI，分段邏輯已用離線模擬測過（見 test_pubmed_split.py）；第一次正式使用請留意印出的「回報／取得」筆數。

輸出欄位（所有資料庫共用）：
  source, pmid, doi, title, abstract, authors, journal, year, pub_type
"""
import argparse
import csv
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

# --- 接上閘門與留痕（找不到 gate.py 時安靜略過，讓腳本也能獨立使用） ---
_root = next((q for q in [Path(__file__).resolve(), *Path(__file__).resolve().parents] if (q / "gate.py").exists()), None)
if _root:
    sys.path.insert(0, str(_root))
try:
    from gate import require_station, log_event
except ImportError:  # 腳本被單獨複製走時
    def require_station(*a, **k): return None
    def log_event(*a, **k): return None

try:
    import requests
except ImportError:
    sys.exit("請先安裝 requests：pip install requests")

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
FIELDS = ["source", "pmid", "doi", "title", "abstract", "authors", "journal", "year", "pub_type"]
BATCH = 200
ESEARCH_CAP = 10000  # NCBI：單一 ESearch 結果集最多可取回 10,000 筆


def esearch(query: str, email: str, api_key: str | None, mindate: str | None = None, maxdate: str | None = None):
    """第一步：拿總筆數與 history 鑰匙。mindate/maxdate 以發表日期（pdat）切段，格式 YYYY/MM/DD。"""
    params = {"db": "pubmed", "term": query, "usehistory": "y", "retmax": 0, "retmode": "json", "email": email}
    if mindate and maxdate:
        params.update({"datetype": "pdat", "mindate": mindate, "maxdate": maxdate})
    if api_key:
        params["api_key"] = api_key
    r = requests.get(BASE + "esearch.fcgi", params=params, timeout=60)
    r.raise_for_status()
    d = r.json()["esearchresult"]
    return int(d["count"]), d.get("webenv", ""), d.get("querykey", "")


def _split_range(lo: str, hi: str):
    """把 YYYY/MM/DD 區間對半切；回傳兩段，或 None（已不能再切）。"""
    from datetime import date, timedelta
    a = date(*map(int, lo.split("/"))); b = date(*map(int, hi.split("/")))
    if a >= b:
        return None
    mid = a + (b - a) // 2
    return (lo, mid.strftime("%Y/%m/%d")), ((mid + timedelta(days=1)).strftime("%Y/%m/%d"), hi)


def collect_segments(query, email, api_key, lo="1800/01/01", hi=None, depth=0):
    """遞迴：每段 ≤ 10,000 才下載；否則切半。回傳 rows 清單。"""
    from datetime import date
    hi = hi or date.today().strftime("%Y/%m/%d")
    count, webenv, qk = esearch(query, email, api_key, lo, hi)
    pad = "  " * depth
    if count == 0:
        return []
    if count <= ESEARCH_CAP:
        print(f"{pad}段 {lo}–{hi}：{count} 筆")
        return efetch_all(count, webenv, qk, email, api_key, quiet=depth > 0)
    halves = _split_range(lo, hi)
    if halves is None:
        sys.exit(f"✗ 單日 {lo} 就有 {count} 筆（> {ESEARCH_CAP}），無法再切。請縮小語法或改用 EDirect。")
    print(f"{pad}段 {lo}–{hi}：{count} 筆 > {ESEARCH_CAP}，切半")
    return collect_segments(query, email, api_key, *halves[0], depth + 1) + collect_segments(query, email, api_key, *halves[1], depth + 1)


def efetch_all(count: int, webenv: str, qk: str, email: str, api_key: str | None, quiet: bool = False) -> list[dict]:
    """第二步：用 retstart 分頁，直到拿滿 count（count 必須 ≤ 10,000）。"""
    rows = []
    for start in range(0, count, BATCH):
        params = {"db": "pubmed", "query_key": qk, "WebEnv": webenv, "retstart": start, "retmax": BATCH,
                  "retmode": "xml", "email": email}
        if api_key:
            params["api_key"] = api_key
        for attempt in range(3):  # NCBI 偶爾會 5xx，重試三次
            try:
                r = requests.post(BASE + "efetch.fcgi", data=params, timeout=120)
                r.raise_for_status()
                break
            except requests.RequestException as e:
                if attempt == 2:
                    raise
                print(f"  重試（{e}）"); time.sleep(2)
        root = ET.fromstring(r.text)
        for art in root.findall(".//PubmedArticle"):
            rows.append(parse_article(art))
        if not quiet or start + BATCH >= count:
            print(f"  已下載 {min(start + BATCH, count)}/{count}")
        time.sleep(0.11 if api_key else 0.34)
    return rows


def parse_article(art) -> dict:
    def text(path):
        el = art.find(path)
        return (el.text or "").strip() if el is not None else ""
    pmid = text(".//PMID")
    t = art.find(".//ArticleTitle")
    title = "".join(t.itertext()).strip() if t is not None else ""
    abstract = " ".join("".join(a.itertext()).strip() for a in art.findall(".//AbstractText"))
    authors = "; ".join(f"{a.findtext('LastName', '')} {a.findtext('Initials', '')}".strip()
                        for a in art.findall(".//Author") if a.find("LastName") is not None)
    journal = text(".//Journal/Title")
    year = text(".//PubDate/Year") or text(".//PubDate/MedlineDate")[:4]
    doi = next(((aid.text or "").strip().lower() for aid in art.findall(".//ArticleId") if aid.get("IdType") == "doi"), "")
    pub_type = "; ".join(pt.text or "" for pt in art.findall(".//PublicationType"))
    return {"source": "pubmed", "pmid": pmid, "doi": doi, "title": title, "abstract": abstract,
            "authors": authors, "journal": journal, "year": year, "pub_type": pub_type}


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--query")
    g.add_argument("--query-file")
    ap.add_argument("--out", default="records_pubmed.csv")
    ap.add_argument("--email", default="meta-pipeline@example.com")
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--by", default="", help="操作者名字，寫進留痕")
    args = ap.parse_args()

    require_station("02")
    query = args.query or " ".join(Path(args.query_file).read_text(encoding="utf-8").split())
    print(f"語法：{query}\n")

    count, webenv, qk = esearch(query, args.email, args.api_key)
    print(f"PubMed 回報總筆數：{count}")
    if count == 0:
        sys.exit("零筆。檢查語法：MeSH 詞拼錯？AND/OR 用反？")
    if count <= ESEARCH_CAP:
        rows = efetch_all(count, webenv, qk, args.email, args.api_key)
    else:
        print(f"超過 NCBI 單次上限 {ESEARCH_CAP}，改依發表日期分段下載：")
        rows = collect_segments(query, args.email, args.api_key)
    # 分段可能重複抓到同一篇（日期邊界），以 PMID 去重
    seen, uniq_rows = set(), []
    for r in rows:
        if r["pmid"] and r["pmid"] in seen:
            continue
        seen.add(r["pmid"]); uniq_rows.append(r)
    rows = uniq_rows

    # 核對完整性：拿到的要等於整體回報的（允許 NCBI 偶發的極少數缺漏，但要明講）
    got = len(rows)
    if got < count:
        gap = count - got
        if gap > max(5, count * 0.001):
            sys.exit(f"✗ 檢索不完整：PubMed 回報 {count} 筆，只取得 {got} 筆（缺 {gap}）。未寫出檔案。"
                     f"常見原因：有些紀錄沒有發表日期而未落入任何日期段。請縮小語法分次跑，或改用 EDirect。")
        print(f"⚠ PubMed 回報 {count} 筆，取得 {got} 筆（缺 {gap}，可能是 NCBI 端已刪除的紀錄）。請在 search_strategy.md 註明。")
    elif got > count:
        print(f"⚠ 取得 {got} 筆多於回報 {count} 筆（分段期間 NCBI 新增了紀錄），以取得者為準。")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    print(f"\n已匯出 {got} 筆 → {args.out}")
    print("請把檢索日期與筆數填進 search_strategy.md。")
    log_event("02", "pubmed_search.py", args={"query": query, "email": args.email},
              outputs=[args.out], note=f"PubMed 回報 {count}，取得 {got}", by=args.by)


if __name__ == "__main__":
    main()
