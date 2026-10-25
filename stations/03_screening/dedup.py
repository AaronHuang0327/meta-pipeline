#!/usr/bin/env python3
"""
dedup.py — 合併多個資料庫的檢索結果並去重

用法：
  python dedup.py --out records_dedup.csv
  python dedup.py --inputs ../02_search/records_pubmed.csv ../02_search/records_embase.csv --out records_dedup.csv

教學重點：
  * 順序：先用 DOI（最可靠），再用「正規化標題 + 年份」。
  * 「正規化」= 全轉小寫、去掉標點與空白，所以 "Relative Motion Splinting:" 跟
    "relative motion splinting" 會被視為同一篇。
  * 任何一次比對成功，都把「新學到的 DOI / 標題鍵」回填到索引——
    例如第一筆沒 DOI、第二筆靠標題配上並帶有 DOI，那個 DOI 從此也能抓到第三筆。
  * 保留第一次出現的那份（通常 PubMed 放前面，摘要最完整），`sources` 欄記錄它出現在哪幾個庫。
  * 被判為重複的另存 duplicates_removed.csv 給你抽查。
"""
import argparse
import csv
import re
import sys
from pathlib import Path

_root = next((q for q in [Path(__file__).resolve(), *Path(__file__).resolve().parents] if (q / "gate.py").exists()), None)
if _root:
    sys.path.insert(0, str(_root))
try:
    from gate import require_station, log_event
except ImportError:
    def require_station(*a, **k): return None
    def log_event(*a, **k): return None

FIELDS = ["id", "sources", "pmid", "doi", "title", "abstract", "authors", "journal", "year", "pub_type"]


def norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="*")
    ap.add_argument("--out", default="records_dedup.csv")
    ap.add_argument("--by", default="")
    args = ap.parse_args()

    require_station("03")
    inputs = [Path(p) for p in args.inputs] if args.inputs else sorted((Path.cwd() / "../02_search").glob("records_*.csv"))
    if not inputs:
        sys.exit("找不到任何 records_*.csv。先完成第 2 站。")

    seen_doi, seen_title, kept, dups = {}, {}, [], []
    total = 0
    for path in inputs:
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                total += 1
                doi = (row.get("doi") or "").strip().lower()
                key_t = norm_title(row.get("title", "")) + "|" + (row.get("year") or "").strip()
                title_ok = len(key_t) > 20  # 太短的標題鍵不可信

                match = None
                if doi and doi in seen_doi:
                    match = seen_doi[doi]
                elif title_ok and key_t in seen_title:
                    match = seen_title[key_t]

                if match is not None:
                    kept[match]["sources"] += ";" + row.get("source", path.stem)
                    # 回填：這筆帶來的新鍵也指向同一篇
                    if doi and doi not in seen_doi:
                        seen_doi[doi] = match
                        if not kept[match]["doi"]:
                            kept[match]["doi"] = doi
                    if title_ok and key_t not in seen_title:
                        seen_title[key_t] = match
                    dups.append({**row, "duplicate_of": kept[match]["id"]})
                    continue

                idx = len(kept)
                rec = {k: row.get(k, "") for k in FIELDS if k not in ("id", "sources")}
                rec["id"] = f"R{idx + 1:04d}"
                rec["sources"] = row.get("source", path.stem)
                kept.append(rec)
                if doi:
                    seen_doi[doi] = idx
                if title_ok:
                    seen_title[key_t] = idx

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(kept)
    if dups:
        cols = []
        for d in dups:  # 各來源欄位可能不同，取聯集
            for k in d:
                if k not in cols:
                    cols.append(k)
        with open("duplicates_removed.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(dups)

    print(f"輸入 {len(inputs)} 個檔案，共 {total} 筆")
    print(f"去除重複 {len(dups)} 筆 → 剩 {len(kept)} 筆，存於 {args.out}")
    print("PRISMA 用數字：合併前 =", total, "；去重後 =", len(kept))
    if dups:
        print("請抽查 duplicates_removed.csv 確認沒有誤判。")
    log_event("03", "dedup.py", args={"inputs": [str(p) for p in inputs]}, outputs=[args.out],
              note=f"合併前 {total} → 去重後 {len(kept)}", by=args.by)


if __name__ == "__main__":
    main()
