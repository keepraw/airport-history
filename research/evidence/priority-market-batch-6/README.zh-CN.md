# 五大优先市场 Batch 6：实际补证与身份候选

实际基准为已 fetch 的 main `5c54ab3e861a43d49cdadb27715e42b88f1630ec`（2026-11-06 再次核对未变）。按 **中国 → 韩国 → 日本 → 美国 → 欧洲** 获取原件；没有重新扫描或重建全球索引。PR #29、#32 未修改，Keepraw-Fly 未修改。

本轮实际跟进 **31 个案例**，统一清单保留 **66 个既有事件案例**，新增合肥、北九州两项完整调查及光州 1964 年迁址的一条二手线索，共 **69 项 backlog**。原 60 个调查单位完整映射；中部与小牧按同一次名古屋历史交接去重，保留两处物理场址。127 条重点市场代码复用线索单独保留，不当作已调查事件或正式机场。来源数量不作为完成进度。

| 市场 | 去重后既有案例 | 本轮实际跟进 | 正式身份新增 | IATA/ICAO 新增 | 主要结果与剩余问题 |
|---|---:|---:|---:|---:|---|
| 中国 | 16 | 14（含新案合肥） | 0 | 0 / 0 | 补齐多组旧新场址官方文件；代码交接原件及适用准入范围仍缺 |
| 韩国 | 7 | 4；另记录光州 1964 二手线索 | 0 | 0 / 0 | 现有规则生成 2 项未发布身份候选；完整代码及发布入口仍阻塞 |
| 日本 | 11 | 4（含新案北九州） | 0 | 0 / 0 | NGO 零时承接、石垣场址/日期、下地岛类型化代码；历史 AIP/行政分配仍待补 |
| 美国 | 11 | 4 | 0 | 0 / 0 | 新旧 Williston 标识并存、St George 历史 LID、Austin 气象标识与机场代码分开 |
| 欧洲 | 21 | 5 | 0 | 0 / 0 | Doncaster、Berlin、Munich、Murcia、Narvik 日期与事件性质进一步分开 |

## 正式数据与未发布候选

| 数据层 | 机场 | IATA | ICAO | 来源 | 历史名称 | 数据版本 |
|---|---:|---:|---:|---:|---:|---|
| 本轮前正式数据 | 37 | 28 | 24 | 101 | 3 | 0.10.0 |
| 本轮后正式数据 | 37 | 28 | 24 | 101 | 3 | 0.10.0 |
| 独立验证的韩国身份候选文件 | 39 | 28 | 24 | 107 | 3 | 0.10.1（仅候选文件标签，未发布/未保留版本号） |

`data/airports.json`、Schema、发布快照、正式身份注册表和现有授权全部保持不变。候选文件的 +2 身份、+6 来源不计正式数据或生产覆盖。

韩国两个实际待入库 ID 由**未修改的现有身份规则**分配，并保存在现有锁保护的 pending 台账：

- 仁川：`apt_9afce57f-b42f-445f-85e2-5987e4f7db20`
- 金浦：`apt_2caa4ef2-6d58-434b-8de7-f5a33fa4b186`

真实 Owner 身份规则授权、竞争身份清单、原件与全部身份谓词通过；使用原有 `identity.allocate`、`release.materialize` 和 `release.gate` 生成候选，Schema/生产解析器验证通过。未生成完整发布回执。干净、精确 main 的原有 `release.prepare` 实际拒绝：

```text
Changed original lacks a fact-specific replacement contract: kr-history
```

98 个逻辑来源及恢复组件均实际读取并校验；97/98 项事实重放通过。`kr-history` 原件及规范化文本均变化，不能覆盖旧哈希或伪造替换合同。完整代码门与独立身份门的结果分开记录于 [admission-audit.json](admission-audit.json) 及 [identity-candidate/audit.json](identity-candidate/audit.json)。没有新建 Executor，没有继承旧授权到新代码。

## 生产解析器真实差分

[formal-resolver-diff.json](formal-resolver-diff.json) 调用现有 `policy_coverage.ts:measure()`，实际读取冻结正式快照、当前正式文件，以及已序列化的身份候选文件；没有把研究 pending 状态在内存中改成 verified 来制造数字。

- 正式比较：**187,738 个代码查询 + 161,542 个名称查询**，4,366 个本地日期。
- 日期网格：2015-01-01—2026-10-29，加所有已知边界及相邻日期；不是任意日期的穷尽覆盖率。
- 正式新增 resolved：**0**；uncertain 数量变化 **0**；既有正式答案变化 **0**；新增/消失冲突 **0 / 0**。
- 新解决同码跨场址复用 **0**；正式时间不确定区间缩小 **0**。
- 未发布身份候选的独立真实差分同样没有新增 resolved。身份已建立不等于已有代码日期覆盖。

## 有实质变化的历史判断

