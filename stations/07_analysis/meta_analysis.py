#!/usr/bin/env python3
"""
meta_analysis.py — 第 7 站備用版（純 Python，無需 R）

用法：
  python meta_analysis.py --outcomes extraction_outcomes.csv --outcome "TAM" --timepoint "12w" --measure MD --out results/
  python meta_analysis.py --outcomes demo_data.csv --outcome "TAM" --timepoint "12w" --measure MD --out results_demo/

支援：MD / SMD（Hedges' g）/ RR / OR；固定效應（inverse variance）與隨機效應（DerSimonian-Laird）；
      I²、τ²、Q；leave-one-out；Egger 迴歸；森林圖；漏斗圖；亞組（--subgroup 欄位需在 outcomes 檔中）。

教學重點（看這裡就懂 meta-analysis 在算什麼）：
  1. 每篇研究算一個效應量 yi 和它的變異數 vi。
  2. 固定效應：權重 w = 1/vi，合併效應 = Σ(w·y) / Σw。大研究（vi 小）權重大。
  3. 異質性 Q = Σ w (y − pooled)²；若研究之間只有抽樣誤差，Q ≈ k−1。
     τ² = max(0, (Q − (k−1)) / C) 是「真實效果的變異數」（DerSimonian-Laird 估計）。
     I² = max(0, (Q − (k−1)) / Q)。
  4. 隨機效應：權重改成 1/(vi + τ²)。τ² 越大，各研究權重越平均（小研究發言權變大）。
"""
import argparse
import csv
import math
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

import numpy as np
from scipy import stats

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ---------- 效應量 ----------

def effect_continuous(r, measure):
    n1, m1, s1 = float(r["n_int"]), float(r["mean_int"]), float(r["sd_int"])
    n2, m2, s2 = float(r["n_ctl"]), float(r["mean_ctl"]), float(r["sd_ctl"])
    how = r.get("reported_as", "mean_sd")
    if how == "mean_se":            # SE → SD
        s1, s2 = s1 * math.sqrt(n1), s2 * math.sqrt(n2)
    elif how == "mean_ci":          # 若 sd 欄填的是 (upper − lower)
        s1, s2 = s1 * math.sqrt(n1) / 3.92, s2 * math.sqrt(n2) / 3.92
    if r.get("higher_is_better", "yes") == "no":
        m1, m2 = -m1, -m2
    if measure == "MD":
        y = m1 - m2
        v = s1**2 / n1 + s2**2 / n2
    else:  # SMD, Hedges' g
        sp = math.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))
        d = (m1 - m2) / sp
        J = 1 - 3 / (4 * (n1 + n2) - 9)
        y = d * J
        v = (n1 + n2) / (n1 * n2) + y**2 / (2 * (n1 + n2))
    return y, v


def effect_binary(r, measure):
    a, n1 = float(r["events_int"]), float(r["n_int"])
    c, n2 = float(r["events_ctl"]), float(r["n_ctl"])
    b, d = n1 - a, n2 - c
    if 0 in (a, b, c, d):            # 零事件：加 0.5 連續性校正
        a, b, c, d = a + .5, b + .5, c + .5, d + .5
    if measure == "RR":
        y = math.log((a / (a + b)) / (c / (c + d)))
        v = 1 / a - 1 / (a + b) + 1 / c - 1 / (c + d)
    else:  # OR
        y = math.log((a * d) / (b * c))
        v = 1 / a + 1 / b + 1 / c + 1 / d
    return y, v


# ---------- 合併 ----------

def pool(y, v):
    y, v = np.asarray(y, float), np.asarray(v, float)
    k = len(y)
    w = 1 / v
    fe = (w * y).sum() / w.sum()
    fe_se = math.sqrt(1 / w.sum())
    Q = (w * (y - fe) ** 2).sum()
    df = k - 1
    C = w.sum() - (w**2).sum() / w.sum()
    tau2 = max(0.0, (Q - df) / C) if C > 0 else 0.0
    I2 = max(0.0, (Q - df) / Q) * 100 if Q > 0 else 0.0
    wr = 1 / (v + tau2)
    re = (wr * y).sum() / wr.sum()
    re_se = math.sqrt(1 / wr.sum())
    z = re / re_se
    p = 2 * (1 - stats.norm.cdf(abs(z)))
    # 預測區間（Higgins 2009）：下一個新研究的真實效果會落在哪
    t = stats.t.ppf(0.975, df - 1) if df > 1 else float("nan")
    pi = (re - t * math.sqrt(tau2 + re_se**2), re + t * math.sqrt(tau2 + re_se**2))
    return dict(k=k, fe=fe, fe_ci=(fe - 1.96 * fe_se, fe + 1.96 * fe_se),
                re=re, re_ci=(re - 1.96 * re_se, re + 1.96 * re_se), re_p=p,
                Q=Q, Q_p=1 - stats.chi2.cdf(Q, df) if df > 0 else float("nan"),
                tau2=tau2, I2=I2, weights=wr / wr.sum() * 100, pi=pi)


