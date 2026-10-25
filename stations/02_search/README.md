# 第 02 站：檢索策略

## 這站在幹嘛

把 PICO 翻譯成資料庫聽得懂的語言，然後把所有可能相關的文獻一網打盡。
原則是**寧可多抓（高敏感度），不要漏抓（低特異度）**——多抓的下一站篩掉就好，漏抓的永遠找不回來。

## 為什麼要這麼龜毛

* 檢索語法會原封不動放進稿件的附錄，審稿人（尤其 Cochrane 系統的）會逐字看。
* 「漏掉一篇關鍵 RCT」是 SR 被拒最常見的理由之一。
* 同一套語法，三年後要更新回顧時可以直接重跑。

## 步驟

### 1. 從 PICO 拆概念
通常只用 P 和 I（有時加 C），**不要**把 O 放進檢索——outcome 在摘要裡常常不會提，放進去會漏。

### 2. 每個概念列同義詞 + 控制詞彙
```
概念 A（伸肌腱損傷）
  自由詞：extensor tendon*, extensor injur*, extensor repair*, zone IV, zone V, zone VI
  MeSH：Tendon Injuries[Mesh], Finger Injuries[Mesh]

概念 B（relative motion）
  自由詞：relative motion, relative extension, yoke splint, ICAM, immediate controlled active motion
  MeSH：Splints[Mesh], Early Ambulation[Mesh]（視情況）
```
同一概念內用 **OR**，概念之間用 **AND**。

### 3. 寫成三套語法（填 `search_strategy_template.md` → 存成 `search_strategy.md`）
PubMed、Embase、Cochrane CENTRAL 的欄位標籤不一樣（`[tiab]` vs `:ti,ab` vs `:ti,ab,kw`），要各寫一份。
Claude 可以幫你翻譯，但**你要逐行看**：MeSH 詞是否真的存在、截斷符號位置對不對。

### 4. 驗證語法的敏感度
拿你已知一定要被抓到的 3–5 篇「種子文獻」（seed papers），確認語法抓得到。抓不到就回去補同義詞。
這步最常被跳過，也最常出事。

### 5. 執行檢索並匯出
* PubMed：`python pubmed_search.py --query "..." --out records_pubmed.csv`（用 NCBI E-utilities，免費）
  或請 Claude 用 PubMed 工具跑，把結果存成同格式 CSV。
* Embase / Scopus / WoS：沒有免費 API，請到學校/醫院圖書館的介面跑，匯出 CSV 或 RIS，放進本資料夾命名為 `records_embase.csv` 等。
* 記錄每個資料庫的**檢索日期**與**筆數**（PRISMA 流程圖要用）。

### 6. 補充檢索
納入文獻的參考文獻清單、ClinicalTrials.gov、引用追蹤（Google Scholar「被引用」）。找到的另外列 `records_other.csv`。

## 你要檢查什麼

- [ ] 每個概念至少 3 個同義詞，含單複數與截斷
- [ ] MeSH / Emtree 詞確實存在（PubMed MeSH Browser 查過）
- [ ] 種子文獻全部被抓到
- [ ] 三個資料庫都有檢索日期與筆數
- [ ] 沒有把 outcome 當檢索條件

## 常見踩雷

* 用 `AND` 連接同義詞（應該是 `OR`）
* 截斷符號打在太前面：`exten*` 會抓到 extension、extent、external……
* 只搜 PubMed——審稿人會直接問「為什麼沒有 Embase？」
* 忘了記錄日期，三個月後寫稿想不起來
