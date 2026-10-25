#!/usr/bin/env python3
"""
gate.py — 生產線的閘門管理員 + 留痕中心

子命令：
  new <題目>                     開新題目，複製九站模板
  status <題目>                  看單一題目九站狀態（含「簽核後輸出被改過」警告）
  next <題目>                    印出下一個該做的動作（給人、也給 Claude）
  board                          所有題目的看板：一眼看到每條線走到哪
  approve <題目> <站> --by --note 蓋章（檢查順序、必要輸出、輸出不是空模板；記錄輸出 sha256）
  reopen  <題目> <站> --by --note 撤章（該站與下游全部打回）
  log <題目> <站> --by --note     手動補一筆事件（例如「寄信問作者」）
  events <題目>                  列出全部事件紀錄

留痕的設計（教學重點）：
  * manifest.json 有兩層紀錄：
      stations[站].log  — 蓋章 / 撤章，誰、何時、備註、當時輸出檔的 sha256
      events[]          — 每支腳本跑完都自動 append 一筆：哪支腳本、參數、產出檔與 sha256、幾列
  * 蓋章時記下輸出檔的 sha256；之後若檔案被改動，status 會標 ⚠ 並要求重新簽核。
    這就是審計軌跡（audit trail）：投稿時「兩位審查者獨立…」有紀錄可對。
  * 各站腳本透過 require_station() 檢查前一站已簽核，透過 log_event() 自動留痕。

給腳本用的 API（各站腳本已內建呼叫）：
    from gate import require_station, log_event
    require_station("03")     # 第 3 站腳本：確認第 2 站已簽核，否則停止
    log_event("03", "dedup.py", args=vars(args), outputs=["records_dedup.csv"], note="去重 523→340")
"""
import argparse
import glob
import hashlib
import json
import random
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIONS_DIR = ROOT / "stations"
PROJECTS_DIR = ROOT / "projects"

# (代號, 名稱, 蓋章前必須存在且非空模板的輸出檔；支援 glob)
STATIONS = [
    ("01", "題目與計畫書",   ["pico.md", "protocol.md"]),
    ("02", "檢索策略",       ["search_strategy.md", "records_*.csv"]),
    ("03", "去重與初篩",     ["records_dedup.csv", "screen_A.csv", "screen_B.csv", "screening_decisions.csv"]),
    ("04", "全文與資格",     ["eligibility.csv"]),
    ("05", "資料擷取",       ["extraction.csv", "extraction_outcomes.csv"]),
    ("06", "偏倚風險",       ["rob.csv"]),
    ("07", "統計分析",       ["results/summary.txt", "results/interpretation.md"]),
    ("08", "GRADE",          ["grade_sof.csv"]),
    ("09", "稿件",           ["manuscript.md", "prisma_flow.svg"]),
]
STATION_INDEX = {code: i for i, (code, _, _) in enumerate(STATIONS)}

STAMP_LINES = [
    "離 impact factor 又近了一站。",
    "這一站的苦工，審稿人永遠看不到，但他們看得到你沒做。",
    "資料不會說謊，但會沉默；你剛剛讓它開口了。",
    "好的 meta-analysis 不是把數字加起來，是把判斷寫下來。",
    "今天的閘門，明天的 Methods 段落。",
    "Cochrane 之神在看，祂點了頭。",
    "你剛剛做的事，叫做 reproducibility。",
    "蓋章的手不抖，森林圖才不會歪。",
    "每一次簽核，都是在替未來的自己省一次 revision。",
]
STAMP = """
   ┌──────────────┐
   │   APPROVED   │
   │   STATION {code} │
   └──────────────┘
"""


# ---------- 基礎工具 ----------

def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def folder_name(code: str) -> str:
    for p in sorted(STATIONS_DIR.iterdir()):
        if p.is_dir() and p.name.startswith(code + "_"):
            return p.name
    raise FileNotFoundError(f"找不到第 {code} 站的模板資料夾")


