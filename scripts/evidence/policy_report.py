"""Reproducible Chinese handoff and content-addressed review artifacts."""
from collections import Counter
from pathlib import Path
import sys

from policy_review import ROOT, DIRECTORY, inputs, load, sha, digest, require, write_json
from policy_gate import authorization, grant_text, batch_grant_text
from policy_executor import fingerprint


def lifecycle_state(policy):
    registry = load(DIRECTORY / 'authorizations.json')
    batch_registry = load(DIRECTORY / 'batch-authorizations.json')
    require(registry['formatVersion'] == batch_registry['formatVersion'] == 1,
            'Unsupported authorization registry')
    grant = authorization(policy) if policy['status'] == 'authorized' else None
    if grant:
        require(registry['authorizations'] == [grant], 'Missing or ambiguous owner policy authorization')
    elif policy['status'] == 'draft':
        require(not registry['authorizations'], 'Draft policy has an owner authorization')
    formal = load(ROOT / 'data/airports.json')
    keys = {'airports': 'airportId', 'assignments': 'assignmentId', 'names': 'nameId', 'sources': 'sourceId'}
    formal_records = {row[key]: row for collection, key in keys.items() for row in formal[collection]}
    admitted = []
    for path in sorted((ROOT / 'research/admissions').glob('*/policy-receipt.json')):
        receipt = load(path)
        if (receipt.get('policyId'), receipt.get('policyVersion'), receipt.get('reviewMode')) != (
                policy['policyId'], policy['policyVersion'], 'policy'):
            continue
        candidate = load(path.parent / 'proposed-data.json')
        dossier = load(path.parent / 'dossier.json')
        require(sha(candidate) == receipt['datasetSha256'] and sha(dossier) == receipt['dossierSha256'],
                'Invalid recorded policy admission bundle')
        candidate_records = {row[key]: row for collection, key in keys.items() for row in candidate[collection]}
        require(dossier and all(d['reviewMode'] == 'policy' and d['reviewer'] is None and
                d['recordId'] in candidate_records for d in dossier), 'Invalid recorded policy admission dossier')
        # A prepared bundle or simulation is not an admission: its exact facts must be in formal data.
        if all(formal_records.get(d['recordId']) == candidate_records[d['recordId']] for d in dossier):
            admitted.append(candidate['dataVersion'])
    return grant, len(batch_registry['authorizations']), formal, admitted


