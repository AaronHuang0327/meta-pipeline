#!/usr/bin/env python3
"""
pull_decisions.py — 把篩選 App 的 decisions 轉成 screen_A.csv / screen_B.csv

用法：
  python pull_decisions.py decisions.json --reviewers "學弟A" "學弟B" --stage ta \
      --records ../../projects/<題目>/03_screening/records_dedup.csv --outdir ../../projects/<題目>/03_screening/

decisions.json：Claude 用 ArtifactData list/query 讀出 decisions 集合後存成的 JSON
  （接受 [{...}, ...] 或 {"docs":[{"id":..,"data":{...}}]} 兩種形狀）

轉換規則：
  * decision = unsure → include，confidence 強制 low，reason 前綴「不確定：」
  * reason 欄取「排除理由 + 備註」
  * 會檢查每位審查者是否涵蓋 records_dedup.csv 的全部 id，缺的列出來
"""
import argparse
import csv
import json
from pathlib import Path


def load(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(d, dict) and "docs" in d:
        return [x.get("data", x) for x in d["docs"]]
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("decisions")
    ap.add_argument("--reviewers", nargs=2, required=True)
    ap.add_argument("--stage", default="ta")
    ap.add_argument("--records", required=True)
    ap.add_argument("--outdir", default=".")
    a = ap.parse_args()

    rows = [r for r in load(a.decisions) if r.get("stage", "ta") == a.stage]
    with open(a.records, encoding="utf-8") as f:
        all_ids = [r["id"] for r in csv.DictReader(f)]

    for letter, name in zip("AB", a.reviewers):
        mine = {r["record_id"]: r for r in rows if r.get("reviewer") == name}
        out = Path(a.outdir) / f"screen_{letter}.csv"
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["id", "decision", "confidence", "reason"])
            for i in all_ids:
                r = mine.get(i)
                if not r:
                    continue
                dec, conf, reason = r["decision"], r.get("confidence", ""), (r.get("reason") or "")
                if r.get("note"):
                    reason = (reason + " | " if reason else "") + r["note"]
                if dec == "unsure":
                    dec, conf, reason = "include", "low", "不確定：" + reason
                w.writerow([i, dec, conf, reason])
        missing = [i for i in all_ids if i not in mine]
        print(f"{name} → {out}：{len(mine)} 筆；缺 {len(missing)} 筆" + (f"（例如 {missing[:5]}）" if missing else ""))
    print("兩人都齊了再跑 adjudicate.py。")


if __name__ == "__main__":
    main()
