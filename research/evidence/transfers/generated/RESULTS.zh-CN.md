# PR #15 IATA 跨场址补证与待审核清单

本报告是原全球／60 组市场调查的增量补证；此前快照保持原样。全部提案 pending、verifiedOn=null，所有判断 reviewer=null。正式 0.8.0 的 27 机场／43 分配／3 名称／77 来源完全未改。

实际推进 8 个同码候选，另核实金边 1 组不同代码替代；新增引用出版物 12 份、锁定组件 16 份、事实判断 19 项（不是同等数量的独立新事件）。完整双侧**关联候选** 3 组，其中双侧直接代码陈述 1 组；行政交接日可确定 0 组。不得把关联候选称为已证实连续分配链。

新增物理记录 2、IATA 记录 5、补证既有 pending IATA 记录 3；新增 ICAO 记录 0。新增正式查询 0。相对前一 pending 假设新增 resolved 0，失去 61；后者来自新增旧场可能区间，保留并报告而不缩边界掩盖。

同码候选共取得旧侧有日期关联 6 次、新侧 6 次（含复用 CAAP；抓取日与表内月份不代表整日有效）。新增独立的场址/代码关联判断 5 项；19 个细项判断包含补证和复核，不冒充同等数量的新事件。实际事件精确到日 5、仅月/年范围 4，事件年为 [2015, 2018, 2019, 2020, 2021, 2022, 2025]。

联合提案的潜在查询（含此前成果，不能归功本次新增）：{"IATA": 6703, "ICAO": 14436}；上一阶段 {"IATA": 6764, "ICAO": 14436}。完整同码候选本次潜在 resolved 仍为 0，行政边界没有被资料补齐。

## 证据矩阵

| 案例 | 旧场有日期 IATA 观察 | 新场有日期 IATA 观察 | 分类 | 本轮新增 resolved |
|---|---:|---:|---|---:|
| 安康五里铺／富强 | 0 | 0 | 仅有单侧 IATA 关联 | 0 |
| 延安二十里铺／南泥湾 | 0 | 0 | 仅有单侧 IATA 关联 | 0 |
| 连云港白塔埠／花果山 | 2 | 1 | 完整同码跨场址候选（两侧关联；不代表已定交接） | 0 |
| 宜宾菜坝／五粮液 | 2 | 1 | 完整同码跨场址候选（两侧关联；不代表已定交接） | 0 |
| 锦州小岭子／锦州湾 | 0 | 0 | 仅有单侧 IATA 关联 | 0 |
| 泸州蓝田／云龙 | 0 | 1 | 仅有单侧 IATA 关联 | 0 |
| 湛江旧民航／吴川 | 0 | 1 | 仅有单侧 IATA 关联 | 0 |
| Tagbilaran／Bohol-Panglao | 2 | 2 | 完整同码跨场址候选（两侧关联；不代表已定交接） | 0 |
| Phnom Penh／Techo | 1 | 1 | 经明确范围原件核查，未发现可新增的同码沿用事实 | 0 |

观察数是出版物中有日期的关联，不是独立分配事实；同页不同捕获及同机构连续版本不能作为独立交叉验证。目录月份、网页抓取时间、予定生效、实际首航和代码分配日期分别保存。

## 逐条待审（不是批准建议）

### 1. 安康五里铺／富强（CN）

首航日已证实；CAAC 2018 停航使“旧场一直运营到新场”假设不成立。

- 旧场 `apt_0dc2a2f7-1222-46d2-afac-c16cbddb24d6`：安康五里铺机场；参考坐标 {"latitude": 32.708056, "longitude": 108.931111}；复用既有 pending 永久 ID；坐标 reference，非正式批准；有日期代码观察：。
- 新场 `apt_68a848c7-9db9-4233-b0d9-65eb7ed7407e`：安康富强机场；参考坐标 {"latitude": 32.75696, "longitude": 108.87338}；复用既有 pending 永久 ID；坐标 reference，非正式批准；有日期代码观察：。

迁场：{"basis": "executed", "earliest": "2020-09-25", "latest": "2020-09-25", "precision": "exact"}；首航日已证实；CAAC 2018 停航使“旧场一直运营到新场”假设不成立。

代码时间：旧场最终撤销、新场首次分配及二者行政交接均未知。保留开放可能边界，不把开航／停航／目录出版日期填成代码生效日；本轮不据单次观察扩出整日连续窗口。

独立性：同一政府系列或 CAAP 衍生航班表不重复算独立佐证；代码表、运营事实和物理调查分别判断。

阻塞／下一步：取得旧场最终代码有效观察／撤销通知和新场首次分配通知；独立人工审核物理身份与关联命名空间。；未取得旧场有日期机场专属 IATA 原件；新场现有报告附表仅关联，不证明有效年份。

本案原件核查范围：仅核查 factIds 与 examinedDiscoverySourceIds 所列范围。历史 CDX 查询无捕获不代表历史上无代码关联；名称通知与运价城市代码不能补足机场 IATA。；附加获取／读件记录：caac-fares-2015, caac-names-2009, quality-2017, quality-2018, spring-archive-index-aka, spring-home-index-aka, spring-cutoff-index-airport-aka, spring-cutoff-index-jianjie-aka。

