# Meta-Analysis 生產線（meta-pipeline）

一條「每站自動產出、人工簽核後才放行」的系統性回顧與統合分析生產線。
設計目的：做一遍，就把 SR/MA 的每個步驟學起來；之後每個新題目都跑同一條線。

## 核心概念：閘門（gate）

```
題目 ──▶ 01 ──▶ 02 ──▶ 03 ──▶ 04 ──▶ 05 ──▶ 06 ──▶ 07 ──▶ 08 ──▶ 09 ──▶ 投稿
         │      │      │      │      │      │      │      │      │
        簽核   簽核   簽核   簽核   簽核   簽核   簽核   簽核   簽核
```

* 每一站做完會產出固定檔名的輸出檔。
* 你（主審）看過、改過、確認後，用 `gate.py approve` 蓋章。
* 沒蓋章，下一站不准開工（腳本會擋）。蓋章紀錄寫進 `manifest.json`，誰、何時、備註，一清二楚——這就是你投稿時 Methods 的證據鏈。
* AI（Claude）負責「草稿與苦工」，人負責「判斷」。篩選與資格判定由第一、第二作者**各自獨立看完每一筆**，不一致由第三人裁決；LLM 只做預篩排序與品管旗標，不取代任何一位審查者。投稿要揭露 AI 用途。
* 每支腳本跑完會自動把「誰、何時、參數、產出檔與 sha256、幾列」寫進 `manifest.json`（`gate.py events <題目>` 查看）；簽核時記下輸出檔雜湊，之後被改動會在 `status` 標 ⚠。

## 九站一覽

| 站 | 名稱 | 自動化做什麼 | 你要判斷什麼 | 主要輸出 |
|---|---|---|---|---|
| 01 | 題目與計畫書 | 從一句臨床問題展開 PICO、納排條件、效應量、PROSPERO 草稿 | 題目是否值得做、PICO 邊界 | `pico.md`, `protocol.md` |
| 02 | 檢索策略 | 產生 PubMed / Embase / Cochrane 語法，執行 PubMed 檢索並匯出 | 語法敏感度、有沒有漏掉同義詞 | `search_strategy.md`, `records_*.csv` |
| 03 | 去重與初篩 | 合併去重；LLM 預篩供排序與品管 | 兩位作者各自獨立篩完全部；第三人裁決不一致 | `records_dedup.csv`, `screen_A/B.csv`, `screening_decisions.csv` |
| 04 | 全文與資格 | 抓 PMC 開放全文、列出需人工取得者、逐篇記錄排除理由 | 最終納入名單 | `eligibility.csv`, `fulltext/` |
| 05 | 資料擷取 | 依模板擷取，每格附頁碼與原文句 | 核對每個數字 | `extraction.csv` |
| 06 | 偏倚風險 | RoB 2 / ROBINS-I / NOS，每個 domain 附理由 | 是否同意判定 | `rob.csv` |
| 07 | 統計分析 | 合併效應、異質性、亞組、敏感度、發表偏倚、森林圖 | 模型選擇、亞組切法、如何解讀 | `results/` |
| 08 | GRADE | 證據等級與 Summary of Findings 表 | 降級理由是否合理 | `grade_sof.csv` |
| 09 | 稿件 | PRISMA 流程圖與 checklist、Methods/Results 初稿 | Discussion 的臨床觀點由你寫 | `manuscript.md`, `prisma_flow.svg` |

## 無痛版給學弟妹

`tools/screening_app/` 是篩選 App：審查者打開連結、選名字、按按鈕，不碰終端機與 CSV。擷取與偏倚評讀用 Google Sheets 由 Claude 填草稿、人核對。通訊作者只跟 Claude 對話，蓋章由 Claude 代跑、記你的名字。詳見 `tools/screening_app/README.md`。

## 快速開始

```bash
# 1. 開一個新題目（會把九站模板複製到 projects/<題目>/）
python gate.py new rme_extensor

# 2. 看目前走到哪
python gate.py status rme_extensor

# 3. 第一站做完、你看過了，蓋章
python gate.py approve rme_extensor 01 --by "Aaron" --note "PICO 確認，effect 用 MD"

# 4. 想撤銷（例如後來發現 PICO 要改）
python gate.py reopen rme_extensor 01 --by Aaron --note "加入 zone VII"

# 5. 多題目看板、下一步、事件紀錄
python gate.py board
python gate.py next rme_extensor
python gate.py events rme_extensor
```

每一站資料夾裡都有 `README.md`，用中文說明「這站在幹嘛、為什麼、常見踩雷、要怎麼檢查」。
教學順序就是 01 → 09，一站一站看 README、跑腳本、簽章。

## 安裝

```bash
git clone https://github.com/AaronHuang0327/meta-pipeline.git
cd meta-pipeline
pip install -r requirements.txt
```

教學手冊（陽光版、可互動蓋章）：`docs/index.html`，開啟 GitHub Pages 後網址為
https://aaronhuang0327.github.io/meta-pipeline/

## 需要的工具

* Python 3.9+（`pip install pandas requests`）
* R 4.x 加 `meta`、`metafor`（第 7 站標準版；沒有 R 可先用 `meta_analysis.py` 備用版）
* Claude（claude.ai 或 Claude Code）：負責 01、02 語法、03 篩選、05 擷取、06 評讀、09 寫作的「草稿」工作，依各站 README 的提示詞操作

## 共用方式

* 本 repo 只放生產線本體（九站模板、腳本、閘門）。
* `projects/` 已被 `.gitignore` 排除：每個題目的全文 PDF、擷取資料、分析結果都留在各自的工作區（本機、私有 repo 或共用雲端資料夾），不要推到公開 repo。
* 想改模板或腳本：開 branch → 改 → pull request，讓其他人看得到改了什麼。

## 與 Claude 一起跑（生產線模式）

把整個 `meta-pipeline/` 資料夾交給 Claude，並說「依 SKILL.md 從第 N 站開始」或直接說「繼續」。
`SKILL.md` 規定 Claude：先跑 `gate.py board`，挑第一個輪到它做的站做完、回報三行、停下來等蓋章；全部在等人時列出每題在等誰。
多個題目可以同時在線上，你只負責蓋章與人類篩選。
