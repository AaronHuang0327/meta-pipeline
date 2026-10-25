#!/usr/bin/env python3
"""
adjudicate.py — 比對兩位「人類」審查者的篩選結果，挑出需要第三人裁決的；
                LLM 預篩結果（選用）只當品管旗標，不參與決定。

用法：
  python adjudicate.py screen_A.csv screen_B.csv --out screening_decisions.csv
  python adjudicate.py screen_A.csv screen_B.csv --llm screen_LLM.csv --out screening_decisions.csv

角色（教學重點）：
  * screen_A.csv  第一作者（人）  獨立看完每一筆
  * screen_B.csv  第二作者（人）  獨立看完每一筆，看不到 A 的結果
  * screen_LLM.csv（選用）LLM 預篩。用途有三，都不是「代替人」：
      1. 排序：LLM 判 include 的排前面，讓人先看最可能相關的
      2. 品管：兩位人類一致 exclude、但 LLM 高信心 include → 標 qa_flag，請人回頭再看一眼
      3. 投稿揭露：Methods 寫「LLM 作為預篩與品管工具，所有決定由兩位人類審查者獨立完成」

輸出欄位：
  id, A, conf_A, reason_A, B, conf_B, reason_B, agreement, LLM, conf_LLM, qa_flag,
  needs_third, final, final_by, final_reason
  * agreement = yes/no（A vs B）
  * needs_third = yes 當 A ≠ B → 第三人（通訊作者）填 final / final_by / final_reason
  * A = B 時 final 自動填入，final_by = "A+B"
  * 印出 Cohen's kappa（A vs B）當體檢數字
"""
import argparse
import csv
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


def read(path):
    if not path:
        return {}
    with open(path, encoding="utf-8") as f:
        return {r["id"].strip(): {k: (v or "").strip().lower() if k != "reason" else (v or "") for k, v in r.items()}
                for r in csv.DictReader(f)}


def kappa(pairs):
    n = len(pairs)
    if n == 0:
        return float("nan")
    agree = sum(a == b for a, b in pairs) / n
    pa = sum(a == "include" for a, _ in pairs) / n
    pb = sum(b == "include" for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (agree - pe) / (1 - pe) if pe != 1 else 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a", help="第一作者的篩選結果")
    ap.add_argument("b", help="第二作者的篩選結果")
    ap.add_argument("--llm", default=None, help="LLM 預篩結果（選用）")
    ap.add_argument("--out", default="screening_decisions.csv")
    ap.add_argument("--by", default="")
    args = ap.parse_args()

    require_station("03")
    A, B, L = read(args.a), read(args.b), read(args.llm)
    ids = sorted(set(A) | set(B))
    missing_a = [i for i in ids if i not in A]
    missing_b = [i for i in ids if i not in B]
    if missing_a or missing_b:
        sys.exit(f"✗ 兩位審查者必須各自看完每一筆。A 缺 {len(missing_a)} 筆、B 缺 {len(missing_b)} 筆。"
                 f"（例如 {(missing_a + missing_b)[:5]}）")

    rows, pairs, n_third, n_qa = [], [], 0, 0
    for i in ids:
        a, b, l = A[i], B[i], L.get(i, {})
        da, db, dl = a.get("decision", ""), b.get("decision", ""), l.get("decision", "")
        if da not in ("include", "exclude") or db not in ("include", "exclude"):
            sys.exit(f"✗ {i} 的 decision 必須是 include 或 exclude（A='{da}', B='{db}'）")
        agree = da == db
        pairs.append((da, db))
        qa = agree and da == "exclude" and dl == "include" and l.get("confidence") == "high"
        n_third += (not agree)
        n_qa += qa
        rows.append({
            "id": i, "A": da, "conf_A": a.get("confidence", ""), "reason_A": a.get("reason", ""),
            "B": db, "conf_B": b.get("confidence", ""), "reason_B": b.get("reason", ""),
            "agreement": "yes" if agree else "no",
            "LLM": dl, "conf_LLM": l.get("confidence", ""), "qa_flag": "yes" if qa else "",
            "needs_third": "" if agree else "yes",
            "final": da if agree else "", "final_by": "A+B" if agree else "", "final_reason": "兩位審查者一致" if agree else "",
        })

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    k = kappa(pairs)
    print(f"共 {len(ids)} 筆；A/B 一致 {len(ids) - n_third} 筆；需第三人裁決 {n_third} 筆")
    print(f"Cohen's kappa (A vs B) = {k:.2f}（> 0.6 算可以；但 kappa 高不等於對）")
    if L:
        print(f"LLM 品管旗標 {n_qa} 筆（兩人都排除、LLM 高信心納入）→ 請兩位回頭各看一眼，改變決定要寫理由。")
    print(f"請打開 {args.out}：needs_third = yes 的列由第三人填 final / final_by / final_reason。")
    log_event("03", "adjudicate.py", args={"a": args.a, "b": args.b, "llm": args.llm}, outputs=[args.out],
              note=f"kappa={k:.2f}，需裁決 {n_third}，QA 旗標 {n_qa}", by=args.by)


if __name__ == "__main__":
    main()
