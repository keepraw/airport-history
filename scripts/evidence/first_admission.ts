/** Review preparation only. Reviewed states exist solely inside the resolver hypothesis. */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";
import { execFileSync } from "node:child_process";
import { resolveAirport } from "../../src/resolve.ts";
import { assertDataset } from "../../src/validate.ts";
import { dateNumber } from "../../src/time.ts";
import type { Dataset, CodeAssignment, PhysicalAirport, Resolution, Source } from "../../src/types.ts";

export const ROOT = resolve(fileURLToPath(new URL("../..", import.meta.url)));
export const DIRECTORY = "research/evidence/first-admission";
const CUTOFF = "2026-10-29", START = "2015-01-01", DAY = 86400000;
const read = <T>(path: string): T => JSON.parse(readFileSync(resolve(ROOT, path), "utf8"));
const hash = (path: string) => createHash("sha256").update(readFileSync(resolve(ROOT, path))).digest("hex");
const json = (value: unknown) => JSON.stringify(value, null, 2) + "\n";
const date = (n: number) => new Date(n * DAY).toISOString().slice(0, 10);
const shift = (s: string, n: number) => date(dateNumber(s) + n);
const key = (r: Pick<CodeAssignment, "scheme" | "code">) => `${r.scheme}:${r.code}`;
type Scope = {
  recordId: string; recordType: "assignment"; airportId: string; eventGroupId: string;
  siteKey: string; scheme: "IATA" | "ICAO"; code: string; class: "A" | "B" | "C";
  decision: "pending"; reviewer: null; proposalStage: string;
  recommendedWindow: [string, string] | null; evidenceSourceIds: string[];
  editionControlSourceIds: string[]; reasonZh: string; residualRisksZh: string[];
  excludedClaims: string[]; unknownBeforeAndAfter: string;
  exactAuthorization: null | (Pick<CodeAssignment, "validFrom" | "validTo" | "evidenceType" | "sourceIds" | "airportId" | "scheme" | "code"> & {
    recordId: string; requiresSeparatePhysicalIdentityApproval: string;
  });
};
type Identity = {
  recordId: string; recordType: "physicalAirport"; airportId: string; eventGroupId: string;
  class: "A"; decision: "pending"; reviewer: null; displayName: string;
  coordinates: { latitude: number; longitude: number }; coordinateStatus: "reference";
  evidenceSourceIds: string[]; exactAuthorization: PhysicalAirport & { scope: string };
};
type Selection = {
  baseCommit: string; formalBaselineSha256: string; decision: "pending"; reviewer: null;
  assignments: Scope[]; physicalAirports: Identity[]; retainedBlockers: string[];
};
type Span = { kind: string; page: number | null; characterStart: number; characterEnd: number; quote: string };
type LockedSource = {
  sourceId: string; publisher: string; url: string; accessedAt: string;
  originalSha256: string; textOriginalSha256: string; excerptPath: string; excerptSha256: string;
  originalPublicationKey: string; sourceFamily: string; role: string;
  documentEffectiveDate: string | null; editionEffectiveDate: string | null;
  componentEffectiveDate: string | null; publicationDate: string | null;
  acquisitionStatus: string; priorLock: string | null; decision: "pending"; reviewer: null;
};
export function loadInputs() {
  const selection = read<Selection>(`${DIRECTORY}/selection.json`);
  const lock = read<{ sources: LockedSource[] }>(`${DIRECTORY}/source-lock.json`);
  const base = read<Dataset>("data/airports.json");
  const stages = Object.fromEntries(["global", "markets", "transfers"].map(stage =>
    [stage, read<Dataset>(`research/evidence/${stage}/generated/proposed-data.json`)]));
  return { selection, lock, base, stages };
}
type Inputs = ReturnType<typeof loadInputs>;
export function validateInputs(input: Inputs) {
  const { selection: s, lock, base, stages } = input;
  if (hash("data/airports.json") !== s.formalBaselineSha256 || base.dataVersion !== "0.8.0")
    throw new Error("Formal baseline changed: explicitly rebase and re-review the preparation");
  assertDataset(base);
  const unique = (ids: string[]) => { if (new Set(ids).size !== ids.length) throw new Error("Duplicate record or source"); };
  unique([...s.assignments, ...s.physicalAirports].map(r => r.recordId));
  unique(s.assignments.map(key)); unique(lock.sources.map(r => r.sourceId));
  if ([s, ...s.assignments, ...s.physicalAirports, ...lock.sources].some(r => r.decision !== "pending" || r.reviewer !== null))
    throw new Error("Preparation cannot record a human approval");
  for (const source of lock.sources) {
    if (!/^[a-z0-9-]+$/.test(source.sourceId) || source.excerptPath !== `excerpts/${source.sourceId}.json`)
      throw new Error("Unsafe source path");
    const path = `${DIRECTORY}/${source.excerptPath}`;
    const e = read<{ originalSha256: string; textOriginalSha256: string; spans: Span[] }>(path);
    if (hash(path) !== source.excerptSha256 || e.originalSha256 !== source.originalSha256 ||
        e.textOriginalSha256 !== source.textOriginalSha256 || !e.spans.length ||
        e.spans.some(p => p.characterEnd - p.characterStart !== p.quote.length || p.characterStart < 0))
      throw new Error(`Detached or altered citation: ${source.sourceId}`);
    if (source.priorLock) {
      const prior = read<{ sources: LockedSource[] }>(source.priorLock).sources.find(p => p.sourceId === source.sourceId);
      if (prior?.originalSha256 !== source.originalSha256) throw new Error("Changed previously locked original");
    }
  }
  const sources = new Map(lock.sources.map(r => [r.sourceId, r]));
  const owners = new Map<string, string>();
  for (const filename of ["global-evidence-proposal-1.json", "global-evidence-proposal-2.json"]) {
    const packet = read<{ events: { eventGroupId: string; proposedRecordIds: string[] }[] }>(`research/evidence/global/generated/batches/${filename}`);
    for (const event of packet.events) for (const id of event.proposedRecordIds) owners.set(id, event.eventGroupId);
  }
  for (const r of [...s.assignments, ...s.physicalAirports])
    if (owners.get(r.recordId) !== r.eventGroupId) throw new Error("Canonical event owner changed");
  for (const r of s.assignments) {
    const proposed = stages[r.proposalStage]?.assignments.find(a => a.assignmentId === r.recordId);
    if (!proposed || proposed.verificationStatus !== "pending" || proposed.verifiedOn !== null ||
        proposed.airportId !== r.airportId || key(proposed) !== key(r)) throw new Error("Changed canonical proposal");
    if (base.assignments.some(a => a.assignmentId === r.recordId || key(a) === key(r)))
      throw new Error("Existing formal code requires a separate conflict review");
    if (Object.values(stages).some(data => data.assignments.some(a => key(a) === key(r) &&
      (a.assignmentId !== r.recordId || a.airportId !== r.airportId))))
      throw new Error("Competing pending code/site allocation requires conflict review");
    if (!s.physicalAirports.some(p => p.airportId === r.airportId)) throw new Error("Separate physical review missing");
    const controls = [...r.evidenceSourceIds, ...r.editionControlSourceIds].map(id => {
      const source = sources.get(id); if (!source) throw new Error("Missing locked evidence"); return source;
    });
    if (r.class !== "A") {
      if (r.exactAuthorization !== null || r.recommendedWindow !== null) throw new Error("Blocked record has approval scope");
      continue;
    }
    const w = r.recommendedWindow, a = r.exactAuthorization;
    if (!w || !a || !Number.isFinite(dateNumber(w[0])) || !Number.isFinite(dateNumber(w[1])) ||
        w[0] >= w[1] || w[1] > CUTOFF || a.validFrom.earliest !== null || a.validTo.latest !== null ||
        a.validFrom.latest !== w[0] || a.validTo.earliest !== w[1] ||
        a.validFrom.precision !== "unknown" || a.validTo.precision !== "unknown" ||
        a.evidenceType !== "continuity_inference" || !isDeepStrictEqual(a.sourceIds, r.evidenceSourceIds) ||
        a.recordId !== r.recordId || a.airportId !== r.airportId || a.scheme !== r.scheme || a.code !== r.code ||
        a.requiresSeparatePhysicalIdentityApproval !== r.airportId)
      throw new Error("Unsafe or inconsistent authorization window");
    const observations = controls.map(p => p.editionEffectiveDate ?? p.documentEffectiveDate ?? p.publicationDate)
      .filter((d): d is string => d !== null);
    // Current ENAIRE index is an actual 29 October observation. Its printed WEF
    // remains separate and is never silently converted to a withdrawal date.
    if (r.evidenceSourceIds.includes("es-murcia-index-current")) observations.push(CUTOFF);
    if (!observations.includes(shift(w[0], -1)) || !observations.includes(w[1]))
      throw new Error("Window lacks dated endpoint observations");
    if (r.code.startsWith("V")) {
      for (const edition of ["2024-02-22", "2025-06-12", "2026-07-09"]) {
        if (!controls.some(p => p.editionEffectiveDate === edition && p.componentEffectiveDate === edition))
          throw new Error("Archive edition has no matching AIRAC metadata anchor");
      }
    }
  }
  for (const p of s.physicalAirports) {
    const existing = stages.global!.airports.find(a => a.airportId === p.airportId);
    if (!existing || base.airports.some(a => a.airportId === p.airportId ||
      (a.externalIds.ourAirports && a.externalIds.ourAirports === existing.externalIds.ourAirports)))
      throw new Error("Duplicate physical identity");
    const { scope: _scope, ...record } = p.exactAuthorization;
    const expected = structuredClone(existing);
    // Curate reference citations to the reviewed AIP observations; retain every
    // permanent value/status and leave the older proposal completely untouched.
    expected.name.sourceIds = [...p.evidenceSourceIds];
    expected.coordinates.sourceIds = [...p.evidenceSourceIds];
    if (!isDeepStrictEqual(record, expected) || !isDeepStrictEqual(p.coordinates, existing.coordinates.value))
      throw new Error("Physical identity or reference attributes changed");
    // Independently convert official ARP DMS, rather than trusting directory decimals.
    const arps: string[] = [];
    for (const id of p.evidenceSourceIds) {
      const source = sources.get(id); if (!source) throw new Error("Missing physical evidence");
      const e = read<{ spans: Span[] }>(`${DIRECTORY}/${source.excerptPath}`);
      for (const span of e.spans) {
        const m = span.quote.match(/(\d{6})N (\d{7})([EW])/); if (m) arps.push(m[0]);
      }
    }
    if (!arps.length || new Set(arps).size !== 1) throw new Error("Missing or inconsistent official ARP");
    const m = arps[0]!.match(/(\d{2})(\d{2})(\d{2})N (\d{3})(\d{2})(\d{2})([EW])/)!
    const latitude = +m[1]! + +m[2]! / 60 + +m[3]! / 3600;
    const longitude = (+m[4]! + +m[5]! / 60 + +m[6]! / 3600) * (m[7] === "W" ? -1 : 1);
    if (Math.abs(latitude - p.coordinates.latitude) > 1e-8 || Math.abs(longitude - p.coordinates.longitude) > 1e-8)
      throw new Error("Reference decimals do not match official ARP");
  }
}

