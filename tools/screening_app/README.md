# 篩選站（screening app）

兩位人類審查者各自獨立做標題摘要篩選（第 3 站）或全文資格判定（第 4 站）的網頁 App。
目標：學弟妹只需要「打開連結、選名字、按按鈕」，不碰終端機、CSV 或 git。

## 組成

| 檔案 | 用途 |
|---|---|
| `index.html` | App 本體。以 Claude artifact 發布，宣告 `db` + `user` 能力 |
| `make_seed.py` | `records_dedup.csv` → `seed.json`（config + records），由 Claude 寫進 App 資料庫 |
| `pull_decisions.py` | App 資料庫的 decisions → `screen_A.csv` / `screen_B.csv` |

## 資料庫結構

```
config/main            {project, stage: "ta"|"ft", reviewers: [A, B], reasons: [...], pico}
records/<id>           {id, order, title, abstract, authors, journal, year, doi, pmid}
decisions/<stage>__r<i>__<id>
                       {stage, reviewer, record_id, order, decision: include|exclude|unsure,
                        reason, confidence: high|medium|low, note, time}
```

存取規則：`config`、`records` 只有編輯者（通訊作者）能寫；`decisions` 任何 Contributor 可寫。
App 只顯示審查者自己的判定，不顯示對方的——獨立性靠流程與信任，不是技術鎖。

## 操作流程（通訊作者）

```bash
# 1. 準備灌檔
python make_seed.py --records ../../projects/<題目>/03_screening/records_dedup.csv \
    --project "<題目>" --reviewers "學弟A" "學弟B" --pico ../../projects/<題目>/01_protocol/pico.md \
    --llm ../../projects/<題目>/03_screening/screen_LLM.csv --out seed.json
# 2. 請 Claude 把 seed.json 寫進 artifact 資料庫（ArtifactData batch，每批 ≤ 50 筆）
# 3. 分享連結給兩位審查者（Contributor）
# 4. 兩人完成後，請 Claude 把 decisions 匯出成 decisions.json，然後：
python pull_decisions.py decisions.json --reviewers "學弟A" "學弟B" --stage ta \
    --records ../../projects/<題目>/03_screening/records_dedup.csv --outdir ../../projects/<題目>/03_screening/
# 5. 回第 3 站跑 adjudicate.py
```

## 審查者操作

1. 打開連結，選自己的名字。
2. 讀標題與摘要，按「納入」「不確定」或「排除」；排除要從下拉選理由。鍵盤：1 / 2 / 3，Enter 存檔。
3. 「清單」可回頭修改任一篇。全部完成會顯示綠色橫幅。
4. 篩完之前，不要跟另一位討論個別文獻。

## 換題目或換階段

同一個 artifact 可以重複用：請 Claude 刪掉舊的 `records` 與 `decisions`，再灌新的。或者每個題目各發布一個 artifact，比較乾淨。
