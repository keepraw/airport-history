# 欧洲与中东代码研究：首轮批次

本包实际审查 34 个规范事件组、15 个国家。按全量最终排名，23 个属于高价值层级，其中 **21 个取得并检查了本轮原件或既有锁定证据**；另外 2 个高价值事件在取得官方原件前受阻，不计入这 21 个。初选队列留下的 11 个较低优先级后续案例单独保留，不计入高价值目标。事件组分成 20 和 14 个的两个 review batch；关联目录观察不增加调查数量。

最终主事件选择有两项复核：Maku 和 Duqm 分别选用同一 reference、同一机场代码的高价值组，原来初选的坐标/标签变更组保留为关联 ID。它们各计一次调查。没有把目录坐标变化直接认定为迁址。全量排名和每个事件的具体理由见 `assessments.json` 的 `globalRanking` 与 `selectionReason`。

取得并保留了 10 个出版者家族的 13 份不同字节原件，另有 5 个官方获取目标失败；检查了 20 项既有研究来源收据，没有重新获取这些已锁定原件。新取得的 21 条 ICAO 代码与具名机场观察，均与代码分配边界分开记录。完整原件与全部提取文本只留在 ignored `work/`；公开文件仅包含来源元数据、必要的短引用、哈希与本项目的事实判断。

本地区新增正式 IATA 分配 **0**、ICAO 分配 **0**；没有新建可声称连续有效的历史候选区间，因此 `claims.json` 保持空数组。实际正式解析覆盖增长、已解决跨机场复用、不确定区间缩减均为 0。所有批次的真实生产解析器对照由上层 `resolver-diff.json` 统一执行；观察和待审政策不算正式覆盖。

| 调查成果 | 证据与限制 | 具体下一步 |
|---|---|---|
| Chişinău KIV→RMO | 新取得 [TAROM 通知](https://www.tarom.ro/en/news/passenger-information-chisinau-airport-iata-code-change-from-kiv-into-rmo/)，2024-01-17 发布，明确预告 2024-01-18 的 IATA 订座系统切换。不是已取得的 IATA 分配通知，也不证明执行和后续连续有效期。 | 取得机场运营商执行记录或 IATA 原通知。独立保存未知 KIV 起点和 RMO 终点；不推断 LUKK 有效期。 |
| Rostov / Platov、Istanbul 两场、Munich | 复用官方物理场址文件、运营商及航司代码事实；逐项检查了旧场与新场。运营转场日与代码日期不等同，航空公司公告附件或原始分配记录仍有缺口。 | 获取 IATA 迁转原通知和各场址对应的历史 AD 2、AIP 修订。 |
| Maku / Persian Gulf PSEEZ | 新取得伊朗 OITU、OIBP AD 2，含具名机场、ARP 与页面 WEF 日期。无法据此断定目录坐标修订是迁址，或确定 IMQ、YEH、PGU 的 IATA 日期。 | 获取较早 AD 2 及 IATA 通知，先排清场址和源记录混淆。 |
| Duqm / Jaaluni、Doha / Hamad | 同一官方目录中分列的代码与机场，反对把两场混为一场。2014 与 2018 两个观察不能自动连成有效区间。 | 补齐对应 AD 2、有效版本控制和独立的 IATA 分配记录。 |
| Oseberg South / East | 新取得 [Avinor AHRI](https://xwiki.avinor.no/spaces/AHRI/pages/24151237/Offshore%2BDestinations) 表格，当前分别为 ENQO / ENQE。目录相反记录可能是字段调换纠错；表中含数字的三位值不作为正式 IATA。 | 获取历史 AHRI 修订或直升机场 AIP 代码变更原件，按平台坐标核验。 |
| Alverca、Rize-Artvin、Scandinavian Mountains | 新官方目录分别支持 LPAR、LTFO、ESKS 的具名观察。NAV 的章节有效日期、DHMI 的页面日期及 LFV 的修订清单日期分别保留。 | 补历史 AD 2 / 首次建立修订及 AVR、RZV、SCR 的 IATA 原件；不使用机场开航日代替。 |
| Mosul / Qeshm 等受阻线索 | ICAA、CAIGA 和部分历史页面的 403 / 503 / 404 按真实结果记录。官方门户不可用没有被替换成未经取得的原件。 | 走正常 AIS 历史档案获取渠道；不绕过访问限制。 |

各国 AIP、航司和运营商来源均未继承 AAI、韩国或中国物理身份授权。公开可访问不代表取得全文或数据库再发布许可；本包不声明这些权利。按出版者划分、同时区分 IATA 和 ICAO 的统一政策提案见上层 `policy/proposal.json`，仍为 proposal-only。

`source-acquisition.json` 保存本轮原始 / 提取 / 规范化文本 SHA-256、获取结果、日期性质与短引用收据；`reused-evidence.json` 明示旧收据缺少的哈希，不伪装成本轮原件重验。`observations.json` 保存分立观察，`boundary-facts.json` 保存 TAROM 的预告边界事实，`assessments.json` 给每个事件保留具体未解决问题与下一步。

复核命令（默认不联网）：

```sh
python3 research/evidence/global-code-expansion/europe/validate.py
python3 research/evidence/global-code-expansion/europe/validate.py --originals
```

第二个命令需要本轮已取得并保存在 ignored `work/` 的原件，检查实际字节、三种哈希和短引用偏移；它不重新下载，也不把收据回放等同于新获取。
