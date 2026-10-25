# 第 03 站：去重與標題摘要篩選

## 這站在幹嘛

上一站可能抓回來八百筆，其中一半是同一篇在不同資料庫重複出現，剩下的大部分跟題目無關。
這站把它們濾成幾十篇「值得看全文」的候選。

## 兩個關鍵觀念

### 去重（deduplication）
同一篇在 PubMed 和 Embase 各出現一次是常態。合併時先用 DOI 比對，沒 DOI 的用「標題正規化 + 年份」。
`dedup.py` 會做這件事，並輸出「哪些被判定為重複」讓你抽查。

### 兩位人類審查者，各自獨立看完每一筆
這是 SR 方法學的硬規定，本生產線**不用 LLM 代替任何一位人**：

| 角色 | 誰 | 做什麼 | 輸出 |
|---|---|---|---|
| 審查者 A | 第一作者 | 獨立看完全部紀錄，每筆判 include / exclude + 信心度 + 理由 | `screen_A.csv` |
| 審查者 B | 第二作者 | 同上，**看不到 A 的結果** | `screen_B.csv` |
| 第三人 | 通訊作者 | 只裁決 A ≠ B 的那些 | 填 `screening_decisions.csv` 的 final 欄 |
| LLM（選用） | Claude | **預篩與品管**：先跑一輪給排序用；兩人都排除但它高信心納入的，標旗請人回頭看 | `screen_LLM.csv` |

為什麼要兩個人都看完全部？因為「一人 + AI」目前在多數期刊與 Cochrane 仍不被接受為獨立雙審查，而且兩人各看一遍，kappa 才有意義。
LLM 的價值在於：把最可能相關的排前面，讓人看得快；以及當第三雙眼睛抓漏。

## 步驟

```bash
# 1. 去重（自動讀 ../02_search/records_*.csv）
python dedup.py --out records_dedup.csv --by 你

# 2.（選用）LLM 預篩：把 records_dedup.csv 交給 Claude，用 screener_prompt.md
#    產出 screen_LLM.csv（欄位：id, decision, confidence, reason）
#    可依此排序 records_dedup.csv，讓 A、B 先看高可能性的；但 A、B 不看 LLM 的判定與理由

# 3. A、B 各自獨立篩選，各產出 screen_A.csv / screen_B.csv（同樣四個欄位）
#    建議用 screening_sheet_template.csv 複製兩份，分開填，填完前不互看

# 4. 比對
python adjudicate.py screen_A.csv screen_B.csv --llm screen_LLM.csv --out screening_decisions.csv --by 你
#    needs_third = yes 的列 → 第三人填 final / final_by / final_reason
#    qa_flag = yes 的列 → A、B 各自回頭看一眼；改變決定要在 reason 寫明
```

## 無痛版：用篩選 App，學弟不碰 CSV

`tools/screening_app/` 是一個網頁 App（已發布為 Claude artifact「篩選站」）。流程：

1. 通訊作者請 Claude 跑 `make_seed.py`，把 `records_dedup.csv`（可加 `screen_LLM.csv` 做排序）灌進 App 的資料庫。
2. 把 App 連結分享給兩位審查者（分享權限要是 **Contributor**，不然存不進去）。
3. 審查者打開連結、選自己的名字，一篇一篇按「納入／不確定／排除」，排除要選理由。可以用手機，中途離開會記得進度。
4. 兩人都按完後，請 Claude 從 App 資料庫讀出 decisions，跑 `pull_decisions.py` 轉成 `screen_A.csv`、`screen_B.csv`，再跑 `adjudicate.py`。

同一個 App 把 stage 換成 `ft` 就是第 4 站的全文資格判定。

## 篩選原則（教學弟妹的話）

* 標題摘要階段**只排除「明確不符」**的，有疑慮一律放行到全文階段。這階段寧可多留。
* 排除理由要能對應到 PICO 的某一項（錯族群、錯介入、錯設計、錯語言、非原始研究）。
* 看不到摘要的（只有標題）→ 放行。
* 會議摘要 → 依 protocol 決定；通常先標記，不直接排除。
* 篩選中途不要討論個別文獻；討論留到比對之後，否則就不叫獨立。

## 你要檢查什麼

- [ ] 去重後筆數合理（通常比合併前少 20–50%），抽查 10 筆重複清單
- [ ] `screen_A.csv`、`screen_B.csv` 都涵蓋全部 id（adjudicate.py 會擋缺漏）
- [ ] 所有 needs_third 的列都有第三人裁決與理由
- [ ] 所有 qa_flag 的列都被回頭看過
- [ ] 記錄數字：合併前、去重後、初篩排除、進入全文——PRISMA 流程圖要用

## 常見踩雷

* 讓 B 看到 A 的結果，或兩人一起篩——那不是獨立
* 用 LLM 的結果當其中一位審查者——投稿時 Methods 寫不出來
* 在這階段就要求「必須有 outcome 數據」——摘要常不寫，會誤殺
* 只信 kappa——kappa 高只代表兩個審查者錯得一樣

## 稿件裡的對應文字（第 9 站會用）

> Two reviewers (A.B. and C.D.) independently screened all titles and abstracts against the eligibility criteria; disagreements were resolved by a third reviewer (E.F.). A large language model (Claude, Anthropic) was used to pre-screen and prioritise records and to flag potential false exclusions for re-examination; it did not replace either human reviewer, and all inclusion decisions were made by the human reviewers.