def project_path(name: str) -> Path:
    p = PROJECTS_DIR / name
    if not p.exists():
        sys.exit(f"找不到題目 {name}。先執行：python gate.py new {name}")
    return p


def load_manifest(proj: Path) -> dict:
    m = json.loads((proj / "manifest.json").read_text(encoding="utf-8"))
    m.setdefault("events", [])
    return m


def save_manifest(proj: Path, m: dict) -> None:
    (proj / "manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")


def find_project_from_cwd(start: Path | None = None):
    """從目前工作目錄往上找 manifest.json，回傳 (project_dir, manifest) 或 (None, None)。"""
    p = (start or Path.cwd()).resolve()
    for q in [p, *p.parents]:
        if (q / "manifest.json").exists() and (q.parent == PROJECTS_DIR.resolve()):
            return q, load_manifest(q)
    return None, None


def resolve_outputs(folder: Path, patterns: list[str]) -> tuple[list[Path], list[str]]:
    """展開 glob；回傳 (找到的檔案, 缺少的 pattern)。"""
    found, missing = [], []
    for pat in patterns:
        hits = [Path(h) for h in glob.glob(str(folder / pat))]
        if hits:
            found.extend(sorted(hits))
        else:
            missing.append(pat)
    return found, missing


def template_hashes(code: str) -> set[str]:
    """該站模板資料夾所有檔案的 sha256，用來偵測「輸出就是原封不動的模板」。"""
    return {sha256(p) for p in (STATIONS_DIR / folder_name(code)).rglob("*") if p.is_file()}


# ---------- 給各站腳本用的 API ----------

def require_station(code: str, strict: bool = True):
    """
    第 N 站的腳本呼叫 require_station("N")：
      * 若在題目工作區內：第 N-1 站必須已簽核，否則停止。
      * 若不在工作區（例如在 stations/ 跑 demo）：印警告後放行。
    """
    proj, m = find_project_from_cwd()
    if proj is None:
        if strict:
            print("⚠ 不在任何題目的工作區內（找不到 manifest.json），跳過閘門檢查。正式作業請在 projects/<題目>/ 底下執行。")
        return None
    idx = STATION_INDEX[code]
    if idx > 0:
        prev = STATIONS[idx - 1][0]
        if m["stations"][prev]["status"] != "approved":
            sys.exit(f"✗ 第 {prev} 站尚未簽核，第 {code} 站不能開工。先完成：python gate.py approve {proj.name} {prev}")
    return proj


def log_event(code: str, script: str, args: dict | None = None, outputs: list[str] | None = None,
              note: str = "", by: str = "") -> None:
    """腳本跑完自動留痕。不在工作區時安靜略過。"""
    proj, m = find_project_from_cwd()
    if proj is None:
        return
    outs = []
    for o in outputs or []:
        p = Path(o)
        if p.exists():
            rows = None
            if p.suffix.lower() == ".csv":
                try:
                    rows = sum(1 for _ in open(p, encoding="utf-8")) - 1
                except Exception:
                    rows = None
            rp = p.resolve()
            rel = str(rp.relative_to(proj)) if proj in rp.parents else str(p)
            outs.append({"file": rel, "sha256": sha256(p), "rows": rows})
    m["events"].append({"time": now(), "station": code, "script": script, "by": by,
                        "args": {k: v for k, v in (args or {}).items() if v is not None},
                        "outputs": outs, "note": note})
    save_manifest(proj, m)
    print(f"📝 已記錄事件到 manifest.json（第 {code} 站 · {script}）")


# ---------- 子命令 ----------

def cmd_new(args):
    dest = PROJECTS_DIR / args.name
    if dest.exists():
        sys.exit(f"題目 {args.name} 已存在。")
    dest.mkdir(parents=True)
    for code, _, _ in STATIONS:
        src = STATIONS_DIR / folder_name(code)
        shutil.copytree(src, dest / src.name)
    save_manifest(dest, {
        "project": args.name, "created": now(),
        "stations": {code: {"status": "pending", "log": []} for code, _, _ in STATIONS},
        "events": [{"time": now(), "station": "00", "script": "gate.py new", "by": args.by, "args": {}, "outputs": [], "note": "開新題目"}],
    })
    print(f"已建立題目：{dest}")
    print(f"下一步：python gate.py next {args.name}")


