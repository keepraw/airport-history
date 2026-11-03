# 全球历史机场 Batch 5：实际证据研究（中文交接）

基准：main `19b7b1decfe2b43916fd4607b049ebb79293ae77`。正式库保持 **0.10.0 / Schema 3.0.0 / 37 机场 / 52 分配 / 101 来源 / 3 名称**，本轮 **正式准入 0 条**。

## 1. 结论先行

- 选出 **12 个事件组**（覆盖 46 个既有 triage 分组），均为未被既往批次映射的候选。
- 取得并锁定 **34 个来源、32 个不同原件字节流**（AOT 两份因 HTTP 202 反爬未能重新取得，如实记为 failed）。原件只在 ignored `work/global-batch-5/originals/`，仓库只含 URL、SHA-256、短锚点和事实说明。
- **为何没有正式入库**：
  1. 韩国 RKSI/RKSS 是唯一已有 Owner 规则授权的生产通道。本轮在干净 main 上实际运行 `admission/v1/evidence.py acquire`（94/98 组件）、`recover.py` 后，`korean.py` 被已授权 Executor 拒绝：`kr-history` 官方目录页字节已变（`146bf11c…` → `03ccbba0…`），且 Executor 对该来源没有事实级替换合同。修复需改动已绑定的 Executor 输入，必须 Owner 重新授权两条规则，本轮没有这样做。
  2. 其他市场只能走 0.9.0 式人工逐条批准。当前 main 中 `data/airports.json`、`package.json`、`research/discovery/reviews.json` 及 discovery 摘要被 923 文件的 rule-v1/kr-molit 保护基线和 priority-markets、code-dates 锁定；`policy_formal.py`（被锁）对任何新 dataVersion 要求 policy receipt。没有 Owner 逐条批准，也没有经批准的人工准入发布路由，因此不能写正式库。
- 印度 BLR/HYD 两案达到“可供 Owner 逐条批准”的程度，精确候选记录见 `proposals.json`（未授权、ID 未保留）。

## 2. 选择的事件组

| # | 案例 | 市场 | 类型 | 状态 |
|---|---|---|---|---|
| 1 | 仁川 RKSI | KR | 已知身份、缺有效期 | insufficient_evidence（授权 Executor 拒绝变更原件） |
| 2 | 金浦 RKSS | KR | 同上 | insufficient_evidence |
| 3 | 石垣旧场→新石垣 ISG/ROIG | JP | 同码跨场址 | insufficient_evidence |
| 4 | 小牧→中部 NGO；RJNN→RJNA、RJGG | JP | IATA 复用 + ICAO 变更 | pending_review |
| 5 | Riem→新慕尼黑 MUC/EDDM | DE | 同码跨场址 | insufficient_evidence |
| 6 | Mueller→Austin-Bergstrom AUS | US | 标识复用 | pending_review |
| 7 | 廊曼→素万那普 BKK；廊曼 DMK | TH | IATA 复用 | insufficient_evidence |
| 8 | Subang→KLIA KUL/WMKK | MY | 同码跨场址 | insufficient_evidence |
| 9 | HAL→Kempegowda BLR（VOBG/VOBL） | IN | IATA 复用 | pending_review（有提案） |
| 10 | Begumpet→Shamshabad HYD（VOHY/VOHS） | IN | IATA 复用 | pending_review（有提案） |
| 11 | 巫家坝→长水 KMG/ZPPP | CN | 同码跨场址 | insufficient_evidence |
| 12 | 长洲岛→西江 WUZ | CN | 同码跨场址 | insufficient_evidence |

筛选但未选：巴东 PDG（唯一自带生效日的 WIPT→WIEE 2015-03-05 仅镜像可读）、广州 CAN（2004 前无原件）、大连/厦门（新场未启用）、LYG/YBP/LZO/ENY/JNG/ZHA（PR #15/#22 已查，缺口未变）。

## 3. 日期必须分开（示例）

- 海得拉巴：S.O.470(E) **通知日 2008-03-10**（原件扫描，原定 2008-03-16 00:01 生效，已被取代）；最终 **IATA 转移生效 2008-03-23 00:01**（仅论文转录，二手）；VOHS **许可证 2008-03-04**；AIP **2012-04-01** 版次与 **AMDT 10-26（2026-09-17 出版、2026-10-29 生效）** 为观察；IATA 查询 **2026-11-03** 为观察日。Begumpet 未物理关闭。
- 班加罗尔：特许协议 **2004-07-05**（BLR 属旧场、应转移，无日期）；S.O.1170(E) **2008-05-16 发布、2008-05-23 00:01 生效**，后改为 **2008-05-24**（二手）；VOBL 许可证 **2008-05-15**；HAL 未关闭。
- 名古屋：中部开港 **2005-02-17**；RJNN 气象电报止于 **2005-02-16 24:00 JST**、RJNA 自 **2005-02-17 00:00 JST**（气象切换日，不是 AIP 指定日）。
- 奥斯汀：FAA 标识 BSM（**1998-07-30** 出版）→ AUS（**1999-02-11** 出版）；开航 **1999-05-23**；Mueller 末日 **1999-05-22**、最后一架飞机离场 **1999-06-24**（二手）。FAA LID 不等于 IATA。

网页捕获时间、Git 提交时间均未当作代码分配日期。

## 4. 生产解析器结果

- **正式增量：0 resolved / 0 uncertain / 0 conflict，已发布答案 0 变化**（`data/airports.json` 与 `test/curated-0.10.0.json` 字节相同）。
- 仅供 Owner 决策的模拟（**不计入覆盖**）：在正式 0.10.0 上追加提案中的 4 个物理身份、8 条分配（4 ICAO + 4 IATA），用未修改的 `resolveAirport()` 逐日比较 2015-01-01—2026-10-29 及边界日：**26,049** 个 not_found→resolved、**267** 个 not_found→uncertain，已发布 resolved 改变 0、新增/消失 conflict 0。见 `coverage.json`。
- 提案的主要风险：ICAO 为 2012→2026 约 14.6 年长间隔连续推断（远超 AAI policy 的 112 天预算）；HYD/BLR 最终生效通知原件未取得。

## 5. 下一步

1. 韩国：Owner 决定是否批准带“动态目录页替换合同”的 Executor 修订并重新授权两条规则，然后按 `admission/v1` 生产流程发布。
2. 印度：Owner 对 `proposals.json` 逐条批准或否决；并补取 Gazette 原扫描与中间 AIP 版次以缩短推断区间；同时需批准一个人工准入的版本化发布路由（现有锁定基线会使 `pnpm check` 失败）。
3. 其他案例按 `batch.json` 的 `nextAction` 获取原件。
