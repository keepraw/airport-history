# PR #22 本地验证与证据版权记录

- 基线：`c712cefcc0b058880b1f21ee728d3cdc8c5ceea7`；PR #21 合并后 CI `41010806134` 两任务最终成功，建分支前已核实。
- `pnpm check`：437 个 TypeScript、50 个发现研究、15 个参考库、96 个证据测试全部通过；包含新增 10 个市场适配器反例／边界测试。正式 Schema、准入回放、来源、政策、既有研究验证与 0.10.0 构建通过。
- 第一次受限环境运行中的两个既有 `spawnSync EPERM` 用例，在允许子进程的环境中保持原测试不变重跑后通过。
- 独立 `pnpm evidence:priority-markets validate`：6 个生成产物离线重算一致；22 个真实语料请求结论一致；301 个基线文件哈希保持；当前候选按生产解析器对比正式 0.10.0。
- 最终增量适配器 10 测试及 TypeScript typecheck 再次通过；原件独立复验覆盖 29 原始组件、29 原始字节流、78 个短引用（含 PDF 物理页和精确偏移）。普通 CI 不重新抓取原件。
- `pnpm policy:rehearse`：完整隔离候选检查通过；生产拒绝 ID 0 的测试授权；实际正式数据和生产授权文件保持不变。该流程明确为离线原件回执回放，`originalBytesRecheckedHere=false`。
- 原印度 executor SHA-256 仍为 `2415279526ff8c0eaf9ee1b3ee5afca8bde26e95bfac2c98930212f9f7992a3f`；原政策 SHA-256 仍为 `3c606e60766f0ec89090e2b382939da67be00a7e9070aefc7568fe5559e05958`。
- 正式新增 resolved=0；现有回答改变=0；conflict 新增／消失=0。韩国内存假设 54 resolved／8,678 uncertain 单独报告，未写入正式数据。
- `git diff --check` 通过。Author／Committer 均配置为 `keepraw <49091395+keepraw@users.noreply.github.com>`，`user.useConfigOnly=true`；提交后再次检查身份。

## 版权和保管边界

本轮仅提交元数据、哈希、URL、权利评估及最小事实引文。全文 HTML／PDF、完整提取、搜索响应、调试脚本与凭证均不进入提交。FAA 仅引用机构正文事实，未取得或假定第三方附图、商业附件的再分发授权。其余原件均不声称获得完整再分发许可。

`pnpm evidence:priority-markets rights` 在既有完整可达历史审计之外，额外加入本轮 29 组件的原始字节／提取／规范化全文哈希，检查暂存文件及基线后的历史新增 blob，防止新全文以纯文本或其他路径进入历史。它是机械内容门禁和逐来源短引审查，不是完整出版物的版权许可。

既有审计中远端旧对象的可访问性记录保持原样；本轮没有重写历史、删除远端对象或声称它们已不可访问。最终 head 的 PR 链接、SHA、CI 和提交后版权审计结果记录在 PR 正文及最终中文交付报告中。
