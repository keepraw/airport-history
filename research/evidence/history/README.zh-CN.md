# PR #15 原件与公开定位符历史审计

曾审计 92 组第三方完整响应与全文提取，共 184 个 Git blob，包含 7 个错误响应。现有证据未明确建立全文再分发许可；公共互联网可下载不等于可以复制到本仓库的 MIT 许可下。完整响应和全文提取继续排除，合法来源 URL、标题、必要短引用及真实 SHA-256 内容完整性信息保留。正式 0.8.0 数据、全球调查、60 组市场调查及跨场址补证的事实、边界、永久 ID 和 pending/reviewer=null 状态未改变。

原公开审计曾列出旧 Head、旧提交、逐文件 Git blob SHA-1、出现提交、API 复核对象、force-with-lease 旧期望值及带旧提交前缀的本地备份名称。其他市场/补证元数据也重复了旧提交定位符。这是已发生的公开暴露；本轮保留该事实及统计，不以格式迁移掩盖。

[公开审计清单](pr15-rights-audit.json) 的 formatVersion 2 只用独立命名空间的确定性指纹比较受限对象：

- blob：`SHA256(ASCII("restricted-git-blob-v1") + NUL + ASCII(normalizedSha1))`。
- commit：`SHA256(ASCII("restricted-git-commit-v1") + NUL + ASCII(normalizedSha1))`。
- normalizedSha1 只去除两端 ASCII 空格、tab、CR、LF，转为小写，严格要求 40 个 ASCII 十六进制字符；输出小写 64 位十六进制。拒绝缩写、Unicode 替代字符及无效输入。

逐文件保留原路径、来源、许可未明确的结论、原始/压缩 SHA-256、出现提交指纹和已移除状态。旧对象标识没有截短、Base64 编码或改为其他可逆形式；精确旧标识、旧 API URL 和原始审计只存于被 Git 忽略的本地私有所有者资料。指纹不是保密机制，不能删除 GitHub 对象，也不能确认许可。

逐提交复核发现，前次清洁快照和后续审计提交仍通过文件树公开旧定位符。只新增删除提交会保留可达定位清单。因此本轮保留本地私有备份，从未改动的 main 建立一次清洁快照，并以普通后续提交固定快照提交/树。推送必须再次核对远端，并使用明确旧 Head 的 `--force-with-lease`。这次例外仅整改历史元数据；不持续重建分支来假装删除服务器对象。前两次 PR 提交以 `locatorExposureCommitFingerprints` 单独记录和拒绝，不把它们误称为含原件的提交。新清洁提交及 main 可以保留正常 Git 标识。

`pnpm evidence:history` 不依赖私有清单或缓存。它拒绝浅克隆、缺失祖先/树/blob 和 graft 历史；枚举 Head 的完整祖先及相对 main 的全部新提交；逐个检查完整树和提交消息，检查 184 个已知 blob 指纹、3 个原件提交指纹及 2 个旧定位符暴露提交指纹。相同 blob 改名、只从最终树删除、合并侧祖先仍会被拒绝。它还读取公开来源锁的完整原件/提取 SHA-256，检查实际字节及 gzip/bzip2/xz/ZIP/TAR 成员、JSON 字符串和 PDF/HTML 内容，阻止换压缩或扩展名重新加入已知全文。新增第三方出版物仍需逐来源人工权利与引用审查，机械检查不等于普遍的许可判定。

市场历史快照的 `baseCommit=null` 配合 `baseCommitFingerprint` 表示原阶段起点已退役；没有用 main 冒充旧研究基准。补证包用 `originalSnapshotBaseCommitFingerprint` 保留该出处，正式 replay base 仍是既有 main。仅相关包和依赖 manifest 按现有构建器重建；旧研究事实、引用和所有待审判断保持一致。既有离线逐字节重建、冻结历史、实际解析器及入库负向测试继续执行，PR #11–14 的已合并祖先和正式记录不重写。

**当前 PR 祖先清洁与 GitHub 服务器旧对象可访问性是两项独立结果。** 本轮代表性只读 API 复核仍可读取旧提交及旧 blob，公开清单如实记录 `remoteOldObjectsStillAccessible: true` 和复核时间。`evidence:history` 只报告这一份有日期的远端证据，不声称每次运行都访问 GitHub，更不据祖先清洁推断远端删除。

本地 Support 资料包含仓库标识、时间线、精确对象清单、API 复核和待评估范围，仅供所有者决定是否提交。可请 GitHub Support 评估旧提交、blob、历史清单、PR 引用和缓存；不假定其支持全部清理，不断言已构成侵权，也没有发送 Support 请求。PR 保持 Open、未合并且关闭 auto-merge。
