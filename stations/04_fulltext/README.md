# 第 04 站：全文取得與資格判定

## 這站在幹嘛

上一站放行的幾十篇，這站要**一篇一篇讀全文**，確定真的符合納入條件。
這也是第一次遇到「拿不到全文」的現實問題。

## 步驟

### 1. 取得全文
把 `screening_decisions.csv` 裡 final = include 的清單交給 Claude：
* 有 PMC 開放取用的（PubMed 頁面有 "Free PMC article"）→ Claude 用 PubMed 工具抓全文
* 其他的 → Claude 列出清單（作者、年份、期刊、DOI），你從醫院圖書館、ResearchGate、或直接寫信給作者取得
* 全文 PDF 一律放進 `fulltext/` 資料夾，檔名用 `<id>_<第一作者>_<年份>.pdf`

### 2. 逐篇判定資格（填 `eligibility_template.csv` → 存成 `eligibility.csv`）
每一篇都要有一列，欄位：
* `decision`：include / exclude
* `exclusion_reason`：**必須從固定清單選**（見下），因為 PRISMA 流程圖要分類統計
* `reason_detail`：一句話，例如「對照組也用了早期活動」
* `page_ref`：你是在第幾頁看到排除理由的

排除理由固定清單：
```
wrong_population   錯族群（例如混了屈肌腱）
wrong_intervention 錯介入（例如 RM 定義不符）
wrong_comparator   錯對照
wrong_outcome      沒報告任何我們要的 outcome
wrong_design       錯設計（例如病例報告、回顧文章）
duplicate_data     同一批病人已在另一篇報告
no_fulltext        取不到全文（要先努力過：圖書館 + 聯絡作者）
language           語言不符 protocol
```

### 3. 這站也是「兩位人類獨立」
跟第 3 站一樣：第一、第二作者各自讀全文、各自判定（`reviewer_A`、`reviewer_B` 欄），不一致由第三人裁決。
Claude 可以先讀一遍、把每篇對應 PICO 的句子與頁碼摘出來給兩位省時間，但判定欄要由人填。

## 你要檢查什麼

- [ ] 每篇 include 的都能明確對應 PICO 四項
- [ ] 每篇 exclude 的都有固定清單的理由 + 頁碼
- [ ] `no_fulltext` 的篇數 ≤ 總數 5%，且已嘗試聯絡作者
- [ ] 檢查有沒有「同一批病人發了兩篇」（看作者、醫院、收案期間）
- [ ] 記錄數字：全文評估篇數、排除篇數（按理由分類）、最終納入篇數

## 常見踩雷

* 一篇文章同時符合多個排除理由——只記**第一個**碰到的（依 P → I → C → O → S 順序），不然流程圖數字會對不起來
* 會議摘要有數據但沒全文——依 protocol；如果納入，第 6 站要標記偏倚風險高
* 忘了從納入文獻的參考文獻裡再找（snowballing）——找到的要回第 2 站登記為 `records_other.csv`