/** Contains only specified A scopes. Does not write any reviewed state to disk. */
export function hypothesis(input: Inputs, records: Scope[], approve = true): Dataset {
  const data = structuredClone(input.base);
  data.dataVersion = "0.9.0"; // Proposed version only; formal bytes stay 0.8.0.
  const ids = new Set(records.map(r => r.recordId));
  if (ids.size !== records.length || records.some(r => r.class !== "A" || !r.exactAuthorization))
    throw new Error("Hypothesis accepts unique A scopes only");
  for (const id of new Set(records.map(r => r.airportId))) {
    const p = input.selection.physicalAirports.find(r => r.airportId === id)!;
    const { scope: _scope, ...record } = p.exactAuthorization;
    data.airports.push(structuredClone(record));
  }
  for (const r of records) {
    const original = input.stages[r.proposalStage]!.assignments.find(a => a.assignmentId === r.recordId)!;
    const a = r.exactAuthorization!;
    data.assignments.push({ ...structuredClone(original), validFrom: structuredClone(a.validFrom),
      validTo: structuredClone(a.validTo), evidenceType: a.evidenceType, sourceIds: [...a.sourceIds],
      verificationStatus: approve ? "verified" : "pending", verifiedOn: approve ? CUTOFF : null,
      note: `Review-only scope ${r.recordId}. Unknown outer boundaries retained; whole-day continuity hypothesis only.` });
  }
  const sourceIds = new Set(data.airports.flatMap(a => [...a.name.sourceIds, ...a.coordinates.sourceIds, ...a.timezone.sourceIds])
    .concat(data.assignments.flatMap(a => a.sourceIds)));
  const reviewed = new Set(records.flatMap(r => r.evidenceSourceIds));
  for (const id of sourceIds) {
    if (data.sources.some(s => s.sourceId === id)) continue;
    const source = Object.values(input.stages).flatMap(s => s.sources).find(s => s.sourceId === id);
    const locked = input.lock.sources.find(s => s.sourceId === id);
    const fresh: Source = source ? structuredClone(source) : {
      sourceId: id, title: `India AIP bounded review ${id}`, url: locked!.url,
      accessedOn: CUTOFF, verificationStatus: "pending", sourceType: "primary",
      license: { id: "LicenseRef-AAI-Terms", url: "https://www.aai.aero/en/corporate/copyright",
        note: "Rights retained; no full-original, chart or photo redistribution permission inferred." },
      note: "Three same-issuer edition observations; original hashes and minimal citations in first-admission/source-lock.json.",
    };
    if (approve && reviewed.has(id)) fresh.verificationStatus = "verified";
    data.sources.push(fresh);
  }
  assertDataset(data);
  return data;
}

