# 稿件模板（PRISMA 2020 結構；填完存成 manuscript.md）

> 數字後面用 `<!-- 出處 -->` 標記來源，定稿前刪除。

## Title
（含 "systematic review and meta-analysis"）

## Abstract（結構式，≤ 300 字）
Background / Methods（資料庫、日期、納入條件、PROSPERO 編號）/ Results（篇數、參與者數、主要效應與 CI、I²、GRADE）/ Conclusions

## Introduction
1. 臨床問題與重要性
2. 現有證據的矛盾或空白
3. 本回顧的目的（一句話，對應 PICO）

## Methods
### Protocol and registration
### Eligibility criteria（← pico.md）
### Information sources and search（← search_strategy.md；完整語法放附錄）
### Study selection（兩位人類審查者獨立；LLM 僅預篩與品管——文字範本見 03_screening/README.md 末段）
### Data extraction（← extraction_prompt.md 項目；SD 換算方法）
### Risk of bias（← 第 6 站工具）
### Data synthesis（← protocol 第 9 節；模型、異質性、亞組、敏感度、發表偏倚；軟體與版本）
### Certainty of evidence（GRADE）

## Results
### Study selection（Figure 1：PRISMA；數字 ← prisma_flow.py）
### Study characteristics（Table 1 ← extraction.csv）
### Risk of bias（Figure 2 ← rob.csv）
### Primary outcome（Figure 3 森林圖；效應、CI、I²、τ²、預測區間 ← results/summary.txt）
### Secondary outcomes
### Subgroup and sensitivity analyses（← subgroup.csv, leave_one_out.csv）
### Publication bias（← funnel.png, egger.txt）
### Certainty of evidence（Table 2 ← grade_sof.csv）

## Discussion
1. 主要發現（一段）
2. 與既有文獻比較
3. 可能機轉與臨床意義（含 MCID 的討論）
4. 限制（誠實：異質性來源、研究品質、間接性、篇數、發表偏倚無法排除）
5. 臨床與研究建議

## Conclusions
（兩三句，不要超過證據）

## Declarations
Funding / Conflicts / Data availability（manifest.json 與各站 CSV 可作為補充資料）/ AI use statement

## Supplementary
S1 完整檢索語法｜S2 排除文獻清單與理由｜S3 偏倚評讀細節｜S4 敏感度與亞組｜S5 PRISMA checklist