def station_state(proj: Path, m: dict, code: str):
    """回傳 (符號, 說明)。"""
    _, name, outputs = STATIONS[STATION_INDEX[code]]
    st = m["stations"][code]
    folder = proj / folder_name(code)
    found, missing = resolve_outputs(folder, outputs)
    if st["status"] == "approved":
        last = next((e for e in reversed(st["log"]) if e["action"] == "approve"), None)
        changed = []
        for f in found:
            rel = str(f.relative_to(folder))
            if last and rel in last.get("hashes", {}) and last["hashes"][rel] != sha256(f):
                changed.append(rel)
        if changed or missing:
            return "⚠", f"已簽核但輸出被改動/缺檔（{', '.join(changed + missing)}）→ 請 reopen 後重新簽核"
        return "✓", f"已簽核 {last['time']} by {last['by']}"
    if not missing:
        return "●", "輸出齊全，等你檢查後蓋章"
    if found:
        return "◐", f"部分輸出（缺 {', '.join(missing)}）"
    return "○", "未開工"


def cmd_status(args):
    proj = project_path(args.name)
    m = load_manifest(proj)
    print(f"\n題目：{m['project']}（建立於 {m['created']}；事件 {len(m['events'])} 筆）\n")
    for code, name, _ in STATIONS:
        mark, note = station_state(proj, m, code)
        print(f"  {mark} {code} {name:<8} {note}")
    print("\n圖例：✓ 已簽核  ● 待簽核  ◐ 進行中  ○ 未開工  ⚠ 簽核後被改動\n")


def cmd_next(args):
    proj = project_path(args.name)
    m = load_manifest(proj)
    for code, name, outputs in STATIONS:
        mark, note = station_state(proj, m, code)
        if mark == "✓":
            continue
        folder = folder_name(code)
        if mark == "⚠":
            print(f"第 {code} 站「{name}」簽核後輸出被改動：python gate.py reopen {args.name} {code} 再重新檢查簽核。")
        elif mark == "●":
            print(f"第 {code} 站「{name}」輸出齊全 → 請檢查後：python gate.py approve {args.name} {code} --by <你>")
        else:
            print(f"下一站：第 {code} 站「{name}」→ 讀 {folder}/README.md，產出 {', '.join(outputs)}")
        return
    print("九站全部通過。投稿去吧。")


def cmd_board(args):
    projs = sorted(p for p in PROJECTS_DIR.iterdir() if p.is_dir() and (p / "manifest.json").exists())
    if not projs:
        print("還沒有任何題目。python gate.py new <題目>")
        return
    head = "題目".ljust(22) + " ".join(c for c, _, _ in STATIONS) + "  下一步"
    print("\n" + head)
    print("-" * len(head))
    for p in projs:
        m = load_manifest(p)
        marks = [station_state(p, m, c)[0] for c, _, _ in STATIONS]
        nxt = next((f"{c} {n}" for (c, n, _), mk in zip(STATIONS, marks) if mk != "✓"), "投稿")
        print(p.name[:21].ljust(22) + "  ".join(marks) + "   " + nxt)
    print("\n✓ 已簽核  ● 待簽核  ◐ 進行中  ○ 未開工  ⚠ 被改動\n")