type Transitions = Record<string, number>;
const count = (rows: Transitions, a: string, b: string) => { const k = `${a}->${b}`; rows[k] = (rows[k] ?? 0) + 1; };
const answer = ({ dataVersion: _version, ...value }: Resolution) => value;
function measure(input: Inputs, records: Scope[], protectFormal = false) {
  const base = input.base, pending = hypothesis(input, records, false), approved = hypothesis(input, records);
  const transitions: Transitions = {}, pendingTransitions: Transitions = {}, reviewTransitions: Transitions = {};
  const byScheme = { IATA: 0, ICAO: 0 };
  const windows: { from: string; toExclusive: string; transition: string; airportId: string | null; code: string; scheme: string }[] = [];
  const boundaries: unknown[] = [];
  let newConflicts = 0, removedConflicts = 0, changedPublishedResolved = 0, changedExistingAnswers = 0;
  let protectedQueries = 0;
  for (const r of records) {
    for (let n = dateNumber(START); n <= dateNumber(CUTOFF); n++) {
      const d = date(n), before = resolveAirport(base, r.code, d, r.scheme);
      const waiting = resolveAirport(pending, r.code, d, r.scheme), after = resolveAirport(approved, r.code, d, r.scheme);
      count(transitions, before.status, after.status); count(pendingTransitions, before.status, waiting.status);
      count(reviewTransitions, waiting.status, after.status);
      if (after.status === "resolved" && before.status !== "resolved") byScheme[r.scheme]++;
      if (after.status === "conflict" && before.status !== "conflict") newConflicts++;
      if (before.status === "conflict" && after.status !== "conflict") removedConflicts++;
      if (before.status === "resolved" && (after.status !== "resolved" || after.airport?.airportId !== before.airport?.airportId)) changedPublishedResolved++;
      const transition = `${before.status}->${after.status}`, airportId = after.airport?.airportId ?? null;
      const last = windows.at(-1);
      if (last?.code === r.code && last.scheme === r.scheme && last.transition === transition && last.airportId === airportId)
        last.toExclusive = date(n + 1);
      else windows.push({ from: d, toExclusive: date(n + 1), transition, airportId, code: r.code, scheme: r.scheme });
    }
    const [start, end] = r.recommendedWindow!;
    for (const d of [...new Set([shift(start, -2), shift(start, -1), start, shift(start, 1), shift(end, -1), end, shift(end, 1)])]) {
      const b = resolveAirport(base, r.code, d, r.scheme), p = resolveAirport(pending, r.code, d, r.scheme), a = resolveAirport(approved, r.code, d, r.scheme);
      boundaries.push({ scheme: r.scheme, code: r.code, localDate: d, formal: b.status, pending: p.status,
        acceptedHypothesis: a.status, airportId: a.airport?.airportId ?? null });
      const expected = start <= d && d < end ? "resolved" : "uncertain";
      if (a.status !== expected || p.status === "resolved") throw new Error("Whole-local-day boundary regression");
    }
  }
  // Protect every complete formal answer for each formal code/date in the benchmark,
  // and all existing assignment boundary dates (including dates before 2015).
  const formalKeys = new Map(base.assignments.map(a => [key(a), a]));
  for (const a of protectFormal ? formalKeys.values() : []) {
    const dates = new Set<string>();
    for (let n = dateNumber(START); n <= dateNumber(CUTOFF); n++) dates.add(date(n));
    for (const r of base.assignments.filter(r => key(r) === key(a)))
      for (const d of [r.validFrom.earliest, r.validFrom.latest, r.validTo.earliest, r.validTo.latest])
        if (d) for (const offset of [-1, 0, 1]) dates.add(shift(d, offset));
    for (const d of dates) {
      const before = resolveAirport(base, a.code, d, a.scheme);
      if (!isDeepStrictEqual(answer(before), answer(resolveAirport(approved, a.code, d, a.scheme))) ||
          !isDeepStrictEqual(answer(before), answer(resolveAirport(pending, a.code, d, a.scheme)))) changedExistingAnswers++;
      protectedQueries++;
    }
  }
  if (changedPublishedResolved || changedExistingAnswers || newConflicts || removedConflicts)
    throw new Error("Hypothesis changes published history or conflict status; exclude from A");
  return { recordIds: records.map(r => r.recordId), uniqueFocusedQueries: records.length * (dateNumber(CUTOFF) - dateNumber(START) + 1),
    formalToAccepted: transitions, formalToPending: pendingTransitions, pendingToAccepted: reviewTransitions,
    netNewResolved: byScheme.IATA + byScheme.ICAO, byScheme, newConflicts, removedConflicts,
    changedPublishedResolved, changedExistingAnswers, protectedQueries, windows, boundaries };
}

