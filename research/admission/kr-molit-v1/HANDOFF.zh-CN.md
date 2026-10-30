# PR25 中文交接：韩国独立准入适配器与授权准备

本轮从实时查询通过的 main `fdfdb02f46e543395d0cf3ad3f779aff26c47c90` 开发。
PR24 已合并；[main CI 41106518661](https://github.com/keepraw/airport-history/actions/runs/41106518661)
已确认 `completed / success`。开始时没有开放 PR，#25 尚不存在，也没有其他远端开发分支。
分支为 `feat/kr-molit-admission-adapter`。不合并、不启用 auto-merge、不创建 Tag/Release。

当前结论：**独立适配器和安全审批准备入口已实现，离线隔离演练通过；完整原件回放受阻，
尚不能宣称完整 Engineering ready。Identity approval pending / Policy authorization pending / Production inactive。**
真实生产身份、授权和正式 resolved 增量均为 0。

## 已落地的工程

- `scripts/admission/kr_adapter.py`：精确版本选择、独立 Policy/Scope/Executor 绑定、真实 GitHub 评论验证、
  身份批次准备、政策授权准备与受控代码分配提案入口。所有输出限定在新的 ignored `work/` 子目录。
- `kr_evidence.py`：从锁定输入重新计算 AIRAC 日期窗口、普通修订控制、机场 NOTAM 生命周期和官方清单集合，
  检查 FIR 分段、重复原文字节、多部分通告、SUP 关联。生产模式实际读取原件、重提取、核对引文及原始图关系。
- `kr_resolver.ts`：调用真实 `assertDataset()` 和 `resolveAirport()`，检查正式记录不变、来源关联、
  37,736 次正式回归、全部条件候选和相邻日期边界，拒绝既有代码改写或 IATA 扩展。
- `kr_rehearsal.py`：一次性副本中的真实身份 gate、韩国准备路径和解析器演练；第二个无注入进程必须拒绝测试权限。
- `kr_verify.py`：905 个基线文件保护、工程回执与逐查询生产阻塞状态检查。
- 新增 32 个 Python 测试和独立 CI 工作流。保留现有 CI、package.json、印度执行器及授权的全部原始字节。

本实现没有把韩国 policy_context 送进印度 `validate_admission()`。物理身份准备使用原函数的人工审批路径；
韩国政策提案使用独立入口，并复用原 Schema、语义和解析器。政策审核不冒充人类逐条阅读。
独立入口是可执行代码，不是返回预期结果的 resolver 替身。

## 精确绑定与范围

生产政策选择符：`kr-molit-bounded-icao@1.0.0`。

| 绑定 | SHA-256 |
|---|---|
| Policy | `9b183f6d46804cfac4e75e26bedaba7109ad851a2ce95ac118952da81e4734a8` |
| Scope | `1d0a8a5231195cdc96aceeabd9415a8f55f76015b62907cf29f838f5be7e11a6` |
| Executor | `3d72d046a8ec0d964ceae438c9a7b37fb14478c3e0d52ca295d7a8bebdfaa6e0` |

完整清单见 `bindings.json`：69 个逐字节执行/Schema/依赖锁文件，以及完整 package.json 的规范化 JSON。
Policy 还冻结 97 个证据文件，包含实际引用的旧来源锁、最小引文及原机场账本输入。
每一个受绑定文件改变都会使旧 Executor 不匹配；Policy、Scope、永久身份映射也分别绑定。
PR24 的研究 Policy/Scope/Executor 原值保留，不继承其 Executor，更不继承印度授权。

当前范围只含 KR / KR-MOLIT-AIP / aim.koca.go.kr / ICAO / RKSI、RKSS /
`[2025-04-18, 2025-05-15)`，每场 27 个完整本地日期。
代码从受控外侧 AIRAC 生效时刻重新计算本地完整日期；不是把 54 个结果写成永远成立的结论。
2025-05-01 普通 AMDT 的精确钟点仍为 null，不能套用 16:00 UTC。
未知政策版本默认拒绝；扩展机场、国家、日期、发行体系或证据内容都需新边界、新绑定与新授权。

## 两类人工审批入口

身份批次仍为 `kr-incheon-gimpo-physical-identities-1`，SHA-256：
`1bf46a730f0f1f750e3479bdfe032e653b6b2c63e113aa6eae908bff3948722c`。

仁川 ARP `372745N 1262621E`、金浦 ARP `373325N 1264751E` 分别校验。
两场均未批准、未分配永久 ID、未正式入库。NOAA 只支持附近位置，不替代精确 ARP。

`identity-text` 输出 PR24 已锁定的准确身份审批文本，不代表实际批准。
`prepare-identities` 必须从真实 GitHub 评论重新取得登录名、用户 ID、账号类型、仓库所有者、评论原文、
对应 issue/PR 和时间戳，并核对批次哈希与原件，才能新分配 UUID。
它输出两个逐记录 dossier 和一个统一批次，通过原有人工身份 admission gate；不会写入正式文件。
模拟 ID、测试 principal、JSON 中的 `approved=true` 均不能替代此条件。

`policy-text`、`record-policy` 是独立的韩国政策入口：必须先存在已正式批准的两个永久身份；
政策文本绑定精确 Policy/Scope/Executor 与身份映射哈希。
还必须从 GitHub 的同一个 main Commit 重新读取正式数据库和身份登记，拒绝未合并工作树中的身份。
当前调用会因缺少永久身份而拒绝，不生成模拟授权文本或登记。
`admit` 每次重新取得两类批准，拒绝评论修改、错误身份、哈希漂移和原件缺失。
身份批准不批准代码、历史名称、日期区间或政策；政策批准不能创建身份。

## 演练结果与实际限制

`verification.json` 来自真实隔离运行：

- 正式 37,736 个代码/日期查询改变 0，正式新增 resolved 0。
- 原身份人工 gate 通过；条件韩国候选 **54/54 resolved**，前后相邻日额外 resolved **0**。
- 测试身份、权限和 ID 只在临时副本；实际生产进程拒绝测试权限，提案目录不存在。
- 9 项隔离负面检查拒绝测试 ID、错误身份、不同场址、冲突 ARP、缺身份批准、缺政策授权及三类绑定漂移。
- 另有 32 项测试覆盖假作者、错仓库/评论/原文、错误 Scope、IATA、未知修订、PERM/EST、缺前身、
  不同原文字节、缺多部分、机场关闭与局部滑行道事件、截断和缺失原件等。

以上采用锁定证据的**离线回放**；注入的证据依赖也明确返回 `originalBytesReadHere=false`。
没有把离线回执标成现场取得原件，更没有把测试权限标成真实 Owner 授权。

本轮真实尝试恢复 98 个锁定组件：**86 个原字节匹配、6 个漂移、6 个无法取得**。
结果逐项见 `original-recovery.json`。漂移包括机场/FIR 历史查询及动态 NOTAM 页面；
无法取得的项目包含四个逐号 checklist 查询、IIAC 位置页和当前 SEL 页面。
未覆盖旧哈希，也未保留漂移响应到公共仓库。
已实际读取/提取 86 个精确组件，并检查 17,234 条原始 NOTAM 的文本/接口字段，矛盾数为 0；
最初发现的 36 个多部分编号后缀案例已修复，见 `partial-original-verification.json`。
实际 `kr_verify.py originals` 在缺失原件处失败，不能用 PR24 的成功回执替代。
`status.json` 对每个候选日列出身份、授权和完整原件回放阻塞。因此不宣称 Engineering ready。

当前取得的普通 AMDT、AD、SUP 和多数 FIR 组件提供精确恢复支持，但不能升级为 2001 年以来完整历史覆盖。
若原锁字节无法再取得，最小安全后续是独立新版本证据包及复核；不能改写 PR24 或放松生产原件条件。

## 正式发布接入还需要什么

安全的人工审批**准备**入口已经存在；真实批准来源仍不存在。
未来实际身份 PR 还需把新版本正式 bundle 回放接入发布检查，保持印度冻结 bundle 的独立校验。
既有 `pnpm validate:admission` 仍检查印度 0.10.0 正式 bundle，不能声称简单替换正式数据库就已完成韩国发布接入。
这是明确的最小后续工程，不用模拟文件掩盖，也不取消印度哈希检查。
当前 `kr_verify.py` 是未激活版本的检查器；正式授权/身份进入仓库时须随相应人工审核 PR 更新版本状态和回放入口。

下一步先恢复完整锁定原件或审查新的有界版本，再由所有者单独审阅统一物理身份批次；
随后准备实际身份入库 PR、新永久 ID 与发布回放。身份正式存在之后，才生成并审阅精确韩国政策授权文本。
合并本 PR 只接受未激活代码，不等同于上述任一批准。

## 数据、版权、Git 和复现

全部 905 个已有文件前后逐字节相同。正式版本 **0.10.0 / Schema 3.0.0**：
**37 机场、52 分配、101 来源、3 历史名称**。印度政策、真实授权、生产执行器、旧研究快照和永久 ID 不变。
Keepraw-Fly 未修改。

完整网页、PDF、NOTAM 原文、数据库响应和提取只在 ignored work/；公开恢复报告只含 ID、哈希及结果。
暂存文件、新增可达 Git blob 和必要祖先需经过现有 `korea_readiness.py rights` 审计；Ignore 不是历史清洁证明。
该检查不宣称旧远端对象已删除，也不建立全文再分发许可。

普通 Author/Committer 均为 `keepraw <49091395+keepraw@users.noreply.github.com>`，
`git config --local user.useConfigOnly true`。提交与 PR 使用英文；最终 Head 的 CI 以 PR 正文和最终报告为准。

复现命令及未来入口见 README；本地最终测试、版权审计和最终 CI 必须以实际运行结果报告，不能引用中间提交替代最终 Head。
