# 檢索策略（填完存成 search_strategy.md）

## 概念拆解

| 概念 | 自由詞（title/abstract） | 控制詞彙（MeSH / Emtree） |
|---|---|---|
| A: | | |
| B: | | |
| C:（選用） | | |

## 種子文獻（驗證敏感度用）
| 作者 年份 | PMID | PubMed 抓到？ | Embase 抓到？ |
|---|---|---|---|
| | | | |

## PubMed（檢索日期：____；筆數：____）
```
#1  ("term a"[tiab] OR "term b"[tiab] OR termc*[tiab])
#2  ("Mesh Term A"[Mesh])
#3  #1 OR #2
#4  ("term d"[tiab] OR ...)
#5  ("Mesh Term B"[Mesh])
#6  #4 OR #5
#7  #3 AND #6
#8  #7 NOT (animals[mh] NOT humans[mh])
```

## Embase（檢索日期：____；筆數：____）
```
#1  'term a':ti,ab OR 'term b':ti,ab OR termc*:ti,ab
#2  'emtree term a'/exp
...
```

## Cochrane CENTRAL（檢索日期：____；筆數：____）
```
#1  ("term a" OR "term b" OR termc*):ti,ab,kw
...
```

## 其他來源
* 納入文獻參考文獻：____ 篇
* ClinicalTrials.gov：____ 筆
* 引用追蹤：____ 篇

## 限制
* 語言：
* 年份：
* 發表型態：