export function buildArtifacts(input = loadInputs()): Record<string, string> {
  validateInputs(input);
  const candidates = input.selection.assignments, accepted = candidates.filter(r => r.class === "A");
  // Singleton effects are measured against formal 0.8.0, then union effects are
  // measured again; repeated pipeline proposals never become repeated queries.
  const singleton = accepted.map(r => measure(input, [r]));
  const combined = measure(input, accepted, true);
  if (singleton.reduce((n, r) => n + r.netNewResolved, 0) !== combined.netNewResolved)
    throw new Error("Non-additive candidate interaction requires explicit review");
  const coverage = { period: [START, CUTOFF], unit: "Unique (scheme, code, localDate); whole local dates only",
    hypothesis: "Only specified A scopes and their separately reviewed identities; approval in memory only. Sources/coordinates/name status remain independent.",
    formalNewResolvedQueries: 0, byRecord: singleton, combined,
    unselectedRecords: candidates.filter(r => r.class !== "A").map(r => ({ recordId: r.recordId, admittedGain: 0, measuredAcceptanceWindow: null })) };
  const dossier = [...input.selection.physicalAirports, ...candidates].map(r => ({ ...r,
    officialNameObservations: input.selection.physicalAirports.find(p => p.airportId === r.airportId)!.evidenceSourceIds
      .flatMap(id => read<{ spans: Span[] }>(`${DIRECTORY}/${input.lock.sources.find(s => s.sourceId === id)!.excerptPath}`).spans
        .filter(s => /^[A-Z]{4} - /.test(s.quote)).map(s => ({ sourceId: id, officialName: s.quote.slice(7) }))),
    coordinateEvidenceState: "Official ARP independently converted to the existing reference decimals. Reference status retained; no coordinate verification upgrade requested.",
    netNewResolved: singleton.find(a => a.recordIds[0] === r.recordId)?.netNewResolved ?? 0,
    observations: r.evidenceSourceIds.map(id => {
      const s = input.lock.sources.find(s => s.sourceId === id)!;
      return { ...s, observedOn: id === "es-murcia-index-current" ? CUTOFF :
        s.editionEffectiveDate ?? s.documentEffectiveDate ?? s.publicationDate,
        independentOriginal: true,
        independenceNote: "Original-publication provenance only; same-issuer editions/components do not become independent publishers.",
        claimScope: r.recordType === "physicalAirport" ? "Named physical site and official ARP; reference attributes only." :
          "Named code/site association at the separately stated observation; no first allocation, final withdrawal or daily ledger.",
        basis: `Fresh original SHA-256 and extraction checked; exact cited positions in ${DIRECTORY}/${s.excerptPath}` };
    }),
    boundaryAssessment: r.recordType === "assignment" ? (r.recommendedWindow ?
      `Certain whole-local-date window [${r.recommendedWindow.join(", ")}); first observation day and final observation day excluded; outer boundaries null/unknown.` :
      "No defensible acceptance window; historical association and single current observation are insufficient.") : null,
    continuityAssessment: r.recordType === "assignment" ? r.reasonZh : null,
    duplicateAndConflictCheck: {
      formalMatches: input.base.assignments.filter(a => r.recordType === "assignment" && key(a) === key(r)).map(a => a.assignmentId),
      pipelineOccurrences: Object.entries(input.stages).map(([stage, data]) => ({ stage,
        recordIds: r.recordType === "assignment" ? data.assignments.filter(a => key(a) === key(r)).map(a => a.assignmentId)
          : data.airports.filter(a => a.airportId === r.airportId).map(a => a.airportId) })),
      conclusion: "Canonical permanent/proposal IDs reused; pipeline occurrences are not independent records. No competing formal or pending code/site allocation for selected keys.",
    },
  }));
  const outputs: Record<string, string> = {
    "dossier.json": json(dossier), "resolver-diff.json": json(coverage),
    "scoped-proposed-data.json": json(hypothesis(input, accepted, false)),
  };
  const lines = ["# 首批正式历史入库人工审批清单", "", "本包仅为研究建议，所有记录 decision=pending、reviewer=null。正式库仍为 0.8.0；A 类不是批准。", "",
    `实际审核：${candidates.length} 条代码分配（A=${accepted.length}、B=${candidates.filter(r => r.class === "B").length}、C=${candidates.filter(r => r.class === "C").length}），另有 ${input.selection.physicalAirports.length} 个独立物理身份（均 A）。`, "",
    `全部 A 类若逐项获批：净增 ${combined.netNewResolved} 个唯一代码/本地日期 resolved 查询，IATA=${combined.byScheme.IATA}、ICAO=${combined.byScheme.ICAO}。正式未入库增量仍为 0。`, "",
    "正式库→假设入库的状态变化：`" + JSON.stringify(combined.formalToAccepted) + "`。只加入待审记录时：`" + JSON.stringify(combined.formalToPending) + "`。待审→假设批准：`" + JSON.stringify(combined.pendingToAccepted) + "`。", "",
    `原有完整正式答案保护检查 ${combined.protectedQueries} 个唯一查询（含既有边界相邻日）；答案变化 ${combined.changedExistingAnswers}，已发布 resolved 身份/状态变化 ${combined.changedPublishedResolved}，新增/消除冲突 ${combined.newConflicts}/${combined.removedConflicts}。`, "",
    "## 必须单独批准的物理身份", "", "ARP 由原始 AIP 独立换算核对。批准的仅为场址身份及现有参考属性；名称/坐标仍 reference，timezone 仍 unknown，不形成名称有效期。", "",
    "| 永久 airportId | 显示名称 | ARP 参考坐标 | 选择 |", "|---|---|---|---|",
    ...input.selection.physicalAirports.map(p => `| \`${p.airportId}\` | ${p.displayName} | ${p.coordinates.latitude}, ${p.coordinates.longitude} | 批准该身份 / 暂缓该身份 |`), "",
    "## 逐条代码分配", "",
  ];
  for (const r of candidates) {
    const physical = input.selection.physicalAirports.find(p => p.airportId === r.airportId)!;
    const gain = singleton.find(p => p.recordIds[0] === r.recordId)?.netNewResolved ?? 0;
    lines.push(`### ${r.class} · ${r.code} · ${physical.displayName}`, "",
      `提案：\`${r.recordId}\`；事件组：\`${r.eventGroupId}\`；${r.scheme}；永久场址：\`${r.airportId}\`。`, "",
      r.reasonZh, "", r.recommendedWindow ? `建议精确窗口：**[${r.recommendedWindow[0]}, ${r.recommendedWindow[1]})**；净增 **${gain}**。外侧 earliest-start / latest-end 保持 null，precision=unknown，evidenceType=continuity_inference。` : "没有可批准时间窗口；继续 pending，预期本轮正式覆盖增量 0。", "",
      "直接事实：原件具名代码/场址观察和官方 ARP；连续性是额外推断，不是原件逐日分配声明。",
      "窗口外仍未知：首次观察日整体排除；末次观察日及其后排除。更早首配及最后撤码未定。", "",
      ...r.evidenceSourceIds.map(id => { const s = input.lock.sources.find(s => s.sourceId === id)!;
        return `- [${id}](${s.url})：${s.publisher}；出版/组件发布日期 ${s.publicationDate ?? "未知"}；章节生效 ${s.componentEffectiveDate ?? s.documentEffectiveDate ?? "不适用/未知"}；档案版次 ${s.editionEffectiveDate ?? "不适用"}；本轮取得 ${s.accessedAt}；SHA-256 \`${s.originalSha256}\`。页码/字符位置见 [最小引用](../${s.excerptPath})。`; }), "",
      `残余风险：${r.residualRisksZh.join("；")}`, "", "冲突检查：三个研究流水线按同一记录 ID 去重；正式库及待审集合无该代码的其他场址竞争。既有永久 ID、边界和正式记录不变。", "",
      r.recommendedWindow ? `精确授权选项：批准 / 暂缓 \`${r.recordId}\`，${r.scheme} ${r.code} → \`${r.airportId}\`，仅 [${r.recommendedWindow[0]}, ${r.recommendedWindow[1]})。须另行批准该物理身份；不自动授权其他代码、开业年份、坐标 verified 或历史名称。` : "补证后重新评估；本包没有为此记录提供批准选项。", "");
  }
  lines.push("## 来源、推断与原有阻塞", "",
    "19 个原始来源组件均在本轮重新取得；14 个与既有锁定 SHA-256 一致，5 个为有针对性的 2025 中间版次。AAI 三个版次只有一个发布机构；同版次组件与 AIRAC 元数据锚点不重复计作独立出版物。", "",
    "AAI 档案路径日期、各章节 DC.date 与 EM.effectiveDateStart 单列。根导航/封面含 Specimen 模板文字，2026-07 的 GEN 0.2 仍停在六月，均未用于证明七月生效；采用同档案真实 AD 章节的 AIRAC 元数据锚点。中间版次也保留其较早章节修订日。", "",
    "2026 ENAIRE 索引的新版 WEF 是 2026-10-01；HTML 中旧版 2026-09-03 不作为新版日期。LEMI/RMU 和 LELC/MJV 行都没有删除/旧版标记。本轮取得日 2026-10-29 是末次观察，不是撤码日。", "",
    "2019 原刊对 LEMI/RMU 是当时新机场的明确关联，对旧 LELC/MJV 则是历史叙述。因此 LELC 只推荐 2026-04-17 起的官方窗口，MJV 暂缓；不沿用 markets 的四条统一跨年窗口。民航服务转移没有删除 San Javier 的军用身份。", "",
    "同址连续性依据多个具名官方/原始观察、相同 ARP、中间抽查及无已知竞争分配。未穷尽所有中间通知，不能声称已证明从未撤销或重分配；此推断由用户单独决定。", "",
    `原有阻塞继续保留：${input.selection.retainedBlockers.join("、")}。未重新全球扫描，未把这些案例算作新增 C 类审核。`, "",
    "## 逐记录授权方式", "",
    "请逐条回复：`批准物理身份 <完整 airportId>，名称和坐标保留 reference、timezone unknown`；然后另行回复 `批准代码分配 <完整提案 ID>，<scheme> <code> → <完整 airportId>，仅 [start,end)`。也可逐条选择暂缓。", "",
    "物理身份授权与代码授权互不替代。以 selection.json 的 exactAuthorization 为机器可读范围，不能用‘批准整个事件组/全部研究’代替。明确授权前不得正式入库；下一轮仍须通过现有 admission gate、来源审查、0.9.0 差分及完整回归检查。", "");
  outputs["审批清单.zh-CN.md"] = lines.join("\n");
  const inputPaths = ["data/airports.json", `${DIRECTORY}/selection.json`, `${DIRECTORY}/source-lock.json`,
    ...input.lock.sources.map(s => `${DIRECTORY}/${s.excerptPath}`),
    ...["global", "markets", "transfers"].flatMap(s => [`research/evidence/${s}/generated/proposed-data.json`, `research/evidence/${s}/generated/dossier.json`]),
    "research/evidence/global/generated/batches/global-evidence-proposal-1.json",
    "research/evidence/global/generated/batches/global-evidence-proposal-2.json",
    "research/evidence/global/source-lock.json", "research/evidence/markets/source-lock.json",
    "src/resolve.ts", "src/time.ts", "src/evidence.ts", "src/validate.ts", "src/types.ts", "scripts/evidence/first_admission.ts"];
  outputs["manifest.json"] = json({ formatVersion: 1, baseCommit: input.selection.baseCommit,
    formalBaselineSha256: input.selection.formalBaselineSha256, preparationOnly: true,
    inputs: Object.fromEntries(inputPaths.sort().map(p => [p, hash(p)])),
    outputs: Object.fromEntries(Object.entries(outputs).map(([p, v]) => [p, createHash("sha256").update(v).digest("hex")])) });
  return outputs;
}