- 复用既有事实 `ankang-finding`（原 global/markets 快照、哈希、定位保持原样）。
- 复用既有事实 `ankang-iata-guide`（原 global/markets 快照、哈希、定位保持原样）。
- 复用既有事实 `ankang-2018-suspension`（原 global/markets 快照、哈希、定位保持原样）。
- 复用既有事实 `ankang-actual`（原 global/markets 快照、哈希、定位保持原样）。

实际解析器逐日结果：{"incrementalResolvedDates": 0, "previousHypotheticalResolvedDatesNowUncertain": 0, "potentialResolvedDatesAgainstFormal": 0, "confirmedConflictDates": 0, "byCode": {"AKA": {"oldResolvedDates": 0, "newResolvedDates": 0, "uncertainDates": 4320, "crossSitePossibleDates": 0, "windows": [{"from": "2015-01-01", "toExclusive": "2026-10-30", "status": "not_found->uncertain", "airportId": null}]}}}


### 2. 延安二十里铺／南泥湾（CN）

既有 CAAC 原件证实实际迁场；尚缺旧场代码原件。

- 旧场 `apt_8deac363-2415-499d-8308-8f10de2528c8`：延安二十里铺机场；参考坐标 {"latitude": 36.636902, "longitude": 109.554001}；复用既有 pending 永久 ID；坐标 reference，非正式批准；有日期代码观察：。
- 新场 `apt_ebdabf02-ae37-4295-9667-39ea914e3c05`：延安南泥湾机场；参考坐标 {"latitude": 36.479413, "longitude": 109.464083}；复用既有 pending 永久 ID；坐标 reference，非正式批准；有日期代码观察：。

迁场：{"basis": "executed", "earliest": "2018-11-08", "latest": "2018-11-08", "precision": "exact"}；既有 CAAC 原件证实实际迁场；尚缺旧场代码原件。

代码时间：旧场最终撤销、新场首次分配及二者行政交接均未知。保留开放可能边界，不把开航／停航／目录出版日期填成代码生效日；本轮不据单次观察扩出整日连续窗口。

独立性：同一政府系列或 CAAP 衍生航班表不重复算独立佐证；代码表、运营事实和物理调查分别判断。

阻塞／下一步：取得旧场最终代码有效观察／撤销通知和新场首次分配通知；独立人工审核物理身份与关联命名空间。；未取得旧场有日期机场专属 IATA 原件；新场现有报告附表仅关联，不证明有效年份。

本案原件核查范围：仅核查 factIds 与 examinedDiscoverySourceIds 所列范围。历史 CDX 查询无捕获不代表历史上无代码关联；名称通知与运价城市代码不能补足机场 IATA。；附加获取／读件记录：caac-fares-2015, caac-names-2009, quality-2017, quality-2018, spring-archive-index-eny, spring-home-index-eny, spring-cutoff-index-airport-eny, spring-cutoff-index-jianjie-eny。

- 复用既有事实 `yanan-finding`（原 global/markets 快照、哈希、定位保持原样）。
- 复用既有事实 `yanan-iata-guide`（原 global/markets 快照、哈希、定位保持原样）。
- 复用既有事实 `yanan-actual`（原 global/markets 快照、哈希、定位保持原样）。

实际解析器逐日结果：{"incrementalResolvedDates": 0, "previousHypotheticalResolvedDatesNowUncertain": 0, "potentialResolvedDatesAgainstFormal": 0, "confirmedConflictDates": 0, "byCode": {"ENY": {"oldResolvedDates": 0, "newResolvedDates": 0, "uncertainDates": 4320, "crossSitePossibleDates": 0, "windows": [{"from": "2015-01-01", "toExclusive": "2026-10-30", "status": "not_found->uncertain", "airportId": null}]}}}


### 3. 连云港白塔埠／花果山（CN）

CAAC 确认 2021 年已迁转；南航 12-02 是计划日期，不升级成已证实实际日。

- 旧场 `apt_6f1a6ff3-98db-4e58-95fc-cc78bd5aa836`：连云港白塔埠机场；参考坐标 {"latitude": 34.571302, "longitude": 118.873143}；复用既有 pending 永久 ID；坐标 reference，非正式批准；有日期代码观察：lianyungang-old-spring-2019-11-20, lianyungang-old-spring-2020-09-21。
- 新场 `apt_64b5eaa6-a984-4816-86d9-d8eb71c91451`：连云港花果山机场；参考坐标 {"latitude": 34.41406, "longitude": 119.17899}；复用既有 pending 永久 ID；坐标 reference，非正式批准；有日期代码观察：lianyungang-new-quality。

迁场：{"basis": "executed", "earliest": "2021-01-01", "latest": "2021-12-31", "precision": "year"}；CAAC 确认 2021 年已迁转；南航 12-02 是计划日期，不升级成已证实实际日。

代码时间：旧场最终撤销、新场首次分配及二者行政交接均未知。保留开放可能边界，不把开航／停航／目录出版日期填成代码生效日；本轮不据单次观察扩出整日连续窗口。

独立性：旧场航空公司历史捕获与新场三家机构共同发布的测评报告是不同事实来源；同页面多次捕获不算独立出版物。

阻塞／下一步：取得旧场最终代码有效观察／撤销通知和新场首次分配通知；独立人工审核物理身份与关联命名空间。

本案原件核查范围：仅核查 factIds 与 examinedDiscoverySourceIds 所列范围。历史 CDX 查询无捕获不代表历史上无代码关联；名称通知与运价城市代码不能补足机场 IATA。；附加获取／读件记录：caac-fares-2015, caac-names-2009, quality-2017, quality-2018, spring-archive-index-lyg, spring-home-index-lyg。