def egger(y, v):
    """Egger 迴歸：標準化效應 vs 精確度。截距顯著偏離 0 → 漏斗不對稱。"""
    y, v = np.asarray(y), np.asarray(v)
    se = np.sqrt(v)
    X = np.column_stack([np.ones_like(se), 1 / se])
    beta, res, *_ = np.linalg.lstsq(X, y / se, rcond=None)
    k = len(y)
    resid = y / se - X @ beta
    s2 = (resid**2).sum() / (k - 2)
    cov = s2 * np.linalg.inv(X.T @ X)
    t = beta[0] / math.sqrt(cov[0, 0])
    p = 2 * (1 - stats.t.cdf(abs(t), k - 2))
    return beta[0], t, p


# ---------- 圖 ----------

def forest(labels, y, v, res, measure, path, log_scale):
    k = len(y)
    fig, ax = plt.subplots(figsize=(9, 1.2 + 0.45 * k))
    f = np.exp if log_scale else (lambda x: x)
    for i, (lab, yi, vi, w) in enumerate(zip(labels, y, v, res["weights"])):
        se = math.sqrt(vi)
        ax.plot([f(yi - 1.96 * se), f(yi + 1.96 * se)], [k - i, k - i], color="#444", lw=1)
        ax.scatter(f(yi), k - i, s=20 + w * 6, marker="s", color="#2b6cb0", zorder=3)
        ax.text(-0.02, k - i, lab, ha="right", va="center", transform=ax.get_yaxis_transform(), fontsize=9)
        ax.text(1.02, k - i, f"{f(yi):.2f} [{f(yi-1.96*se):.2f}, {f(yi+1.96*se):.2f}]  {w:.1f}%",
                ha="left", va="center", transform=ax.get_yaxis_transform(), fontsize=8)
    lo, hi = res["re_ci"]
    ax.fill([f(lo), f(res["re"]), f(hi), f(res["re"])], [0, 0.25, 0, -0.25], color="#c05621")
    ax.text(-0.02, 0, f"Random effects (k={k})", ha="right", va="center", transform=ax.get_yaxis_transform(), fontsize=9, weight="bold")
    ax.text(1.02, 0, f"{f(res['re']):.2f} [{f(lo):.2f}, {f(hi):.2f}]  I²={res['I2']:.0f}%",
            ha="left", va="center", transform=ax.get_yaxis_transform(), fontsize=8, weight="bold")
    ax.axvline(1 if log_scale else 0, color="#888", lw=0.8, ls="--")
    if log_scale:
        ax.set_xscale("log")
    ax.set_yticks([]); ax.set_ylim(-1, k + 1)
    ax.set_xlabel(measure + ("  (log scale)" if log_scale else ""))
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    plt.tight_layout(); fig.savefig(path, dpi=200); plt.close(fig)


def funnel(y, v, res, measure, path):
    se = np.sqrt(v)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(y, se, color="#2b6cb0")
    top = se.max() * 1.1
    s = np.linspace(0, top, 50)
    ax.plot(res["re"] - 1.96 * s, s, "--", color="#888"); ax.plot(res["re"] + 1.96 * s, s, "--", color="#888")
    ax.axvline(res["re"], color="#c05621")
    ax.set_ylim(top, 0); ax.set_xlabel(measure + (" (log)" if measure in ("RR", "OR") else "")); ax.set_ylabel("Standard error")
    ax.set_title("Funnel plot")
    plt.tight_layout(); fig.savefig(path, dpi=200); plt.close(fig)


