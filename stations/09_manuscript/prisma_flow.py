#!/usr/bin/env python3
"""
prisma_flow.py — 產生 PRISMA 2020 流程圖（SVG），並驗算數字

用法：
  python prisma_flow.py --db "PubMed=412" --db "Embase=388" --other 6 \
      --dedup 523 --screened-out 471 --fulltext 52 \
      --excl "wrong_population=12" --excl "wrong_design=9" --included 9 --out prisma_flow.svg

驗算規則（對不上就不出圖）：
  * Σ資料庫 + 其他來源 − 去重後 = 去除的重複數（必須 ≥ 0）
  * 去重後 − 初篩排除 = 全文評估篇數
  * 全文評估 − Σ各理由排除 = 納入篇數

教學重點：流程圖的每個數字審稿人都會加減看一遍。對不上，整篇可信度歸零。
"""
import argparse
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


def kv(items):
    out = []
    for s in items or []:
        k, v = s.split("=")
        out.append((k.strip(), int(v)))
    return out


def box(x, y, w, h, lines, fill="#fff"):
    svg = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="#333" stroke-width="1.2"/>']
    ly = y + 20
    for i, line in enumerate(lines):
        weight = "bold" if i == 0 else "normal"
        svg.append(f'<text x="{x + 12}" y="{ly}" font-family="Helvetica, Arial, sans-serif" font-size="13" font-weight="{weight}">{line}</text>')
        ly += 18
    return "\n".join(svg)


def arrow(x1, y1, x2, y2):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#333" stroke-width="1.2" marker-end="url(#a)"/>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", action="append", help="資料庫=筆數，可重複")
    ap.add_argument("--other", type=int, default=0, help="其他來源（參考文獻、登錄等）筆數")
    ap.add_argument("--dedup", type=int, required=True, help="去重後筆數")
    ap.add_argument("--screened-out", type=int, required=True, help="標題摘要排除筆數")
    ap.add_argument("--not-retrieved", type=int, default=0, help="找不到全文的筆數")
    ap.add_argument("--fulltext", type=int, required=True, help="全文評估篇數")
    ap.add_argument("--excl", action="append", help="排除理由=篇數，可重複")
    ap.add_argument("--included", type=int, required=True)
    ap.add_argument("--out", default="prisma_flow.svg")
    ap.add_argument("--by", default="")
    args = ap.parse_args()

    require_station("09")
    dbs, excls = kv(args.db), kv(args.excl)
    total = sum(v for _, v in dbs) + args.other
    dup = total - args.dedup
    errors = []
    if dup < 0:
        errors.append(f"去重後 ({args.dedup}) 比合併前 ({total}) 還多")
    if args.dedup - args.screened_out - args.not_retrieved != args.fulltext:
        errors.append(f"去重後 {args.dedup} − 初篩排除 {args.screened_out} − 未取得 {args.not_retrieved} ≠ 全文 {args.fulltext}")
    if args.fulltext - sum(v for _, v in excls) != args.included:
        errors.append(f"全文 {args.fulltext} − 排除 {sum(v for _, v in excls)} ≠ 納入 {args.included}")
    if errors:
        print("數字對不上，請回去各站核對：")
        for e in errors:
            print("  ✗", e)
        sys.exit(1)

    W, H = 760, 620
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         '<defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#333"/></marker></defs>',
         f'<rect width="{W}" height="{H}" fill="#fff"/>']
    # 左欄：識別 → 篩選 → 納入
    id_lines = ["Records identified from:"] + [f"  {k} (n = {v})" for k, v in dbs]
    if args.other:
        id_lines.append(f"  Other sources (n = {args.other})")
    s.append(box(40, 30, 320, 24 + 18 * len(id_lines), id_lines, "#fff7e6"))
    s.append(box(420, 30, 300, 60, ["Records removed before screening:", f"  Duplicates removed (n = {dup})"]))
    y1 = 30 + 24 + 18 * len(id_lines)
    s.append(arrow(200, y1, 200, 170)); s.append(arrow(360, 60, 420, 60))

    s.append(box(40, 170, 320, 60, ["Records screened", f"(n = {args.dedup})"], "#fff7e6"))
    s.append(box(420, 170, 300, 60, ["Records excluded", f"(n = {args.screened_out})"]))
    s.append(arrow(360, 200, 420, 200)); s.append(arrow(200, 230, 200, 290))

    s.append(box(40, 290, 320, 60, ["Reports sought for retrieval", f"(n = {args.dedup - args.screened_out})"], "#fff7e6"))
    s.append(box(420, 290, 300, 60, ["Reports not retrieved", f"(n = {args.not_retrieved})"]))
    s.append(arrow(360, 320, 420, 320)); s.append(arrow(200, 350, 200, 410))

    s.append(box(40, 410, 320, 60, ["Reports assessed for eligibility", f"(n = {args.fulltext})"], "#fff7e6"))
    ex_lines = ["Reports excluded:"] + [f"  {k} (n = {v})" for k, v in excls]
    s.append(box(420, 410, 300, 24 + 18 * len(ex_lines), ex_lines))
    s.append(arrow(360, 440, 420, 440)); s.append(arrow(200, 470, 200, 530))

    s.append(box(40, 530, 320, 60, ["Studies included in review", f"(n = {args.included})"], "#e6f4ea"))
    s.append("</svg>")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(s))
    print(f"驗算通過。合併前 {total} → 去重 {dup} → 篩選 {args.dedup} → 全文 {args.fulltext} → 納入 {args.included}")
    print(f"已輸出 {args.out}（PRISMA 2020 格式；投稿時可轉成 PNG/PDF）")
    log_event("09", "prisma_flow.py", args={"db": args.db, "other": args.other, "dedup": args.dedup, "screened_out": args.screened_out,
                                             "fulltext": args.fulltext, "excl": args.excl, "included": args.included},
              outputs=[args.out], note=f"合併前 {total} → 納入 {args.included}", by=args.by)


if __name__ == "__main__":
    main()