def artifacts():
    p, lock, *_ = inputs()
    directory = DIRECTORY / 'generated'
    decisions = load(directory / 'decisions.json')
    summary = load(directory / 'summary.json')
    coverage = load(directory / 'coverage.json')
    medium = load(directory / 'medium-coverage.json')
    batches = load(directory / 'medium-batches.json')
    owner_grant, batch_count, formal, admitted = lifecycle_state(p)
    lifecycle = (f"当前状态 `{p['status']}`，有效 owner 政策授权 {int(owner_grant is not None)} 条，"
                 f"批次授权登记 {batch_count} 条。")
    admission_state = (f"当前正式数据为 {formal['dataVersion']} / Schema {formal['schemaVersion']}；"
        + (f"已包含 {len(admitted)} 个已记录政策准入包：{', '.join(admitted)}。" if admitted else
           '尚未发生真实政策自动准入，没有新增机场事实入库。'))
    candidates = [d for d in decisions if d['sample'] == 'unpublished']
    positives = [d for d in decisions if d['sample'] == 'published-positive']
    low = [d for d in candidates if d['risk'] == 'low']
    selected = [d for d in candidates if d['risk'] in ('low', 'medium')]
    original_count = sum(bool(d['researchEvidence']) for d in candidates)
    rows = ['# 可规模化证据审核：真实候选试运行', '',
        f"政策 `{p['policyId']}@{p['policyVersion']}`，SHA-256 `{p['policySha256']}`。{lifecycle}", '',
        admission_state, '',
        '以下候选、原件核验和解析器测量来自已记录的试运行。授权登记本身不代表重新取得私有原件或正式自动入库；每个正式数据 PR 仍须人工最终合并。', '',
        f"执行器 SHA-256 `{fingerprint()['executorSha256']}`。授权同时绑定规则与执行器；判定代码、门禁、证据解析、Schema、解析器或锁定依赖变化，均不能沿用旧执行器授权。", '',
        f"基线：正式 {lock['baseline']['dataVersion']} / Schema {lock['baseline']['schemaVersion']}；main `{lock['baseline']['baseCommit']}`；数据 SHA-256 `{lock['baseline']['sha256']}`。",
        '新批次独立锁定最新正式快照；旧研究流水线继续使用原 0.7.0 / 0.8.0 基线。未扫描来源变化、未重建全球研究队列。', '',
        f"试运行全部 {len(candidates)} 条去重后的未入库代码候选；{original_count} 条具有既有原件来源哈希记录。另有六条 0.9.0 人工批准代码作为正向回归；七项对应物理身份继续由现有正式 admission replay 保护。",
        '43 条候选不是 43 份新取回原件：本轮独立重新提取核验的是五个机场的十个 AIP 章节观察（八种不同原件字节、两个版次、一个发布机构）。其余候选仅检查已有锁定材料并保留阻塞。', '',
        '| 风险 | 未入库代码记录数 | 后续动作 |', '| --- | ---: | --- |',
        *[f"| {label} | {summary['counts'].get(key, 0)} | {action} |" for key, label, action in (
            ('low', '低风险', '政策获明确授权后自动审核并生成待合并 PR'),
            ('medium', '中风险', '精确批次一次授权'), ('high', '高风险', '人工例外裁决'),
            ('insufficient', '证据不足', '补充政策要求的原始观察，不能自动批准'))], '',
        '## 实际抽样核验的事实', '',
        '| 代码 | 官方名称 | ARP 原文 | 本地确定窗口 | 结论 |', '| --- | --- | --- | --- | --- |']
    sources = {s['sourceId']: s for s in load(DIRECTORY / 'source-lock.json')['sources']}
    for d in selected:
        s = sources[d['sourceIds'][0]]
        excerpt = load(DIRECTORY / s['excerptPath'])
        arp = next(q['quote'] for q in excerpt['spans'] if 'coordinates and its site' in q['quote']).split('its site ')[1]
        rows.append(f"| {d['code']} | {s['officialName']} | {arp} | `[{d['window'][0]}, {d['window'][1]})` | {d['risk']} |")
    rows += ['', '逐一核验两版的官方代码／名称、ARP、原件与独立提取哈希、短引用字符位置、章节出版／修订日。ARP 重新转换后与永久物理身份的 reference 坐标吻合；名称和坐标保持 reference，时区仍未知。',
        '2026-04-16 与 2026-07-09 版次分别用同档案 VEHO 章节的真实 AIRAC 元数据控制；各机场章节修订日单列。未将旧章节修订日、检索日或模板 Specimen 文字冒充版次生效日。',
        'VOGA、VEDG 两版章节字节完全相同：仍是两个被版次控制的时间观察，但只有一份不同原件；按“至少两份不同原件”条件进入中风险。VEHO、VASD、VOKN 各有两份不同原件，最大间隔 84 天，推断窗口 83 天。',
        '没有从开航事件推断分配日；未证明首次分配、最终撤销、历史名称区间或历史时区。竞争场址筛查覆盖全部锁定研究提案与现有参考位置假设，不能解释为全历史无冲突证明。', '',
        '## 已知正负样本', '', '| 已批准代码 | 分类 | 原因 |', '| --- | --- | --- |']
    rows += [f"| {d['code']} | {d['risk']} | {', '.join(d['reasons'])} |" for d in positives]
    rows += ['', '五条印度宽窗口进入中风险：最大观察间隔 476 天，超过自动上限 112 天。VEKI 官方名称从 KUSHINAGAR AIRPORT 扩展为带城市名的标签，作为非关键名称变化追加批次提示，没有误报为重大来源冲突。LELC 属 ENAIRE，超出当前政策范围；这不否定既有人工核实。',
        '正向样本没有自动低风险通过，原因是预先提出的严格短窗口条件；没有为提高通过率放宽条件。已有人工决定和正式结果完全保留。', '',
        '| 阻塞代码 | 记录数 | 实际分类 |', '| --- | ---: | --- |']
    for code in ('LEMI', 'RMU', 'MJV', 'TAG', 'LYG', 'YBP'):
        matches = [d for d in candidates if d['code'] == code]
        rows.append(f"| {code} | {len(matches)} | {', '.join(sorted({d['risk'] for d in matches}))} |")
    rows += ['', '上述九条负向记录自动批准数为零。TAG、LYG、YBP 均检测到跨永久物理 ID 的代码关联；LEMI/RMU/MJV 保留明确例外阻塞。安全突变测试还覆盖未知冲突、ARP 偏移、原件缺失、无版次锚点、开航日期替代、已发布记录变化、伪造身份和授权范围扩展。',
        '本次有限样本未发现危险的自动误准；不能据此宣称全球误判率为零。较保守的系统性限制是：政策只覆盖 AAI AIP、稳定名称／ARP 和短窗口，其它权威来源即使真实也不会自动通过。', '',
        '## 真实解析器差分', '',
        f"低风险：新增 **{coverage['transitions'].get('not_found->resolved', 0)}** 个 `not_found → resolved`，另有 **{coverage['transitions'].get('not_found->uncertain', 0)}** 个 `not_found → uncertain`，均按代码＋本地日期计数；不是新增机场数量。",
        f"中风险独立模拟：若精确批次获批，新增 {medium['transitions'].get('not_found->resolved', 0)} 个 resolved；不得计入低风险自动收益。",
        f"保护检查共 {coverage['codeQueries']} 次代码查询、{coverage['nameQueries']} 次既有机场名称查询；枚举 2015-01-01 至 2026-10-29，并增加 {coverage['additionalBoundaryDates']} 个所有数据边界及相邻日。",
        f"已发布 resolved 变化 {coverage['changedPublishedResolved']}；既有完整代码答案变化 {coverage['changedExistingAnswers']}；新增／移除 conflict 为 {coverage['newConflicts']}/{coverage['removedConflicts']}。不承诺无限日期穷举，区间边界及相邻日另行覆盖。",
        '模拟数据中的 verified 仅用于真实解析器测量，不能作为授权输入。正式准备必须实际读取私有原件并复核哈希、提取和引用，随后生成入库包；正式 PR 的 CI 从冻结旧基线调用原 admission CLI，离线校验原件复核收据，明确不声称本进程取得原件。CLI 只输出 work/ 中的待提交包。', '',
        '## 拒绝条件统计', '', '| 触发原因 | 未入库记录数 |', '| --- | ---: |']
    rows += [f'| `{key}` | {value} |' for key, value in sorted(summary['refusalRules'].items(), key=lambda kv: (-kv[1], kv[0]))]
    rows += ['', '一个记录可以触发多个原因。大量 outside-scope 或未受控 AIP 观察意味着不符合这项政策，不能推导为该机场没有权威历史证据。优先补充缺失的有日期 AIP 版次、准确代码／场址引用与版次锚点；迁场案例仍需人工裁决。', '',
        '## 政策授权状态与范围', '',
        f"精确授权范围为 `{p['policyId']}@{p['policyVersion']}` / `{p['policySha256']}`，适用范围 SHA-256 `{sha(p['scope'])}`。{lifecycle}",
        '范围：AAI 官方档案 AIP 的 ICAO 代码和独立物理身份 reference 属性；不含 IATA、迁场、开航日期、官方名称历史、时区或已发布事实更正。至少两个有日期且受版次控制的观察、两个不同原件；同一机构仍只计一个发布机构；相邻观察与总窗口均不超过 112 天。',
        '首日和末日不纳入确定窗口，未知外侧边界保持 null。任何竞争场址、身份不清、实质冲突、未知冲突或正式结果变化均停止；缺少原件重放、哈希变化、规则缺失／禁用／不兼容、条件不满足均 fail closed。',
        f"本次可减少三个机场／三条代码共六项逐条事实授权；长期收益随符合条件的新增记录增长。本轮尚未减少实际人工合并次数，也没有把测试通过记为 owner 亲自读过来源。",
        '中风险上限：观察间隔 868 天、窗口 1096 天；每批最多 20 个事件。中风险接受只绑定精确记录清单、窗口、来源、基线、残余风险及批次 SHA，不能授权后续新增记录。', '',
        '原始提案的精确政策授权文本（当前登记状态见上文；提案文本本身不构成授权）：', '', '```text', grant_text(p), '```', '']
    for grant in ([owner_grant] if owner_grant else []):
        rows += [f"政策授权来源：{grant['authorizationSource']}；主体 `{grant['authorizedBy']['login']}` / ID {grant['authorizedBy']['githubUserId']}；批准日 `{grant['approvedOn']}`。", '']
    for b in batches:
        rows += [f"中风险固定批次 `{b['batchSha256']}`，包含 {len(b['records'])} 条代码和对应物理身份；独立授权文本：", '', '```text', batch_grant_text(b), '```', '']
    rows += ['完整逐记录理由、原始提案阻塞、证据哈希及精确候选见 decisions.json；试运行产物与正式数据分开保存，历史快照继续保留，Keepraw-Fly 不在本工作流范围内。', '']
    rehearsal_path = directory / 'rehearsal-live.json'
    if rehearsal_path.exists():
        r = load(rehearsal_path)
        rows += ['## 工程修复与隔离端到端演练', '',
            '冻结旧基线来自已发布 main 的 0.9.0，并核对对应 Git 提交和不可变快照。候选正式数据库在隔离副本中更新为 0.10.0，原 admission CLI 不再把候选当旧基线；旧记录完整保留。',
            f"测试主体为 `{r['authority']['login']}` / ID {r['authority']['githubUserId']}，并非 keepraw。测试授权仅写入随即销毁的隔离副本；生产授权校验拒绝该测试授权：{r['productionRejectedTestGrant']}。",
            f"VEHO、VASD、VOKN：新增 {r['addedAirports']} 个物理身份、{r['addedAssignments']} 条代码、{r['addedSources']} 个来源；候选 SHA-256 `{r['candidateSha256']}`。",
            f"本地演练读取实际私有原件：{r['originalBytesRecheckedHere']}；覆盖 {r['originalSourceCount']} 个必要原件组件；原 CLI 通过：{r['originalAdmissionCliPassed']}；候选完整 pnpm check 通过：{r['fullCandidatePnpmCheckPassed']}。",
            'GitHub CI 另行重建该隔离授权和正式候选并执行完整 pnpm check，使用的是已记录原件复核收据的离线回放；普通 CI 不宣称重新取得原件。可手动运行独立原件网络复核工作流，实际下载后逐字节比对；不会上传完整原件或提取。',
            f'上述隔离演练没有改变证据阈值、112 天限制或适用范围，也没有正式自动入库。当前真实政策及授权登记状态另行报告：{lifecycle}', '']
    proposal = {'formatVersion': 1, 'status': 'authorized' if owner_grant else
                ('disabled' if p['status'] == 'disabled' else 'proposed_not_authorized'),
        'authorizationSource': owner_grant['authorizationSource'] if owner_grant else None,
        'policyId': p['policyId'], 'policyVersion': p['policyVersion'], 'policySha256': p['policySha256'],
        'scopeSha256': sha(p['scope']), 'scope': p['scope'], 'parameters': p['parameters'],
        'executor': fingerprint(), 'authorizationBinding': ['policySha256', 'scopeSha256', 'executorSha256'],
        'authorizationText': grant_text(p), 'mediumBatchAuthorizationTexts': [batch_grant_text(b) for b in batches]}
    return '\n'.join(rows), proposal


def main(command):
    directory = DIRECTORY / 'generated'
    report, proposal = artifacts()
    if command == 'build':
        (directory / '审核报告.zh-CN.md').write_text(report)
        write_json(directory / 'authorization-proposal.json', proposal)
        write_json(directory / 'manifest.json', {'formatVersion': 1, 'mode': 'dry_run',
            'files': {p.name: digest(p) for p in sorted(directory.iterdir()) if p.name != 'manifest.json'}})
    elif command == 'validate':
        require((directory / '审核报告.zh-CN.md').read_text() == report and
                load(directory / 'authorization-proposal.json') == proposal, 'Stale policy report/proposal')
        manifest = load(directory / 'manifest.json')
        require(set(manifest['files']) == {p.name for p in directory.iterdir() if p.name != 'manifest.json'},
                'Unmanifested policy artifact')
        for name, expected in manifest['files'].items():
            require(digest(directory / name) == expected, 'Changed policy artifact')
        print('Chinese policy report, exact authorization proposal and all artifact hashes reproduced.')
    else: raise ValueError('Expected build or validate')


if __name__ == '__main__': main(sys.argv[1])
