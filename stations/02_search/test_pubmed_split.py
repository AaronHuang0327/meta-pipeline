#!/usr/bin/env python3
"""
test_pubmed_split.py — 離線模擬 NCBI，驗證「超過 10,000 筆時依日期分段」的邏輯

跑法：python test_pubmed_split.py
模擬一個有 25,000 筆、發表日期分布在 1990–2025 的查詢，確認：
  1. 每一段 esearch 回報都 ≤ 10,000 才呼叫 efetch
  2. 聯集後 PMID 數 == 整體總數
"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pubmed_search as ps

# ---- 假資料庫：25,000 篇，日期集中在某幾年以逼出多層切分 ----
random.seed(7)
N = 25000
start = date(1990, 1, 1)
DB = {}
for i in range(N):
    # 故意讓 2018–2020 很密集
    if random.random() < 0.6:
        d = date(2018, 1, 1) + timedelta(days=random.randint(0, 3 * 365))
    else:
        d = start + timedelta(days=random.randint(0, 35 * 365))
    DB[str(100000 + i)] = d

calls = {"esearch": 0, "efetch": 0, "max_count_fetched": 0}


def fake_esearch(query, email, api_key, mindate=None, maxdate=None):
    calls["esearch"] += 1
    if mindate and maxdate:
        lo = date(*map(int, mindate.split("/"))); hi = date(*map(int, maxdate.split("/")))
        ids = [p for p, d in DB.items() if lo <= d <= hi]
    else:
        ids = list(DB)
    key = "|".join(sorted(ids))
    return len(ids), key, "1"


def fake_efetch_all(count, webenv, qk, email, api_key, quiet=False):
    calls["efetch"] += 1
    assert count <= ps.ESEARCH_CAP, f"efetch 被要求抓 {count} 筆，超過上限"
    calls["max_count_fetched"] = max(calls["max_count_fetched"], count)
    ids = webenv.split("|") if webenv else []
    return [{"pmid": p} for p in ids]


ps.esearch = fake_esearch
ps.efetch_all = fake_efetch_all

total, _, _ = ps.esearch("q", "e", None)
rows = ps.collect_segments("q", "e", None, hi="2025/12/31")
uniq = {r["pmid"] for r in rows}
print(f"總筆數 {total}；分段後取得 {len(rows)} 列、去重 {len(uniq)} 篇；esearch {calls['esearch']} 次、efetch {calls['efetch']} 次、單段最大 {calls['max_count_fetched']}")
assert len(uniq) == total, "聯集後筆數與總數不符"
assert calls["max_count_fetched"] <= ps.ESEARCH_CAP
print("PASS")