function main() {
  const command = process.argv[2] ?? "validate";
  if (command === "verify-originals") {
    if (!process.argv[3]) throw new Error("Supply the private sourceId.bin directory");
    // Reuse the existing extractor; protected originals/text never become outputs.
    execFileSync("python3", ["-c", `import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,'scripts/evidence')
from global_batch import extract
base=Path(sys.argv[1]);cache=Path(sys.argv[2])
for s in json.loads((base/'source-lock.json').read_text())['sources']:
 raw=(cache/(s['sourceId']+'.bin')).read_bytes()
 assert hashlib.sha256(raw).hexdigest()==s['originalSha256'],s['sourceId']
 text=extract(raw)
 assert hashlib.sha256(text.encode()).hexdigest()==s['textOriginalSha256'],s['sourceId']
 for p in json.loads((base/s['excerptPath']).read_text())['spans']:
  part=raw.decode() if p['kind']=='raw_html' else ' '.join((text.split('\\f')[p['page']-1] if p['page'] else text).split())
  assert part[p['characterStart']:p['characterEnd']]==p['quote'],s['sourceId']
print('19 fresh original hashes, independent extractions and every minimal citation reproduced; no human approval recorded.')`,
      DIRECTORY, resolve(process.argv[3])], { cwd: ROOT, stdio: "inherit" });
    return;
  }
  if (!["build", "validate"].includes(command)) throw new Error("Use build, validate or verify-originals");
  const outputs = buildArtifacts();
  const destination = resolve(ROOT, process.argv[3] ?? `${DIRECTORY}/generated`);
  if (command === "build") {
    if (destination !== resolve(ROOT, `${DIRECTORY}/generated`) && !destination.startsWith(resolve(ROOT, "work") + "/"))
      throw new Error("Build destination must be generated/ or private work/");
    mkdirSync(destination, { recursive: true });
  }
  for (const [name, value] of Object.entries(outputs)) {
    if (command === "build") writeFileSync(join(destination, name), value);
    else if (readFileSync(join(destination, name), "utf8") !== value) throw new Error(`Non-reproducible review output: ${name}`);
  }
  console.log("First admission preparation: 9 assignments, 7 separate identities; pending only; real resolver diff reproduced.");
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
