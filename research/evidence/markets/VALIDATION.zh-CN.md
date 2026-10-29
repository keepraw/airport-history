# 本地工程验收（2026-10-29）

完整 `pnpm check` 通过，使用 Node 24 与仓库固定的 pnpm 10.14.0：

- TypeScript：16 个测试文件、417 项测试全部通过。
- 历史研究：50 项；参考数据：15 项；证据：39 项，全部通过。
- 正式 schema、数据、admission gate、离线构建全部通过。
- 新市场、旧全球阶段均完成禁止联网条件下的逐字节离线重建。
- 60 份本轮引用的完整原始字节 SHA-256、完整提取文本 SHA-256、77 个引用位置已在本地原件上核对，见 `original-verification.json`。公开离线包验证保留引用，不声称用短引用重构完整受保护原件。
- `git diff --check` 通过。

相对本轮起点 （提交指纹 `0ca52e94ce6eca4f0af5ca4ac85fe7ff05902414ae75f70bfe20f93b10bd4bcd`；算法见历史审计），以下内容无差异：正式 `data/`、`test/curated-0.8.0.json`、PR13 direct 证据与提案、上一轮全球事实判断、全球 proposed-data 和查询覆盖。PR11–13 的冻结研究也通过原有重建验证。

正式版本仍为 0.8.0：27 个物理机场、43 条代码分配、3 条历史名称、77 个来源。构建产物 SHA-256 为 `b768275e886be0d6094bf8d4aa2c1ac13a932ad532b9f3354d08f9e194981907`。

所有新事实和记录均 pending，reviewer=null。真实 admission gate 仍拒绝提案。KSGU、KDXZ、KXWA 的旧阻塞未解除。内存批准假设下，Murcia 双侧代码有限窗口可解析；边界日与中国关联记录保持 uncertain。已发布 resolved 结果改变为 0。

本地 Author、Committer 均检查为 `keepraw <49091395+keepraw@users.noreply.github.com>`。最终远程提交的 GitHub 用户映射、精确 Head CI 和 Open／未合并状态在 PR #15 说明与最终交接报告中核验；本文件不提前宣称远程检查成功。