# ---------- 主程式 ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outcomes", required=True)
    ap.add_argument("--outcome", required=True)
    ap.add_argument("--timepoint", default=None)
    ap.add_argument("--measure", default="MD", choices=["MD", "SMD", "RR", "OR"])
    ap.add_argument("--subgroup", default=None, help="outcomes 檔中的欄位名")
    ap.add_argument("--out", default="results/")
    ap.add_argument("--by", default="")
    args = ap.parse_args()

    require_station("07")
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    with open(args.outcomes, encoding="utf-8") as f:
        allrows = [r for r in csv.DictReader(f) if r["outcome"] == args.outcome]
    # 時間點保護：同一研究不同追蹤時間不能混進同一張森林圖（同一群病人會被算兩次）
    tps = sorted({r.get("timepoint", "") for r in allrows})
    if args.timepoint is None:
        if len(tps) > 1:
            raise SystemExit(f"✗ 此 outcome 有 {len(tps)} 個時間點（{', '.join(tps)}），必須用 --timepoint 指定其中一個。")
        rows = allrows
    else:
        rows = [r for r in allrows if r.get("timepoint", "") == args.timepoint]
    if len(rows) < 2:
        raise SystemExit("少於 2 篇，無法合併。")
    ids = [r["id"] for r in rows]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise SystemExit(f"✗ 研究 ID 重複：{', '.join(dup)}。多臂試驗請先在第 5 站決定合併或選臂，再跑分析。")

    log_scale = args.measure in ("RR", "OR")
    eff = effect_binary if log_scale else effect_continuous
    y, v, labels = [], [], []
    for r in rows:
        yi, vi = eff(r, args.measure)
        y.append(yi); v.append(vi)
        labels.append(f"{r['id']} {r.get('first_author','')} {r.get('year','')}".strip())
    res = pool(y, v)
    f = (lambda x: math.exp(x)) if log_scale else (lambda x: x)

    lines = [f"Outcome: {args.outcome} | Timepoint: {args.timepoint or 'all'} | Measure: {args.measure} | k = {res['k']}", ""]
    conv = [] if log_scale else [r['id'] for r in rows if r.get('reported_as', 'mean_sd') != 'mean_sd']
    if conv:
        lines.append(f"注意：以下研究的 SD 經換算，請確認：{', '.join(conv)}\n")
    lines += [
        f"Fixed effect  : {f(res['fe']):.3f}  [{f(res['fe_ci'][0]):.3f}, {f(res['fe_ci'][1]):.3f}]",
        f"Random effect : {f(res['re']):.3f}  [{f(res['re_ci'][0]):.3f}, {f(res['re_ci'][1]):.3f}]   p = {res['re_p']:.4f}",
        f"Prediction interval : [{f(res['pi'][0]):.3f}, {f(res['pi'][1]):.3f}]",
        f"Heterogeneity : Q = {res['Q']:.2f} (p = {res['Q_p']:.3f}), tau² = {res['tau2']:.4f}, I² = {res['I2']:.1f}%",
        "", "Study weights (random effects):"]
    lines += [f"  {lab:<30} {w:5.1f}%" for lab, w in zip(labels, res["weights"])]

    # leave-one-out
    loo_rows = []
    for i in range(len(y)):
        r_ = pool(y[:i] + y[i+1:], v[:i] + v[i+1:])
        loo_rows.append({"excluded": labels[i], "RE": f(r_["re"]), "lower": f(r_["re_ci"][0]), "upper": f(r_["re_ci"][1]), "I2": r_["I2"]})
    with open(out / "leave_one_out.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=loo_rows[0].keys()); w.writeheader(); w.writerows(loo_rows)

    # Egger
    if len(y) >= 10:
        b0, t, p = egger(y, v)
        (out / "egger.txt").write_text(f"Egger intercept = {b0:.3f}, t = {t:.2f}, p = {p:.3f}\n(p < 0.1 視為漏斗不對稱的訊號)\n", encoding="utf-8")
        lines.append(f"\nEgger: intercept {b0:.3f}, p = {p:.3f}")
    else:
        (out / "egger.txt").write_text("k < 10，Egger 檢定檢力不足，未執行。\n", encoding="utf-8")
        lines.append("\nEgger: k < 10，未執行。")

    # 亞組
    if args.subgroup:
        groups = {}
        for r, yi, vi in zip(rows, y, v):
            groups.setdefault(r.get(args.subgroup, ""), []).append((yi, vi))
        sg = []
        for g, pairs in groups.items():
            if len(pairs) >= 2:
                r_ = pool([p[0] for p in pairs], [p[1] for p in pairs])
                sg.append({"subgroup": g, "k": len(pairs), "RE": f(r_["re"]), "lower": f(r_["re_ci"][0]), "upper": f(r_["re_ci"][1]), "I2": r_["I2"]})
        if sg:
            with open(out / "subgroup.csv", "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=sg[0].keys()); w.writeheader(); w.writerows(sg)
            lines.append(f"\n亞組（{args.subgroup}）結果見 subgroup.csv")

    (out / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    forest(labels, y, v, res, args.measure, out / "forest.png", log_scale)
    funnel(np.array(y), np.array(v), res, args.measure, out / "funnel.png")
    print("\n".join(lines))
    print(f"\n已輸出 → {out}/（summary.txt, forest.png, funnel.png, leave_one_out.csv, egger.txt）")
    print("請撰寫 interpretation.md：效應大小的臨床意義、異質性來源、可信度。")
    log_event("07", "meta_analysis.py",
              args={"outcome": args.outcome, "timepoint": args.timepoint, "measure": args.measure, "subgroup": args.subgroup},
              outputs=[str(out / "summary.txt"), str(out / "forest.png"), str(out / "leave_one_out.csv")],
              note=f"k={res['k']} RE={f(res['re']):.3f} I2={res['I2']:.0f}%", by=args.by)


if __name__ == "__main__":
    main()