- 复用既有事实 `lianyungang-finding`（原 global/markets 快照、哈希、定位保持原样）。
- 复用既有事实 `lianyungang-iata-guide`（原 global/markets 快照、哈希、定位保持原样）。
- `lianyungang-carrier-planned-transfer`：[南方航空 lianyungang 转场通知](https://www.csair.com/newh5/cn/service_notice/1fld91cllsvn0.shtml)；航空公司原公告直接区分两场并安排迁转；这是前瞻性自有航班计划，不是实际执行回顾，也没有 IATA 三字码。；原件 `62fbfe8866dc74b45145a7c4cf76031d67d6132c8a5b9f0537d95c464bc6d4a2`；引用 `lianyungang-carrier-planned-transfer-q1`。
- `lyg-old-guide-undated`：[龙腾卡机场指引客户版（出版日未知）](https://www.boc.cn/bcservice/bc1/201106/P020111212557815165903.pdf)；原服务提供商指南明确旧场代码 LYG，但未核实印刷出版日；URL 的 2011 及 PDF 创建时间均不作为有效观察日期。仅补强机场代码命名空间，不计入有日期观察。；原件 `4ffddbe5ae8cf24a97fb44ce392d06a9b4b38b37ecb64e3b0aa7ff2b4d91ac37`；引用 `lyg-old-guide-undated-q1`。
- `lianyungang-new-quality`：[2022 年民用机场服务质量评价报告（2023 年 05 月）](https://chinaairports.org.cn/u/cms/www/202306/12170016gkl3.pdf)；原研究报告列出新场 连云港花果山 的 LYG 关联。2022 是测评数据年度，2023-05 是出版月；二者均非分配生效日。；原件 `42a0649aedb9ac903ce35398c294053d8954f4facb9cc62612bf156d15885ff1`；引用 `lianyungang-new-quality-q1`。
- `lianyungang-old-spring-2019-11-20`：[春秋航空 连云港白塔埠机场 历史网页（捕获 2019-11-20）](https://flights.ch.com/airports/airport-LYG/)；历史捕获页面把旧场 连云港白塔埠机场 与航空公司机场订票路径 LYG 关联。代码仅存在 HTML href，属于间接机场订票代码判断；不是正文明确标为 IATA 的行政记录。捕获日也不是原文发布日期或代码分配日。；原件 `3b657ba675df9401cdeb001024c647e18a0ba2b560bbda65695050f635a51b92`；引用 `lianyungang-old-spring-2019-11-20-q1`, `lianyungang-old-spring-2019-11-20-q2`。
- `lianyungang-old-spring-2020-09-21`：[春秋航空 连云港白塔埠机场 历史网页（捕获 2020-09-21）](https://flights.ch.com/airports/airport-LYG/)；历史捕获页面把旧场 连云港白塔埠机场 与航空公司机场订票路径 LYG 关联。代码仅存在 HTML href，属于间接机场订票代码判断；不是正文明确标为 IATA 的行政记录。捕获日也不是原文发布日期或代码分配日。；原件 `b46a359d592c97d8d85e87a18a502d651fd4082763ee84f3d987ade5144719a3`；引用 `lianyungang-old-spring-2020-09-21-q1`, `lianyungang-old-spring-2020-09-21-q2`。

实际解析器逐日结果：{"incrementalResolvedDates": 0, "previousHypotheticalResolvedDatesNowUncertain": 0, "potentialResolvedDatesAgainstFormal": 0, "confirmedConflictDates": 0, "byCode": {"LYG": {"oldResolvedDates": 0, "newResolvedDates": 0, "uncertainDates": 4320, "crossSitePossibleDates": 4320, "windows": [{"from": "2015-01-01", "toExclusive": "2026-10-30", "status": "not_found->uncertain", "airportId": null}]}}}

- 待审 `transfers-proposal-lianyungang-old-iata-lyg`：assignment，pending / reviewer=null；需要真实人工审核；未确定行政交接，未知边界必须保持开放。
- 待审 `markets-proposal-lianyungang-new-iata-lyg`：assignment，pending / reviewer=null；需要真实人工审核；未确定行政交接，未知边界必须保持开放。；原件只有月份观察；未虚构具体 observedOn 日期，仍缺现有正式入库门槛所需的精确有日期原件。

### 4. 宜宾菜坝／五粮液（CN）

CAAC 地区管理局确认 2019-12-05 实际投运；不是代码分配日。

- 旧场 `apt_bbf9f2c1-fc01-4ed7-a4aa-74e6ed8ca45f`：宜宾菜坝机场；参考坐标 {"latitude": 28.800556, "longitude": 104.545}；复用既有 pending 永久 ID；坐标 reference，非正式批准；有日期代码观察：yibin-old-spring-2019-11-15, yibin-old-spring-2019-11-21。
- 新场 `apt_8354da99-7d18-4329-bf7b-4ed042a4ad72`：宜宾五粮液机场；参考坐标 {"latitude": 28.858431, "longitude": 104.526157}；复用既有 pending 永久 ID；坐标 reference，非正式批准；有日期代码观察：yibin-new-quality。

迁场：{"basis": "executed", "earliest": "2019-12-05", "latest": "2019-12-05", "precision": "exact"}；CAAC 地区管理局确认 2019-12-05 实际投运；不是代码分配日。

代码时间：旧场最终撤销、新场首次分配及二者行政交接均未知。保留开放可能边界，不把开航／停航／目录出版日期填成代码生效日；本轮不据单次观察扩出整日连续窗口。

独立性：旧场航空公司历史捕获与新场三家机构共同发布的测评报告是不同事实来源；同页面多次捕获不算独立出版物。

阻塞／下一步：取得旧场最终代码有效观察／撤销通知和新场首次分配通知；独立人工审核物理身份与关联命名空间。

本案原件核查范围：仅核查 factIds 与 examinedDiscoverySourceIds 所列范围。历史 CDX 查询无捕获不代表历史上无代码关联；名称通知与运价城市代码不能补足机场 IATA。；附加获取／读件记录：caac-fares-2015, caac-names-2009, quality-2017, quality-2018, spring-archive-index-ybp, spring-home-index-ybp, spring-cutoff-index-airport-ybp, spring-cutoff-index-jianjie-ybp。

- 复用既有事实 `yibin-finding`（原 global/markets 快照、哈希、定位保持原样）。
- 复用既有事实 `yibin-iata-guide`（原 global/markets 快照、哈希、定位保持原样）。
- 复用既有事实 `yibin-executed-date`（原 global/markets 快照、哈希、定位保持原样）。
- `yibin-new-quality`：[2022 年民用机场服务质量评价报告（2023 年 05 月）](https://chinaairports.org.cn/u/cms/www/202306/12170016gkl3.pdf)；原研究报告列出新场 宜宾五粮液 的 YBP 关联。2022 是测评数据年度，2023-05 是出版月；二者均非分配生效日。；原件 `42a0649aedb9ac903ce35398c294053d8954f4facb9cc62612bf156d15885ff1`；引用 `yibin-new-quality-q1`。
- `yibin-old-spring-2019-11-15`：[春秋航空 宜宾菜坝机场 历史网页（捕获 2019-11-15）](https://flights.ch.com/airports/airport-YBP/)；历史捕获页面把旧场 宜宾菜坝机场 与航空公司机场订票路径 YBP 关联。代码仅存在 HTML href，属于间接机场订票代码判断；不是正文明确标为 IATA 的行政记录。捕获日也不是原文发布日期或代码分配日。；原件 `66f4d0817f023cab782d56f6e16d67f911fe099b65e482396a596af35ef8a739`；引用 `yibin-old-spring-2019-11-15-q1`, `yibin-old-spring-2019-11-15-q2`。
- `yibin-old-spring-2019-11-21`：[春秋航空 宜宾菜坝机场 历史网页（捕获 2019-11-21）](https://flights.ch.com/airports/jianjie-YBP/)；历史捕获页面把旧场 宜宾菜坝机场 与航空公司机场订票路径 YBP 关联。代码仅存在 HTML href，属于间接机场订票代码判断；不是正文明确标为 IATA 的行政记录。捕获日也不是原文发布日期或代码分配日。；原件 `d00603abbdf67083210b9054f48348977257c1cb6b84e92e3448a60e97ddc6cf`；引用 `yibin-old-spring-2019-11-21-q1`, `yibin-old-spring-2019-11-21-q2`。

实际解析器逐日结果：{"incrementalResolvedDates": 0, "previousHypotheticalResolvedDatesNowUncertain": 0, "potentialResolvedDatesAgainstFormal": 0, "confirmedConflictDates": 0, "byCode": {"YBP": {"oldResolvedDates": 0, "newResolvedDates": 0, "uncertainDates": 4320, "crossSitePossibleDates": 4320, "windows": [{"from": "2015-01-01", "toExclusive": "2026-10-30", "status": "not_found->uncertain", "airportId": null}]}}}

- 待审 `transfers-proposal-yibin-old-iata-ybp`：assignment，pending / reviewer=null；需要真实人工审核；未确定行政交接，未知边界必须保持开放。
- 待审 `markets-proposal-yibin-new-iata-ybp`：assignment，pending / reviewer=null；需要真实人工审核；未确定行政交接，未知边界必须保持开放。；原件只有月份观察；未虚构具体 observedOn 日期，仍缺现有正式入库门槛所需的精确有日期原件。

### 5. 锦州小岭子／锦州湾（CN）

CAAC 年报仅足以确认 2015 年，不能采用次级网页的日精度。

- 旧场 `apt_07a48d16-088f-4f88-81c3-a689cb03531b`：锦州小岭子机场；参考坐标 {"latitude": 41.101398, "longitude": 121.061996}；复用既有 pending 永久 ID；坐标 reference，非正式批准；有日期代码观察：。
- 新场 `apt_309b521b-0137-4c9b-a404-11d7bfc17075`：锦州湾机场；参考坐标 {"latitude": 40.936032, "longitude": 121.277114}；复用既有 pending 永久 ID；坐标 reference，非正式批准；有日期代码观察：。

迁场：{"basis": "executed", "earliest": "2015-01-01", "latest": "2015-12-31", "precision": "year"}；CAAC 年报仅足以确认 2015 年，不能采用次级网页的日精度。

代码时间：旧场最终撤销、新场首次分配及二者行政交接均未知。保留开放可能边界，不把开航／停航／目录出版日期填成代码生效日；本轮不据单次观察扩出整日连续窗口。

独立性：同一政府系列或 CAAP 衍生航班表不重复算独立佐证；代码表、运营事实和物理调查分别判断。

阻塞／下一步：取得旧场最终代码有效观察／撤销通知和新场首次分配通知；独立人工审核物理身份与关联命名空间。；未取得旧场有日期机场专属 IATA 原件；新场现有报告附表仅关联，不证明有效年份。

本案原件核查范围：仅核查 factIds 与 examinedDiscoverySourceIds 所列范围。历史 CDX 查询无捕获不代表历史上无代码关联；名称通知与运价城市代码不能补足机场 IATA。；附加获取／读件记录：caac-fares-2015, caac-names-2009, quality-2017, quality-2018, spring-archive-index-jnz, spring-home-index-jnz, spring-cutoff-index-airport-jnz, spring-cutoff-index-jianjie-jnz。

- 复用既有事实 `jinzhou-finding`（原 global/markets 快照、哈希、定位保持原样）。
- 复用既有事实 `jinzhou-iata-guide`（原 global/markets 快照、哈希、定位保持原样）。

实际解析器逐日结果：{"incrementalResolvedDates": 0, "previousHypotheticalResolvedDatesNowUncertain": 0, "potentialResolvedDatesAgainstFormal": 0, "confirmedConflictDates": 0, "byCode": {"JNZ": {"oldResolvedDates": 0, "newResolvedDates": 0, "uncertainDates": 4320, "crossSitePossibleDates": 0, "windows": [{"from": "2015-01-01", "toExclusive": "2026-10-30", "status": "not_found->uncertain", "airportId": null}]}}}


### 6. 泸州蓝田／云龙（CN）

运营商资料支持 2018-09，尚不能从次级日精度推导代码边界。

- 旧场 `apt_56b57bca-08d5-4b5e-944e-1e9cce968a0a`：泸州蓝田机场；参考坐标 {"latitude": 28.852577, "longitude": 105.392579}；复用既有 pending 永久 ID；坐标 reference，非正式批准；有日期代码观察：。
- 新场 `apt_f11bdf7d-d81d-46fc-a94f-8c8c42d4e245`：泸州云龙机场；参考坐标 {"latitude": 29.030357, "longitude": 105.468407}；复用既有 pending 永久 ID；坐标 reference，非正式批准；有日期代码观察：luzhou-new-quality。

迁场：{"basis": "executed", "earliest": "2018-09-01", "latest": "2018-09-30", "precision": "month"}；运营商资料支持 2018-09，尚不能从次级日精度推导代码边界。

代码时间：旧场最终撤销、新场首次分配及二者行政交接均未知。保留开放可能边界，不把开航／停航／目录出版日期填成代码生效日；本轮不据单次观察扩出整日连续窗口。

独立性：同一政府系列或 CAAP 衍生航班表不重复算独立佐证；代码表、运营事实和物理调查分别判断。

阻塞／下一步：取得旧场最终代码有效观察／撤销通知和新场首次分配通知；独立人工审核物理身份与关联命名空间。

本案原件核查范围：仅核查 factIds 与 examinedDiscoverySourceIds 所列范围。历史 CDX 查询无捕获不代表历史上无代码关联；名称通知与运价城市代码不能补足机场 IATA。；附加获取／读件记录：caac-fares-2015, caac-names-2009, quality-2017, quality-2018, spring-archive-index-lzo, spring-home-index-lzo, spring-cutoff-index-airport-lzo, spring-cutoff-index-jianjie-lzo。

- 复用既有事实 `luzhou-finding`（原 global/markets 快照、哈希、定位保持原样）。
- `luzhou-new-quality`：[2022 年民用机场服务质量评价报告（2023 年 05 月）](https://chinaairports.org.cn/u/cms/www/202306/12170016gkl3.pdf)；原研究报告列出新场 泸州云龙 的 LZO 关联。2022 是测评数据年度，2023-05 是出版月；二者均非分配生效日。；原件 `42a0649aedb9ac903ce35398c294053d8954f4facb9cc62612bf156d15885ff1`；引用 `luzhou-new-quality-q1`。

实际解析器逐日结果：{"incrementalResolvedDates": 0, "previousHypotheticalResolvedDatesNowUncertain": 0, "potentialResolvedDatesAgainstFormal": 0, "confirmedConflictDates": 0, "byCode": {"LZO": {"oldResolvedDates": 0, "newResolvedDates": 0, "uncertainDates": 4320, "crossSitePossibleDates": 0, "windows": [{"from": "2015-01-01", "toExclusive": "2026-10-30", "status": "not_found->uncertain", "airportId": null}]}}}

- 待审 `transfers-proposal-luzhou-new-iata-lzo`：assignment，pending / reviewer=null；需要真实人工审核；未确定行政交接，未知边界必须保持开放。；原件只有月份观察；未虚构具体 observedOn 日期，仍缺现有正式入库门槛所需的精确有日期原件。

### 7. 湛江旧民航／吴川（CN）

CAAC 年报确认实际替代发生于 2022；南航 03-24 预告不能单独当执行回顾。

- 旧场 `apt_19e1bbf7-38d2-4d37-8c9a-e11b2f9e3705`：湛江旧民航机场（具体场址待匹配）；参考坐标 null；仅保留调查假设 ID，未加入机场提案；不将遂溪、坡头等军用机场当旧民航机场；有日期代码观察：。
- 新场 `apt_70c6479b-100c-44fe-b9f2-8fd1b608d9bc`：湛江吴川国际机场；参考坐标 {"latitude": 21.481667, "longitude": 110.590278}；新增待审永久 ID；新吴川 OA354995；CAAC 替代事实与服务报告具名，ARP 待补；有日期代码观察：zhanjiang-new-quality。

迁场：{"basis": "executed", "earliest": "2022-01-01", "latest": "2022-12-31", "precision": "year"}；CAAC 年报确认实际替代发生于 2022；南航 03-24 预告不能单独当执行回顾。

代码时间：旧场最终撤销、新场首次分配及二者行政交接均未知。保留开放可能边界，不把开航／停航／目录出版日期填成代码生效日；本轮不据单次观察扩出整日连续窗口。

独立性：同一政府系列或 CAAP 衍生航班表不重复算独立佐证；代码表、运营事实和物理调查分别判断。

阻塞／下一步：取得旧场最终代码有效观察／撤销通知和新场首次分配通知；独立人工审核物理身份与关联命名空间。；旧网页只有泛称湛江机场，不能排除军用场址；旧场身份及代码均不作记录提案。

本案原件核查范围：仅核查 factIds 与 examinedDiscoverySourceIds 所列范围。历史 CDX 查询无捕获不代表历史上无代码关联；名称通知与运价城市代码不能补足机场 IATA。；附加获取／读件记录：caac-fares-2015, caac-names-2009, quality-2017, quality-2018, spring-archive-index-zha, spring-home-index-zha。

- 复用既有事实 `zhanjiang-finding`（原 global/markets 快照、哈希、定位保持原样）。
- `zhanjiang-carrier-planned-transfer`：[南方航空 zhanjiang 转场通知](https://www.csair.com/newh5/cn/service_notice/1fulnefkl4qoa.shtml)；航空公司原公告直接区分两场并安排迁转；这是前瞻性自有航班计划，不是实际执行回顾，也没有 IATA 三字码。；原件 `5297a5ddc116552ee192da196157d0d34693bcc02b5db19ddb7f9c145638cd6c`；引用 `zhanjiang-carrier-planned-transfer-q1`。
- `zhanjiang-new-quality`：[2022 年民用机场服务质量评价报告（2023 年 05 月）](https://chinaairports.org.cn/u/cms/www/202306/12170016gkl3.pdf)；原研究报告列出新场 湛江吴川 的 ZHA 关联。2022 是测评数据年度，2023-05 是出版月；二者均非分配生效日。；原件 `42a0649aedb9ac903ce35398c294053d8954f4facb9cc62612bf156d15885ff1`；引用 `zhanjiang-new-quality-q1`。

实际解析器逐日结果：{"incrementalResolvedDates": 0, "previousHypotheticalResolvedDatesNowUncertain": 0, "potentialResolvedDatesAgainstFormal": 0, "confirmedConflictDates": 0, "byCode": {"ZHA": {"oldResolvedDates": 0, "newResolvedDates": 0, "uncertainDates": 4320, "crossSitePossibleDates": 0, "windows": [{"from": "2015-01-01", "toExclusive": "2026-10-30", "status": "not_found->uncertain", "airportId": null}]}}}

- 待审 `apt_70c6479b-100c-44fe-b9f2-8fd1b608d9bc`：physicalAirport，pending / reviewer=null；Human physical-site and coordinate review required.
- 待审 `transfers-proposal-zhanjiang-new-iata-zha`：assignment，pending / reviewer=null；需要真实人工审核；未确定行政交接，未知边界必须保持开放。；原件只有月份观察；未虚构具体 observedOn 日期，仍缺现有正式入库门槛所需的精确有日期原件。

### 8. Tagbilaran／Bohol-Panglao（PH）

CAAP 确认新场 2018-11-28 实际启用；旧场停止商业服务精确时刻仅有矛盾转载，不采用。

- 旧场 `apt_78682b36-d300-4f1a-be34-3d6d9614e17e`：Tagbilaran Airport (old city site)；参考坐标 {"latitude": 9.664191111111112, "longitude": 123.85362958333333}；新增待审永久 ID；JICA 旧场 ARP 与 OurAirports 5747 人工对应，不重用新场 ID；有日期代码观察：bohol-old-schedule-2015, bohol-old-schedule-2017。
- 新场 `apt_4dc2e0a8-c3ea-42a1-96c7-a268411b7460`：Bohol-Panglao International Airport；参考坐标 {"latitude": 9.56666667, "longitude": 123.775}；复用 global pending ID；CAAP 新场参考点独立于旧场；有日期代码观察：bohol-new-tag-airasia, bohol-tag。

迁场：{"basis": "executed", "earliest": "2018-11-28", "latest": "2018-11-28", "precision": "exact"}；CAAP 确认新场 2018-11-28 实际启用；旧场停止商业服务精确时刻仅有矛盾转载，不采用。

代码时间：旧场最终撤销、新场首次分配及二者行政交接均未知。保留开放可能边界，不把开航／停航／目录出版日期填成代码生效日；本轮不据单次观察扩出整日连续窗口。

独立性：同一政府系列或 CAAP 衍生航班表不重复算独立佐证；代码表、运营事实和物理调查分别判断。

阻塞／下一步：取得旧场最终代码有效观察／撤销通知和新场首次分配通知；独立人工审核物理身份与关联命名空间。；PAL 转场稿目前仅取得转载，旧场停止时刻有冲突；追踪航空公司原公告或 CAAP 撤销原件。

本案原件核查范围：仅核查 factIds 与 examinedDiscoverySourceIds 所列范围。历史 CDX 查询无捕获不代表历史上无代码关联；名称通知与运价城市代码不能补足机场 IATA。；附加获取／读件记录：caac-fares-2015, caac-names-2009, quality-2017, quality-2018。

- 复用既有事实 `bohol-actual`（原 global/markets 快照、哈希、定位保持原样）。
- `bohol-old-arp-jica`：[JICA New Bohol Airport Draft Final Report (2012): existing Tagbilaran ARP](https://libportal.jica.go.jp/library/Data/DocforEnvironment/Reports/SoutheastAsia/PhilippinesNBACSEPProject/Phillipine_Bohol%20Airport_DFR_2012.pdf)；2012 调查报告给出旧 Tagbilaran ARP；仅支持物理旧场匹配，早于研究窗且不能证明 TAG 分配或 2018 撤销。；原件 `58f24675ee738ddf8a9003e3f0b68cea77af0b6e3b754ab6e6ff225be0547f44`；引用 `bohol-old-arp-jica-q1`。
- `bohol-new-site-airasia`：[AirAsia resumes Ho Chi Minh City flights and announces Clark–Bohol route](https://newsroom.airasia.com/news/2020/2/24/airasia-resumes-flights-to-ho-chi-minh-city-launches-clark-bohol-route-this-summer)；航空公司对其已在新 Panglao 场址运营作实际陈述；文中未取得 TAG 代码，不能单凭该文建立代码观察。；原件 `adbdd0aa554f8b3c5c27705be060f5a2f5aec851263770202556fcf44baa6da5`；引用 `bohol-new-site-airasia-q1`。
- 复用既有事实 `bohol-physical-point`（原 global/markets 快照、哈希、定位保持原样）。
- `bohol-old-schedule-2015`：[Bohol Economic Factbook 2015 Edition（航班表 October 2015）](https://boholinvest.bohol.gov.ph/wp-content/uploads/2021/02/Bohol-Economic-Factbook-2015-Edition.pdf)；政府编制的旧 Tagbilaran 航班表直接印有 TAG；表内数据日期是 2015-10，不以封面 2015、2021 上传路径或 2022 存档替代。新 Panglao 仍被描述为替代现有机场的建设项目。；原件 `4fec6c9df532bcb04899122201c5627ed467ff73bdce5a7281d5c0cb1a29beeb`；引用 `bohol-old-schedule-2015-q1`, `bohol-old-schedule-2015-q2`, `bohol-old-schedule-2015-q3`。
- `bohol-old-schedule-2017`：[Bohol Economic Factbook 2016 Edition（航班表 October 2017）](https://boholinvest.bohol.gov.ph/wp-content/uploads/2021/02/Bohol-Economic-Factbook-2016-4.pdf)；政府编制的旧 Tagbilaran 航班表直接印有 TAG；表内数据日期是 2017-10，不以封面 2016、2021 上传路径或 2022 存档替代。新 Panglao 仍被描述为替代现有机场的建设项目。；原件 `bb7a45093e069349016b227ac976ae6a14b099daffae54a2c20387d1eb80b694`；引用 `bohol-old-schedule-2017-q1`, `bohol-old-schedule-2017-q2`, `bohol-old-schedule-2017-q3`。
- `bohol-new-tag-airasia`：[AirAsia celebrates the reopening of Bohol; Manila–TAG booking offer](https://newsroom.airasia.com/news/2020/11/18/airasia-celebrates-the-reopening-of-bohol-offers-50-off-on-all-flights-from-mnl-to-tag-this-week)；2020-11-18 原航空公司公告使用 Bohol(TAG) 预订代码；通过该公司 2020-02 已迁入 Panglao 的原文连接物理身份，属于间接新场代码关联。12-01 是计划复航日，不能认定 11-18 已实际飞行。；原件 `c4ed4d80b48cc1e5fb614bf08255ca8319e04f2a9124e5f28280321fee599a71`；引用 `bohol-new-tag-airasia-q1`。
- 复用既有事实 `bohol-tag`（原 global/markets 快照、哈希、定位保持原样）。

实际解析器逐日结果：{"incrementalResolvedDates": 0, "previousHypotheticalResolvedDatesNowUncertain": 61, "potentialResolvedDatesAgainstFormal": 0, "confirmedConflictDates": 0, "byCode": {"TAG": {"oldResolvedDates": 0, "newResolvedDates": 0, "uncertainDates": 4320, "crossSitePossibleDates": 4320, "windows": [{"from": "2015-01-01", "toExclusive": "2026-10-30", "status": "not_found->uncertain", "airportId": null}]}}}

- 待审 `apt_78682b36-d300-4f1a-be34-3d6d9614e17e`：physicalAirport，pending / reviewer=null；Human physical-site and coordinate review required.
- 待审 `transfers-proposal-bohol-old-iata-tag`：assignment，pending / reviewer=null；需要真实人工审核；未确定行政交接，未知边界必须保持开放。；原件只有月份观察；未虚构具体 observedOn 日期，仍缺现有正式入库门槛所需的精确有日期原件。
- 待审 `global-proposal-bohol-new-iata-tag`：assignment，pending / reviewer=null；需要真实人工审核；未确定行政交接，未知边界必须保持开放。

### 9. Phnom Penh／Techo（KH）

原件明确旧 PNH → 新 KTI；正式 0.8.0 已有 KTI 分配，用户关于缺新场 PNH 的假设不成立。不得补造 Techo 的 PNH。

- 旧场 `apt_dafb3e33-c7ed-431a-b8e8-22eecf543107`：Phnom Penh International Airport；参考坐标 {"latitude": 11.547155, "longitude": 104.844699}；复用正式 0.8.0 永久 ID，既有分配不修改；有日期代码观察：pnh-kti-sia-distinct。
- 新场 `apt_b97de260-274b-4cfd-b56e-5f035c6a7768`：Techo International Airport；参考坐标 {"latitude": 11.359987, "longitude": 104.921272}；复用正式 0.8.0 永久 ID，既有分配不修改；有日期代码观察：techo-kti-current。

迁场：{"basis": "executed", "earliest": "2025-09-09", "latest": "2025-09-09", "precision": "exact"}；运营商回顾证实 2025-09-09 实际运营，10-20 为揭幕。

代码时间：保持现有 PNH/KTI 和 ICAO 正式边界完全原样；不提出旧记录修订。

独立性：SIA 航空公司与机场业主／运营商；后两者同项目相互依赖，不作两份独立代码证明。

阻塞／下一步：未穷尽全套 IATA 分配台账，不声称全球从未有其他 PNH 变化；本明确范围没有可新增同码事实。

本案原件核查范围：复核正式库及 SIA 原公告、新运营商实际开业回顾和业主专属 IATA/ICAO 声明；结论限于本次迁场。；附加获取／读件记录：caac-fares-2015, caac-names-2009, quality-2017, quality-2018。

- `pnh-kti-sia-distinct`：[SIA SN125/260825: relocation of PNH to KTI](https://agent360.singaporeair.com/content/dam/agent360/web-assets/pdf/local/hk/HKGSQ_Relocation_of_PNH_to_KTI_Airport_SN125.pdf)；已用于正式库的原公告再次确认旧 PNH→新 KTI，而非 PNH 沿用。复用正式永久 ID，不新增代码或覆盖旧开放边界。；原件 `2eede00804c89c252f2c4c9ec962dba955ebdd7202a929912720bf56d8e08a27`；引用 `pnh-kti-sia-distinct-q1`, `pnh-kti-sia-distinct-q2`。
- `techo-executed-2025`：[Celebrating our one-year journey at Techo International Airport](https://www.techoairport.com.kh/news/oneyearjourneytechointernationalairport)；新机场运营商区分 2025-09-09 实际运营与 10-20 揭幕，不能把典礼当首航。；原件 `f2cee0108e729b77bca2c71cde0063b41021573606f7b66ba6c0551c49d9ce1e`；引用 `techo-executed-2025-q1`。
- `techo-kti-current`：[Techo International Airport (IATA: KTI, ICAO: VDTI)](https://www.ocic.com.kh/projects/techo-international-airport)；机场业主明确新场是 KTI，未发现新场 PNH 分配；与运营商同项目依赖，不能算独立的两票代码分配证据。；原件 `9d24412bd27aa08ac6b388f3d997f7335cf04b5dd87fa8a080549d06b70dafdf`；引用 `techo-kti-current-q1`。

实际解析器逐日结果：{"incrementalResolvedDates": 0, "previousHypotheticalResolvedDatesNowUncertain": 0, "potentialResolvedDatesAgainstFormal": 0, "confirmedConflictDates": 0, "byCode": {"PNH": {"oldResolvedDates": 3904, "newResolvedDates": 0, "uncertainDates": 416, "crossSitePossibleDates": 0, "windows": [{"from": "2015-01-01", "toExclusive": "2025-09-09", "status": "resolved->resolved", "airportId": "apt_dafb3e33-c7ed-431a-b8e8-22eecf543107"}, {"from": "2025-09-09", "toExclusive": "2026-10-30", "status": "uncertain->uncertain", "airportId": null}]}, "KTI": {"oldResolvedDates": 0, "newResolvedDates": 410, "uncertainDates": 3910, "crossSitePossibleDates": 0, "windows": [{"from": "2015-01-01", "toExclusive": "2025-09-10", "status": "uncertain->uncertain", "airportId": null}, {"from": "2025-09-10", "toExclusive": "2026-10-25", "status": "resolved->resolved", "airportId": "apt_b97de260-274b-4cfd-b56e-5f035c6a7768"}, {"from": "2026-10-25", "toExclusive": "2026-10-30", "status": "uncertain->uncertain", "airportId": null}]}}}


## 离线复现与继续采集

`pnpm evidence:transfers build` 从锁定最小摘录及既有快照确定性离线重建。`pnpm evidence:transfers verify` 验证摘录哈希及脱离原件的哈希出处；不能从摘录重构完整原件。

`pnpm evidence:transfers fetch --source <id> --limit 5` 只采目录中的新原件，断点跳过已取得项；`--retry-failures` 明确重试失败，`--recover` 校验重新下载字节与锁定 SHA。完整原件只存 ignored work/；动态页面改变时拒绝覆盖。可用 `verify --cache work/transfer-originals` 核验私有原件及完整提取，不把全文加入 Git。

继续工作应按 matrix 的 gaps 补充 catalog/citations/assessments，再采集和构建；无需重扫全球目录。保留 discovery-log 中获取失败、未认证镜像、城市代码表等排除原因。原全球和市场报告是阶段快照，最终采用本补证的联合解析结果。