- **安康**：2014 环保部原批复明确旧场民航于 2010 年停航，2016 年官方访谈仍记载飞行学校活动；2018 年统计写的是“继续停航”。不能将 2018 当首次停航，也不能据此判物理关闭或代码撤销。
- **延安**：CAAC 原件记录 1981 年由东关迁至二十里铺；在二十里铺、南泥湾之外须保留更早场址，未将 ENY/ZLYA 倒填至东关。
- **连云港、宜宾、泸州、湛江、昆明、梧州**：补充旧新具名地理/行政/许可与代码关联原件；相对坐标、雷达坐标、气象城市代码、许可和开航日期均未当作代码分配。梧州长洲岛与常州市无关。
- **大兴**：开航前原件明确 PKX/ZBAD 已获批复；建设总结内部同时出现 PKX 2019-03-05 与 03-06，保留冲突，不虚构精确生效时刻。
- **锦州**：2015-12-10 为开航事件，原网页发表于 12-14；环评跑道参考点采用北京 54 坐标系，不能直接作 WGS84 ARP。
- **合肥**：从既有 HFE/ZSOF 线索选出的新案。CAAC 记录 2013-05-30 零时新桥启用与骆岗转场；没有写代码生效，不能直接设 HFE/ZSOF 边界。
- **名古屋**：中部机场官方早期编年明确 2005-02-17 0:00 承接 NGO 并供用；这是具名运营方的实际代码使用交接记载，不冒充 IATA 行政分配原通知。RJNN/RJNA/RJGG 仍独立研究。
- **石垣、下地岛、北九州**：补充官方旧新场址、ARP 和类型化 ICAO/IATA 对照。6 条 PDF 图形文字摘引单列为 AI 视觉核对的转录，绑定页图哈希，未冒充自动文本提取。
- **日本资料入口**：取得官方 AIS Japan 转 SWIM 说明、SWIM AIP 下载服务和使用条件；NDL 可定位 2005 年第 316/317/318 号历史修订。服务说明及书目不等于已取得历史 AIP。使用条件中的第三方、图件及用途限制单独保留。
- **Williston**：FAA 2019 年历史目录与 d-TPP 原件保留新旧标识并存，不能从新场启用推断旧代码撤销。直接“Ident (ICAO)”列与 FAA LID 分别记录。
- **St George、Austin、New Orleans**：DXZ/SGU 的 FAA 历史观察、KBSM/KAUS 气象变化分别保留；陈旧模型输入不当在力观察；MSY 航站楼搬迁不新建机场身份。
- **Doncaster**：2022-12-02 停航、12-12 证书交回，以及 2025-09-04 AIP 条目删除分开，未宣称代码当日撤销。
- **Berlin**：按各原件分别记录 2020-11-08 停止飞行运行及 2021-05-05 起法律效力；前一日午夜的许可表述不擅改成不同代码日期。
- **Munich、Murcia、Narvik**：搬迁夜、2019-01-15 商业开航及 2017-03-31 关闭分别保留。Munich 已取得原件与 Batch 5 同字节，未当新独立来源；ENAIRE 失效历史 URL 按错误页记录。

## 数据、权限与后续任务入口

- [backlog.json](backlog.json)：真实事件及场址去重后的统一清单；旧人工工作流文字仅作历史出处，当前任务采用 AI 自动补证及机器规则核验。
- [unit-crosswalk.json](unit-crosswalk.json)：原 60 单位的完整映射；[research-batches.json](research-batches.json) 按市场顺序自动拆包，每包不超过 20 案，无逐包审批。
- [source-lock.json](source-lock.json)、[original-verification.json](original-verification.json)：实际原件、自动提取/规范化、短引位置、视觉/HTML 属性引文各自表示、版权和来源谱系。原始 PDF、完整 HTML、全文提取、页图均只在 ignored `work/`。
- [new-findings.json](new-findings.json)：31 个实际跟进案例和一条额外发现线索的事实、日期种类、未知边界和具体缺件；研究资料未被计为正式覆盖。
- [source-rule-proposal.json](source-rule-proposal.json)：一次性、可复用的项目级来源/命题规则建议及明确谓词，全部为 `proposal-only`，不是已激活的政策或新 Executor。中国、日本、美国、欧洲的源授权不继承 AAI 或韩国授权。满足适用规则才可进入正式候选；其余自动保留候选及原因，不要求逐机场/逐批评论。

本轮未修改 `src/`、`scripts/`、Schema、工作流、依赖或授权绑定文件。只添加研究快照和轻量离线完整性测试；不增加审批或发布 Router。历史输入按其原提交回放，测试不要求后续当前数据永远等于 37 个机场。

正式数据日后通过适用规则更新并合并后，再用 Keepraw-Fly 已有 `scripts/update-airport-history.py` 同步；本轮没有 Fly 更新、合并、auto-merge 或 Release。

## 已执行验证

使用 Node 24、pnpm 10.14.0、Python 3 和现有 Poppler 提取器。

```sh
corepack pnpm validate:data
python3 -m unittest discover -s test/evidence -p test_priority_market_batch_6.py -v
corepack pnpm typecheck
corepack pnpm exec vitest run test/resolve.test.ts test/conflicts.test.ts test/validate.test.ts test/build.test.ts
corepack pnpm build
```

原件复核在本轮本地实际完成；公开 CI 只校验保留元数据、短引及回执绑定，不声称重新获取私有原件。新增测试验证历史输入、候选未正式发布、身份/代码分离和来源范围；不会对每次纯数据更新重复增加发布 E2E 或政策演练。最终提交的 CI、确定性生成和版权审计结果见 PR 正文及验证记录。
