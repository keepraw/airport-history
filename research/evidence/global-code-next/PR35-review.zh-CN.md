# PR #35 针对性最终合并审查

审查对象：`90b3b5e014168c22a934e716eac3cc1890b5c67a`，已发布基线 `7d21ff6762e1569faa1be19c8203e577420cd1f2`（0.11.0）。只读检查现有代码、数据、原件缓存、收据及最新 GitHub 作业；未下载资料、重跑全球索引或完整历史 CI，未修改任何发布文件。

**结论：未发现阻止合并的实际问题，建议 PR #35 可以合并，由 Owner 作最终决定。**

## 核查结果

1. **授权和执行器未扩大。** `global_code_admission.check_inputs()` 本次针对性调用通过。`official-aip-bounded-icao@1.0.0`、既有授权注册表与绑定执行器一致；执行器 SHA-256 为 `2415279526ff8c0eaf9ee1b3ee5afca8bde26e95bfac2c98930212f9f7992a3f`。授权继续限定 AAI、指定 archive URL、ICAO、有界连续性、稳定名称／ARP、至少两观察和两原件、未知外边界及原有升级条件。没有继承中国或韩国授权。参见 `scripts/evidence/global_code_admission.py:43`、`:56`、`:58`、`:65`。

2. **确定窗口正确。** VANM、VEAY、VOSH 均采用 2026-06-11 与 2026-07-09 的受控版本观察。旧分类器 `scripts/evidence/policy_review.py:251` 以首次观察次日起至末次观察日前的半开区间生成 `[2026-06-12, 2026-07-09)`，每条 27 个完整本地日期。六份 AD 2 的名称和 ARP 成对一致，版本组件日期与发布时间不被冒作分配日期。三条记录的外侧边界仍为 null。数据位置：`data/airports.json:2820`、`:2844`、`:2868`。

3. **既有记录完整保留。** 对 airports、assignments、sources、names 做逐集合前缀深比较全部通过；冻结 0.11.0 数据 SHA 与 `git show 7d21ff:data/airports.json` 完全一致。旧永久 ID、代码分配、来源和历史名称没有修改。0.12.0 数据、冻结快照与准入 bundle 的 SHA 均为 `4573fb7e6fac8e02c8e3f57443599385dffada17b250a29f1a18964f6d6d8cc9`。

4. **13,017 个 uncertain 增量不是 resolved。** 既有固定测量包含 4,366 个本地日期；三新代码各有 27 个 certain 日期，其余 `3 × (4,366 − 27) = 13,017` 为 not_found→uncertain，符合 `src/time.ts:11`、`:23` 的未知边界语义。它们只表明日期证据不足，不证明这些远期历史日期的代码实际存在。旧 uncertain、旧 resolved 答案及冲突没有变化。收据见 `research/admissions/0.12.0/coverage.json:6`、`:202`。

5. **隔离回放没有绕开原准入门。** helper 限定十三个数据／最小引用覆盖目标，拒绝脚本、schema、政策与授权的替换，并校验每个输入哈希（`:68`–`:83`）。临时 checkout 固定真实发布基线（`:93`–`:95`）；先重放中国旧身份包，再恢复限定数据，调用未修改 `policy_formal.py`（`:110`）。该 CLI 继续调用原 `review.py validate`；原 `policy_gate.validate_context()` 重新查授权、执行 evaluate、比较整个预期 proposal／batch／dossier／receipt，并验证离线原件收据。helper 没有 monkeypatch 授权、原件验证或分类器。回放结束重新核对原执行器和输入（`:112`–`:116`）。

6. **原件、版权和构建收据一致。** 六份 AD 2 加一份 GEN 0.2 原件的保留缓存 SHA 本次都与原始核验收据及 overlay 来源锁一致；未重新获取原件。收据明确区分真实准备阶段 private original replay 与 CI offline receipt replay。公开资料仅含事实、必要短引文和哈希，未声称获得完整原件再分发权；`rights-audit.json` 明确 `fullRedistributionPermissionEstablished:false`。现有两次逐字节相同构建收据与当前六个 dist 产物哈希全部匹配。没有为本次审查重复完整构建。

7. **最新远端 CI 全部成功。** 本次读取四个工作流的最新作业，均 completed/success：
   - CI `42462009254`：check、policy-admission-rehearsal。
   - Worldwide ingestion `42462009243`：materialize-worldwide。
   - Rule-based identity `42462009251`：isolated-rule-engine。
   - Korean adapter `42462009261`：inactive-adapter。
   未触发重跑。

## 本次小规模生产探针

直接调用未修改的 `resolveAirport()`，检查三个代码在 2026-06-10 至 2026-07-10 的 93 个代码／日期，以及九个外部历史日期：81 个窗口内结果均 resolved，12 个相邻／观察日均 uncertain；九个区间外日期也均 uncertain。0.11.0 对相同新代码日期为 not_found。此检查复核日期边界，不重新执行整份 200,836 查询的历史测量。

## 发布状态与后续条件

这仍是 0.12.0 **未合并提案**：新增可信 ICAO 关系 3，提案 resolved 增量 81，not_found→uncertain 增量 13,017；IATA、跨场址复用解决、不确定区间缩减均为 0。main 实际新增覆盖仍为 0。

PR #35 尚未合并，Fly #114 应保留等待。GitHub 在未合并时也可能提供预计算的 `merge_commit_sha`，不能把它当成真实发布合并。必须在 `merged:true`、真实合并提交可达 main 且该 main CI 成功后，才以该真实合并提交更新 Fly；不得用 PR HEAD 或预计算 merge ref 制作正式 0.12.0 包。
