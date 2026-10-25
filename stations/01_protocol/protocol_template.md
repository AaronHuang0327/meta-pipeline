# 系統性回顧與統合分析 計畫書（填完存成 protocol.md）

> 結構對齊 PRISMA-P 2015，可直接貼進 PROSPERO 表單。

## 1. 題目

## 2. 背景與理由
（三段：臨床問題為何重要 → 現有證據為何不足或互相矛盾 → 本回顧要回答什麼）

## 3. 目的
主要目的：
次要目的：

## 4. 納入與排除條件
（從 pico.md 複製，並加上：）
* 重複發表的處理：
* 會議摘要是否納入：
* 資料不全時是否聯絡作者：

## 5. 資訊來源與檢索
* 資料庫：PubMed/MEDLINE、Embase、Cochrane CENTRAL（其他：Scopus、Web of Science、CINAHL）
* 檢索日期：
* 其他來源：納入文獻的參考文獻、臨床試驗登錄（ClinicalTrials.gov）
* 完整語法：見 02_search/search_strategy.md

## 6. 研究篩選
* 兩位審查者（第一、第二作者）各自獨立完成全部紀錄的標題摘要篩選與全文篩選，篩選期間不互看結果
* 不一致處由第三位審查者（通訊作者）裁決
* 大型語言模型（Claude）僅用於預篩排序與品管（標記可能的誤排除供人工複查），不取代任何一位審查者；所有納入決定由人類審查者做出（投稿時需揭露）

## 7. 資料擷取
* 擷取項目：研究特徵（作者、年份、國家、設計、樣本數）、病人特徵、介入細節、對照細節、各 outcome 於各時間點之數值
* 連續變項缺 SD 時的處理：由 SE、CI、IQR 換算（Cochrane Handbook 6.5.2）
* 多臂試驗的處理：

## 8. 偏倚風險評讀
* RCT：RoB 2
* 非隨機介入研究：ROBINS-I
* 觀察性研究（若採用）：Newcastle-Ottawa Scale
* 兩位審查者獨立評讀

## 9. 資料合成
* 效應量：主要 outcome ____，次要 ____
* 模型：隨機效應（DerSimonian-Laird / REML）為主；固定效應作為敏感度
* 異質性：I²、τ²、Cochran Q；I² > 50% 視為顯著異質
* 預先設定之亞組：
  1.
  2.
* 敏感度分析：排除高偏倚風險研究；leave-one-out
* 發表偏倚：≥ 10 篇時做漏斗圖與 Egger 檢定
* 無法合併時：敘述性合成（SWiM 指引）

## 10. 證據確定性
GRADE，每個主要 outcome 一行 Summary of Findings

## 11. 登記
PROSPERO 編號：（待填）
