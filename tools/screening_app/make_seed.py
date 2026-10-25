#!/usr/bin/env python3
"""
make_seed.py — 把去重後的紀錄轉成篩選 App 的灌檔（給 Claude 用 ArtifactData batch 寫入）

用法：
  python make_seed.py --records ../../projects/<題目>/03_screening/records_dedup.csv \
      --project "RME after extensor repair" --reviewers "學弟A" "學弟B" \
      --pico ../../projects/<題目>/01_protocol/pico.md \
      [--llm ../../projects/<題目>/03_screening/screen_LLM.csv] [--stage ta] \
      --out seed.json

產出 seed.json：
  {"config": {...}, "records": [{"id":..., "order":..., "title":..., ...}, ...]}
  * order：若有 LLM 預篩，include 排前面、exclude 排後面（同組內保留原順序），
    這樣審查者先看最可能相關的；但 LLM 的判定與理由不會進 App。
  * stage：ta = 標題摘要篩選；ft = 全文資格判定（同一個 App，換 stage 就是第 4 站）
"""
import argparse
import csv
import json
from pathlib import Path

REASONS_TA = ["wrong_population 錯族群", "wrong_intervention 錯介入", "wrong_comparator 錯對照",
              "wrong_design 錯設計（病例報告／回顧文章）", "not_primary 非原始研究", "language 語言不符",
              "duplicate 重複發表", "other 其他（請寫備註）"]
REASONS_FT = ["wrong_population 錯族群", "wrong_intervention 錯介入", "wrong_comparator 錯對照",
              "wrong_outcome 沒報告任何我們要的 outcome", "wrong_design 錯設計", "duplicate_data 同一批病人已在另一篇報告",
              "no_fulltext 取不到全文", "language 語言不符"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--reviewers", nargs=2, required=True, metavar=("A", "B"))
    ap.add_argument("--pico", default=None, help="pico.md，內容會顯示在 App 的「納入條件」折疊區")
    ap.add_argument("--llm", default=None, help="screen_LLM.csv，只用來排序")
    ap.add_argument("--stage", default="ta", choices=["ta", "ft"])
    ap.add_argument("--out", default="seed.json")
    a = ap.parse_args()

    with open(a.records, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    llm = {}
    if a.llm:
        with open(a.llm, encoding="utf-8") as f:
            llm = {r["id"].strip(): r["decision"].strip().lower() for r in csv.DictReader(f)}
    rank = {"include": 0, "": 1, "exclude": 2}
    rows.sort(key=lambda r: (rank.get(llm.get(r["id"], ""), 1)))
    records = []
    for i, r in enumerate(rows):
        records.append({"id": r["id"], "order": i + 1, "title": r.get("title", ""), "abstract": r.get("abstract", ""),
                        "authors": r.get("authors", ""), "journal": r.get("journal", ""), "year": r.get("year", ""),
                        "doi": r.get("doi", ""), "pmid": r.get("pmid", "")})
    config = {"project": a.project, "stage": a.stage, "reviewers": a.reviewers,
              "reasons": REASONS_FT if a.stage == "ft" else REASONS_TA,
              "pico": Path(a.pico).read_text(encoding="utf-8") if a.pico else ""}
    Path(a.out).write_text(json.dumps({"config": config, "records": records}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(records)} 筆 → {a.out}（LLM 排序：{'有' if llm else '無'}）")
    print("下一步：請 Claude 用 ArtifactData batch 把 config 寫到 config/main、records 逐筆寫到 records/<id>。")


if __name__ == "__main__":
    main()
