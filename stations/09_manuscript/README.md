# 第 09 站：稿件

## 這站在幹嘛

前八站的所有產出，組裝成一篇依 PRISMA 2020 格式的稿件。
好消息：**Methods 跟 Results 幾乎已經寫好了**——Methods 是第 1 站 protocol 的過去式改寫，Results 是第 3–8 站的數字排列。
真正要從零寫的只有 Introduction 的論證和 Discussion 的臨床判斷。

## 步驟

### 1. 畫 PRISMA 流程圖
```bash
python prisma_flow.py --db "PubMed=412" --db "Embase=388" --db "CENTRAL=57" --other 6 \
    --dedup 523 --screened-out 471 --fulltext 52 \
    --excl "wrong_population=12" --excl "wrong_intervention=20" --excl "wrong_design=9" --excl "no_fulltext=2" \
    --included 9 --out prisma_flow.svg
```
數字來源：第 2 站（各庫筆數）、第 3 站（去重後、初篩排除）、第 4 站（全文篇數、排除理由、最終納入）。
**腳本會自動驗算：去重後 − 初篩排除 = 全文篇數；全文 − 各理由排除 = 納入。對不上就不給出圖。**

### 2. 填 PRISMA 2020 checklist（`prisma_checklist.md`）
27 項，每項寫「稿件第幾頁」。投稿時要附。

### 3. 組稿（`manuscript_template.md` → `manuscript.md`）
把各站產出丟給 Claude，請它依模板填 Methods 與 Results：
* Methods 每段對應 protocol 一節，改成過去式
* Results 依序：檢索結果 → 研究特徵表 → 偏倚風險圖 → 主要 outcome 森林圖與數字 → 次要 outcome → 亞組與敏感度 → 發表偏倚 → GRADE SoF 表
* **每個數字都要能回溯到某一站的某個檔案**——Claude 寫稿時要求它在數字後面用註解標出處 `<!-- results/summary.txt -->`，定稿前再刪

### 4. 你寫的部分
* Introduction 最後一段（為什麼現在需要這篇、跟既有回顧差在哪）
* Discussion：主要發現的臨床意義、跟既有文獻比較、機轉推測、**限制**（這段要誠實：異質性來源、納入研究品質、間接性）、臨床與研究建議
* Claude 可以給 Discussion 骨架與「可能的論點清單」，但定稿要是你的判斷

### 5. 圖表
* Figure 1：PRISMA 流程圖
* Figure 2：偏倚風險交通燈圖（可用 robvis 線上工具：https://mcguinlu.shinyapps.io/robvis/ ）
* Figure 3+：森林圖（主要 outcome 一張）
* Table 1：納入研究特徵（從 extraction.csv 整理）
* Table 2：Summary of Findings（從 grade_sof.csv）
* 補充：完整檢索語法、排除文獻清單與理由、漏斗圖、敏感度分析

### 6. 揭露 AI 使用
Methods 篩選段寫明：兩位人類審查者獨立篩選，LLM 僅用於預篩排序與品管旗標、不取代審查者（文字範本在 `03_screening/README.md` 末段）。
擷取段寫明：LLM 產出擷取草稿，兩位人類核對。
投稿信與稿件末尾依期刊要求揭露（多數期刊現在要求）。`manifest.json` 的事件紀錄可作為補充資料。

## 你要檢查什麼

- [ ] PRISMA 流程圖數字自洽（腳本已驗，但再對一次）
- [ ] Methods 與 protocol 一致；偏離處在 Discussion 限制段說明
- [ ] 稿件每個數字都對得到 results/ 或各站 CSV
- [ ] 摘要的數字跟正文一致（最常出錯的地方）
- [ ] Checklist 27 項都填了頁碼
- [ ] AI 使用已揭露

## 常見踩雷

* 摘要寫「顯著改善」但正文 CI 幾乎貼 0——審稿人會抓
* Discussion 只講好的，限制段三行帶過
* 忘了把 PROSPERO 編號放進摘要
* Figure 檔案解析度不足（期刊通常要 300 dpi）