def cmd_approve(args):
    proj = project_path(args.name)
    m = load_manifest(proj)
    code = args.station.zfill(2)
    if code not in STATION_INDEX:
        sys.exit(f"沒有第 {code} 站。")
    idx = STATION_INDEX[code]
    _, name, outputs = STATIONS[idx]

    if idx > 0:
        prev = STATIONS[idx - 1][0]
        if m["stations"][prev]["status"] != "approved":
            sys.exit(f"第 {prev} 站還沒簽核，不能跳站。生產線的意義就是不跳站。")

    folder = proj / folder_name(code)
    found, missing = resolve_outputs(folder, outputs)
    if missing:
        sys.exit(f"第 {code} 站缺少輸出檔：{', '.join(missing)}。做完再來蓋章。")
    tmpl = template_hashes(code)
    bad = [str(f.relative_to(folder)) for f in found if f.stat().st_size == 0 or sha256(f) in tmpl]
    if bad:
        sys.exit(f"第 {code} 站這些輸出是空檔或原封不動的模板：{', '.join(bad)}。填完再蓋章。")
    if not args.by or args.by == "reviewer":
        sys.exit("請用 --by 寫上你的名字；審計軌跡要有人名。")

    entry = {"action": "approve", "time": now(), "by": args.by, "note": args.note or "",
             "hashes": {str(f.relative_to(folder)): sha256(f) for f in found}}
    m["stations"][code]["status"] = "approved"
    m["stations"][code]["log"].append(entry)
    m["events"].append({"time": entry["time"], "station": code, "script": "gate.py approve", "by": args.by,
                        "args": {}, "outputs": [{"file": k, "sha256": v} for k, v in entry["hashes"].items()], "note": args.note or ""})
    save_manifest(proj, m)

    print(STAMP.format(code=code))
    print(f"第 {code} 站「{name}」已簽核。{random.choice(STAMP_LINES)}")
    if idx + 1 < len(STATIONS):
        nxt = STATIONS[idx + 1]
        print(f"下一站：{nxt[0]} {nxt[1]} → 請看 {folder_name(nxt[0])}/README.md")
    else:
        print("九站全部通過。投稿去吧。")


def cmd_reopen(args):
    proj = project_path(args.name)
    m = load_manifest(proj)
    code = args.station.zfill(2)
    idx = STATION_INDEX[code]
    for c, _, _ in STATIONS[idx:]:
        if m["stations"][c]["status"] == "approved":
            m["stations"][c]["status"] = "pending"
            m["stations"][c]["log"].append({"action": "reopen", "time": now(), "by": args.by, "note": args.note or ""})
    m["events"].append({"time": now(), "station": code, "script": "gate.py reopen", "by": args.by, "args": {}, "outputs": [], "note": args.note or ""})
    save_manifest(proj, m)
    print(f"第 {code} 站及其之後所有站已重開。上游改了，下游一定要重跑——這不是懲罰，是誠實。")


def cmd_log(args):
    proj = project_path(args.name)
    m = load_manifest(proj)
    m["events"].append({"time": now(), "station": args.station.zfill(2), "script": "manual", "by": args.by, "args": {}, "outputs": [], "note": args.note})
    save_manifest(proj, m)
    print("已記錄。")


def cmd_events(args):
    proj = project_path(args.name)
    m = load_manifest(proj)
    for e in m["events"]:
        outs = ", ".join(f"{o['file']}" + (f"({o['rows']} 列)" if o.get("rows") is not None else "") for o in e.get("outputs", []))
        print(f"{e['time']}  [{e['station']}] {e['script']:<22} {e.get('by', ''):<8} {e.get('note', '')}  {outs}")


def main():
    ap = argparse.ArgumentParser(description="Meta-analysis 生產線閘門")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new"); p.add_argument("name"); p.add_argument("--by", default=""); p.set_defaults(fn=cmd_new)
    p = sub.add_parser("status"); p.add_argument("name"); p.set_defaults(fn=cmd_status)
    p = sub.add_parser("next"); p.add_argument("name"); p.set_defaults(fn=cmd_next)
    p = sub.add_parser("board"); p.set_defaults(fn=cmd_board)
    p = sub.add_parser("events"); p.add_argument("name"); p.set_defaults(fn=cmd_events)
    for c, fn in (("approve", cmd_approve), ("reopen", cmd_reopen), ("log", cmd_log)):
        p = sub.add_parser(c)
        p.add_argument("name"); p.add_argument("station")
        p.add_argument("--by", default="reviewer"); p.add_argument("--note", default="")
        p.set_defaults(fn=fn)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
