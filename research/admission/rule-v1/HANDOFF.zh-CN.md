# PR26 中文交接：规则级身份准入与版本化证据

本 PR 是可执行的工程实现。正式库仍为 **0.10.0 / Schema 3.0.0 / 37 机场 / 52 分配 / 101 来源 / 3 名称**。真实韩国永久身份、真实新增授权、正式 resolved 增量均为 **0**。没有发送 Owner 授权评论，没有合并、auto-merge、Tag 或 Release，没有修改 Keepraw-Fly。

开发前核实 main 为 `a852596869d7ae157ef53fdf236ffbdaff5508c8`，主 CI [41162122068](https://github.com/keepraw/airport-history/actions/runs/41162122068) completed/success 后才建开发分支。923 个原有文件全部保持原字节。

## 逐项回答验收问题

1. **可以通过一次身份规则授权覆盖两机场，无需逐机场批准。** 真实官方原件下仁川、金浦均为 AUTO_ELIGIBLE。规则授权缺失时在 UUID 生成前拒绝；真实授权仍未取得。身份规则不包含 RKSI/RKSS 名字白名单。
2. **身份规则可覆盖其他合格韩国机场。** 独立来源目前限定经审查的 IIAC/KAC 自有场址资料；候选须具备相同形式的受控观察、完整修订、机场通告和场址竞争证据。8 个明确标记的合成机场批量测试通过。韩国代码 v2 仍只覆盖 RKSI/RKSS 的既有 27 天研究窗口；不能把它称为全韩国代码授权。扩展代码证据/Scope 需要相应规则版本和授权，不需要逐机场身份特批。
3. **增加新国家的独立模块不会自动破坏既有授权。** 新 Executor 使用显式传递依赖闭包；无全目录自动扩张。印度与韩国 v1 原 SHA 均保留。修改共享依赖时，受到影响的规则必须重新授权。正式发布验证在冻结历史树上运行旧验证器，再验证新候选，保留历史授权的实际适用版本。
4. **12 项必要事实阻塞解除 12 项；旧 12 份精确字节恢复 0 份。** 新版本完整回放 98 个逻辑组件、160 个单独取得的原件组件，解析 19,639 条 NOTAM。当前版本有 83 个逻辑组件仍精确匹配旧原件，其余使用新原件或透明分拆集合。旧 v1 精确字节路径仍受旧限制，未更新它的 SHA 或冒充它成功。
5. **已建立版本化原件机制。** 私有 SHA-256 CAS、创建时排他写入、读时重新哈希、独立 UTC 观察时间、原始 URL、父版本哈希、逐事实重验证与候选 bundle 绑定。公开提交三个不可变元数据版本，不提交完整 PDF、网页、API 或 NOTAM。组合清单保留每个官方单条响应的独立哈希；派生集合从不伪装成原件。
6. **真实原件端到端隔离演练通过。** 正式代码流程、两次真实 Schema/不可变关系/解析器门禁、独立代码审核、bundle 重放、重复批次和 PR 准备均在可丢弃副本运行。只替换授权/已发布主线/待审分支的外部依赖为明确测试主体；真实原件及物理风险谓词未替换。清洁生产进程拒绝序列化测试授权。没有使用模拟授权创建真实数据 PR。
7. **54/54 个韩国条件结果成立。** 两机场各 27 天，`[2025-04-18, 2025-05-15)`；没有额外边界日期、没有 ICN/GMP 正式推断。37,736 个正式回归查询答案不变。实际调用未改动的 `resolveAirport()`。
8. **正式数据及既有授权完全不变。** 923 文件逐哈希保护，印度 Executor `2415279526ff8c0eaf9ee1b3ee5afca8bde26e95bfac2c98930212f9f7992a3f`，韩国 v1 Executor `3222018573f8204dbed40df839cc64dd1e69e29b490d3fbb2b225bac3f473a6a`。正式构建 SHA-256 `03b267486089a2a5ade9f3d4ff7949603d198e04c718f7c9f6bc84cbef5ab61f`。
9. **新增精确绑定如下。** 所有字段均由机器重算，并由未来真实 Owner 评论精确绑定；这些 SHA 不是授权本身。
10. **当前两机场还需 2 次独立规则级授权。** 一次身份规则，一次韩国代码 v2；可在同一授权登记 PR 汇总。身份授权没有机场名单/批次数量限制。不会把印度或韩国 v1 的授权继承到新规则。
11. **异常自动分三类并去重。** AUTO_ELIGIBLE 保留可准入证据；迁址、竞争/重复场址、同码异址、历史场址重用、名称/ARP 冲突、未闭合重大通告进入 MANUAL_REVIEW；缺必要原件、日期/修订控制不明、来源不独立或无法复现进入 INSUFFICIENT_EVIDENCE。稳定任务键保留证据修订，不因每日重跑生成相同任务。完整批次在第一个 UUID 生成前做交叉竞争检查。
12. **第一批真实数据 PR 还需：** 本工程 PR 人工合并；两份真实规则授权按精确文本登记；在生产工作区持久保存私有 CAS 或重新取得并重验证合格新版本；基于最新 main 重新检查正式/待审/历史场址、完整原件、Schema、解析器及版权；运行生产 submit。系统读取其他待审批次身份登记以跨工作区复用 UUID，提交前核对 main lease，并以稳定批次分支避免重复 PR。最终仍由 Owner 人工合并。

## Policy / Scope / Executor SHA-256

| 规则 | Policy | Scope | Executor |
| --- | --- | --- | --- |
| `official-aip-stable-physical-identity@0.1.0-draft` | `1de275a7baeb1b1216190d7f5e1b2b09ebe7449e5a117ad1f98af9247efd80ee` | `597ddbc5afeb66df29bf7dcb405846e9ac912ae4bfa93bfd2b71c24a6c8b4e65` | `ec8ad19d6739cc5900eb2753e54c43ea0c37d06a428971651d061269f2664619` |
| `kr-molit-bounded-icao@2.0.0-draft` | `37e01b54bcf28f4d25a5e49b04f5905d3b107de132e4d4b5d9da062ba7024350` | `ca29502a69df9e8283fbdfddd0022be6988054336caacdb57f1b2076b555e413` | `ec8ad19d6739cc5900eb2753e54c43ea0c37d06a428971651d061269f2664619` |

新 Manifest 版本 2 绑定 181 个显式文件。仅 `package.json#/version` 为规则明确允许增加的发布变量，其余 package 值完整绑定；数据版本增长不会重新解释旧 Executor。任意旧内容地址下的原件变更仍失败。合法的新证据版本必须生成新哈希、重新证明事实、重算窗口并绑定新 bundle；它不是一次隐含扩权。

## 旧 12 项原件阻塞明细

| sourceId | 新版处理 | 剩余事实阻塞 |
| --- | --- | --- |
| kr-notam-rksi-available | 新官方 API 响应；重新证明窗口内 51 条通告及清单覆盖 | 无 |
| notam-ui | 新官方 UI；规范化文本相同，协议引用重验证 | 无；仅当前查询协议，不是历史快照 |
| notam-valid-ui | 新官方 UI；规范化文本相同 | 无；不支持历史分配 |
| notam-all-rksi | 完整新响应 1,622 行；历史窗口、生命周期与 outstanding 集合重算 | 无 |
| notam-all-rkrr | 9,999 行截断响应仅作诊断；正式覆盖改用全部完整 FIR 分段和六份官方清单 | 无；不声称完整全时段查询 |
| notam-fir-early | 新官方 1,385 行；合并其他分段重新计算历史窗口 | 无 |
| checklist-z0471-25 | 12 份单条官方查询原件，逐个哈希并重建清单集合 | 无 |
| checklist-a0478-25 | 14 份单条官方查询原件 | 无 |
| checklist-z0384-25 | 23 份单条官方查询原件 | 无 |
| checklist-a0351-25 | 14 份单条官方查询原件 | 无 |
| iiac-location | 新官方运营方页面；自有机场/运营地址重新验证，与 AIP 同街道/地点关联 | 无；不声称独立精确 ARP |
| iata-seoul-current | 新官方页面重验证 SEL 为都会区的当前事实 | 无；不用于历史机场身份或代码日期 |

重试还取得了最初超过下载上限的 111,077,190 字节官方 AIP AMDT 5/25 PDF，并拆分本次新超时的 G0304/25 清单。没有只对旧 12 项打补丁，其余组件也重新验证。新研究发现旧金浦名称摘要和 AD 2.1 原件拼写不同；新候选采用 `SEOUL / GIMPO International`，旧证据不改写，也不把元数据修正解释成历史改名。

IIAC/KAC 页面仅以自有资产地址事实计算为独立上游；MOLIT 的多个发行页面只计一个发行体系。Gimpo 的 Haneul-gil/하늘길、Gangseo-gu/강서구、Seoul/서울시 对应是明确政策参数。NOAA 位置不能替代独立运营方场址资料。ARP 容差 30 米、观察间隔上限 28 天、永久/待审重复场址搜索 100 米、参考记录附近匹配 2,000 米均为待 Owner 精确批准的规则参数。

## 可运行入口

```sh
# 当前 inactive 发行完整性；不取得原件，也不冒充原件重放
python3 admission/v1/verify.py
python3 admission/v1/test_engine.py

# 实际取得新版本原件；保存私有 CAS 和新清单，旧清单不覆盖
python3 admission/v1/evidence.py acquire
python3 admission/v1/recover.py work/rule-admission/versions/<version-sha256>.json
python3 admission/v1/korean.py --manifest work/rule-admission/versions/<version-sha256>.json

# 真实原件 + 明确测试授权，仅在可丢弃副本；不提交真实数据 PR
python3 admission/v1/rehearse.py --manifest work/rule-admission/versions/<version-sha256>.json

# 生成未来 Owner 应精确签署的规则文本；本轮没有发送这些评论
python3 admission/v1/authorize.py text --rule identity
python3 admission/v1/authorize.py text --rule kr-code
# record 必须实时读取真实 Owner 评论；仅输出 ignored work/，不改生产登记
python3 admission/v1/authorize.py record --rule identity --comment-url <owner-comment-url> --output work/identity-grants.json
python3 admission/v1/authorize.py record --rule kr-code --comment-url <owner-comment-url> --registry work/identity-grants.json --output work/both-grants.json

# 两份真实授权正式登记后才可能执行；目前生产 prepare 必然拒绝
python3 admission/v1/release.py prepare --manifest work/rule-admission/versions/<version-sha256>.json --data-version <new-version> --bundle work/<new-bundle>
python3 admission/v1/release.py validate --bundle work/<new-bundle>
python3 admission/v1/publish.py plan --bundle work/<new-bundle> --output work/<new-plan>
python3 admission/v1/publish.py submit --bundle work/<new-bundle> --output work/<new-submit-plan>
```

`submit` 用真实评论再鉴权、重读私有原件、验证 main lease、在临时 Git 分支生成一个批量候选提交、运行 staged 版权审计和版本化发行检查，最后创建待人工合并 PR。它没有合并、auto-merge、Tag 或 Release 路径。规则文本和登记机制独立于候选身份，不需要逐机场审批。提交传输本轮未向 GitHub 发送正式数据：隔离验收到实际 PR plan 为止。

生产 prepare/plan 还要求 HEAD 精确等于已发布 main，且所有非 ignored 文件均无本地修改或未审查新增；参考库/历史场址资料不能通过修改本地工作树绕过竞争审查。私有 work/ 原件与候选输出不受此门禁妨碍。

未来正式候选 PR 会随数据提交审查过的 CI 路由模板，避免旧验证器在新工作树误套旧哈希。旧 `pnpm check` 在各自冻结历史树执行；新 bundle 独立检验扩展，历史链可递归重放。公开 CI 没有私有 CAS，只报告结构、来源关联、不可变关系和真实解析器的离线验证范围；发布准备/提交必须另行完成私有原件重放。

## 已完成的验证

- 完整 `pnpm check`：437 TypeScript、50 discovery、15 reference、146 evidence，合计 648 项通过。
- 新引擎 22 项测试通过；含 8 个合成机场、缺身份/代码授权、精确 Policy/Scope/Executor 改动、原件篡改/缺失、独立性、完整修订、批内/历史/待审竞争、跨工作区待审登记读取、异常去重和完整离线隔离链。
- 实际印度 `pnpm policy:rehearse` 通过，含完整候选 `pnpm check`；仍明确是离线原件回执回放。
- 韩国旧路径仍通过；新真实原件隔离链通过，54 条条件结果、37,736 正式查询不变、额外边界 0、测试授权被正式进程拒绝。
- 新版全部 98 组件事实原件重放通过；源码、登记、数据和三个证据元数据版本可独立校验。
- Git 可达历史和 staged 版权审计在提交前/后执行，结果见 PR 描述；完整原件仅在 ignored `work/`。

这些结果不代表已经取得真实授权、已经发布韩国身份或已经创建韩国正式 resolved。当前唯一待合并成果是工程开发 PR。
