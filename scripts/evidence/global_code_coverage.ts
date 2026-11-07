/** Compare research candidates with the production resolver, without changing verification. */
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { isDeepStrictEqual } from "node:util";
import { resolveAirport } from "../../src/resolve.ts";
import { assertDataset, validateDataset } from "../../src/validate.ts";
import { dateNumber } from "../../src/time.ts";
import type { Dataset, Resolution, CodeAssignment, PhysicalAirport, Source } from "../../src/types.ts";

const directory = "research/evidence/global-code-expansion";
const read = <T>(path: string): T => JSON.parse(readFileSync(path, "utf8"));
const hash = (path: string) => createHash("sha256").update(readFileSync(path)).digest("hex");
const json = (value: unknown) => JSON.stringify(value, null, 2) + "\n";
type Code = { scheme: "IATA" | "ICAO"; code: string };
type Claims = { sources: Source[]; airports: PhysicalAirport[]; assignments: CodeAssignment[] };
type Batch = { batchId: string; eventGroupIds: string[]; codes: Code[]; claimsPath: string;
  conditionalReview?: { assignmentIds: string[]; basis: string; remainingBlockers: string[] } };
type Input = { baselinePath: string; baselineSha256: string; formalSha256: string;
  publishedBaselineCommit: string; publicationState: "unmerged_data_PR_candidate";
  from: string; toExclusive: string; reviewedOn: string; batches: Batch[] };
const input = read<Input>(`${directory}/resolver-input.json`);
if (hash(input.baselinePath) !== input.baselineSha256 || hash("data/airports.json") !== input.formalSha256)
  throw new Error("Baseline or formal input fingerprint changed");
const baseline = read<Dataset>(input.baselinePath);
const formal = read<Dataset>("data/airports.json");
assertDataset(baseline); assertDataset(formal);
for (const collection of ["airports", "assignments", "names", "sources"] as const) {
  if (!isDeepStrictEqual(formal[collection].slice(0, baseline[collection].length), baseline[collection]))
    throw new Error(`Published ${collection} changed`);
}
const start = dateNumber(input.from), end = dateNumber(input.toExclusive);
if (!Number.isFinite(start) || !Number.isFinite(end) || start >= end) throw new Error("Invalid measurement period");
const date = (n: number) => new Date(n * 86400000).toISOString().slice(0, 10);
const codeKey = (c: Code) => `${c.scheme}:${c.code}`;
const answer = ({ dataVersion: _version, query: { date: _date, ...query }, ...r }: Resolution) => ({ ...r, query });

function append(base: Dataset, claims: Claims, schemes: Set<string>): Dataset {
  const result = structuredClone(base);
  for (const collection of ["sources", "airports", "assignments"] as const) {
    const id = collection === "sources" ? "sourceId" : collection === "airports" ? "airportId" : "assignmentId";
    const incoming = collection === "assignments" ? claims.assignments.filter(a => schemes.has(a.scheme)) : claims[collection];
    for (const record of incoming) {
      const identity = (record as unknown as Record<string, unknown>)[id];
      const existing = result[collection].find(r => (r as unknown as Record<string, unknown>)[id] === identity);
      if (existing && !isDeepStrictEqual(existing, record)) throw new Error(`Conflicting ${id}: ${String(identity)}`);
      if (!existing) (result[collection] as unknown[]).push(record);
    }
  }
  // Do not promote pending records or sources to verified for a simulated gain.
  assertDataset(result);
  return result;
}

function conditionalReview(candidate: Dataset, assignmentIds: string[]): Dataset {
  const ids = new Set(assignmentIds), dataset = structuredClone(candidate);
  const baseIds = new Set(baseline.assignments.map(a => a.assignmentId));
  const sourceIds = new Set<string>();
  for (const id of ids) {
    if (baseIds.has(id)) throw new Error("Conditional review must not change an existing formal assignment");
    const assignment = dataset.assignments.find(a => a.assignmentId === id);
    if (!assignment) throw new Error(`Missing conditional assignment ${id}`);
    assignment.verificationStatus = "verified";
    assignment.verifiedOn = input.reviewedOn;
    for (const sourceId of assignment.sourceIds) sourceIds.add(sourceId);
  }
  for (const id of sourceIds) {
    const existing = baseline.sources.find(s => s.sourceId === id);
    if (existing && existing.verificationStatus !== "verified")
      throw new Error("Conditional review must not upgrade an existing formal source");
    const source = dataset.sources.find(s => s.sourceId === id);
    if (!source) throw new Error(`Missing conditional source ${id}`);
    source.verificationStatus = "verified";
  }
  const validation = validateDataset(dataset);
  // A conditional conflict must be measured and rejected for admission, not hidden by
  // aborting the research report. All other schema/evidence failures still stop here.
  const fatal = validation.errors.filter(e => !e.startsWith("Conflicting assignments (confirmed conflict): "));
  if (fatal.length) throw new Error(fatal.join("\n"));
  return dataset;
}

function measure(before: Dataset, after: Dataset, codes: Code[]) {
  const transitions: Record<string, number> = {};
  const windows: Record<string, { from: string; toExclusive: string; before: string; after: string;
    beforeAirportId: string | null; afterAirportId: string | null }[]> = {};
  const narrowed: { code: string; from: string; toExclusive: string; days: number }[] = [];
  const resolvedSites = new Map<string, Set<string>>(), gainedCodes = new Set<string>();
  let representedCodeDateQueries = 0, productionResolverCalls = 0, changedResolvedAnswers = 0;
  let changedExistingAnswers = 0, newConflicts = 0;
  const unique = new Map(codes.map(c => [codeKey(c), c]));
  for (const [key, code] of [...unique].sort(([a], [b]) => a.localeCompare(b, "en"))) {
    const points = new Set([start, end]);
    for (const a of [...before.assignments, ...after.assignments]) {
      if (a.scheme !== code.scheme || a.code !== code.code) continue;
      for (const boundary of [a.validFrom.earliest, a.validFrom.latest, a.validTo.earliest, a.validTo.latest]) {
        if (boundary !== null) {
          const n = dateNumber(boundary);
          if (n > start && n < end) points.add(n);
        }
      }
    }
    const sorted = [...points].sort((a, b) => a - b);
    const segments: typeof windows[string] = [];
    for (let i = 0; i < sorted.length - 1; i++) {
      const from = sorted[i]!, to = sorted[i + 1]!, days = to - from;
      const b = resolveAirport(before, code.code, date(from), code.scheme);
      const a = resolveAirport(after, code.code, date(from), code.scheme);
      productionResolverCalls += 2;
      // Every resolver date branch changes only at a finite assignment bound. Check the
      // other end of every partition as an independent guard against a bad partition.
      if (days > 1) {
        const lastB = resolveAirport(before, code.code, date(to - 1), code.scheme);
        const lastA = resolveAirport(after, code.code, date(to - 1), code.scheme);
        productionResolverCalls += 2;
        if (!isDeepStrictEqual(answer(b), answer(lastB)) || !isDeepStrictEqual(answer(a), answer(lastA)))
          throw new Error(`Resolver answer changes inside partition: ${key}/${date(from)}`);
      }
      const transition = `${b.status}->${a.status}`;
      transitions[transition] = (transitions[transition] ?? 0) + days;
      representedCodeDateQueries += days;
      if (b.status === "resolved" && !isDeepStrictEqual(answer(b), answer(a)))
        changedResolvedAnswers += days;
      if (b.status !== "not_found" && !isDeepStrictEqual(answer(b), answer(a))) changedExistingAnswers += days;
      if (b.status !== "conflict" && a.status === "conflict") newConflicts += days;
      if (b.status === "uncertain" && a.status === "resolved") {
        const previous = narrowed.at(-1);
        if (previous && previous.code === key && previous.toExclusive === date(from)) {
          previous.toExclusive = date(to); previous.days += days;
        } else narrowed.push({ code: key, from: date(from), toExclusive: date(to), days });
      }
      if (a.status === "resolved") {
        const sites = resolvedSites.get(key) ?? new Set<string>();
        sites.add(a.airport!.airportId); resolvedSites.set(key, sites);
      }
      if (b.status !== "resolved" && a.status === "resolved") {
        gainedCodes.add(key);
      }
      const row = { from: date(from), toExclusive: date(to), before: b.status, after: a.status,
        beforeAirportId: b.airport?.airportId ?? null, afterAirportId: a.airport?.airportId ?? null };
      const previous = segments.at(-1);
      if (previous && previous.toExclusive === row.from && previous.before === row.before && previous.after === row.after &&
        previous.beforeAirportId === row.beforeAirportId && previous.afterAirportId === row.afterAirportId)
        previous.toExclusive = row.toExclusive;
      else segments.push(row);
    }
    windows[key] = segments;
  }
  return { candidateValidation: validateDataset(after), uniqueCodes: unique.size, representedCodeDateQueries, productionResolverCalls, transitions,
    newResolved: Object.entries(transitions).reduce((n, [k, v]) => n + (k.endsWith("->resolved") && !k.startsWith("resolved->") ? v : 0), 0),
    uncertainToResolved: transitions["uncertain->resolved"] ?? 0,
    notFoundToResolved: transitions["not_found->resolved"] ?? 0,
    uncertainIntervalsNarrowed: narrowed.length, uncertainCodeDaysReduced: narrowed.reduce((n, w) => n + w.days, 0), narrowedWindows: narrowed,
    newlyResolvedCrossSiteReuseCodes: [...resolvedSites].filter(([key, sites]) => gainedCodes.has(key) && sites.size > 1).map(([key]) => key),
    newConflicts, changedResolvedAnswers, changedExistingAnswers, windows };
}

const allClaims: Claims = { sources: [], airports: [], assignments: [] };
const allConditionalIds: string[] = [];
const batchReports = input.batches.map(batch => {
  const claims = read<Claims>(batch.claimsPath);
  for (const collection of ["sources", "airports", "assignments"] as const)
    (allClaims[collection] as unknown[]).push(...claims[collection]);
  const codes = [...batch.codes, ...baseline.assignments.map(a => ({ scheme: a.scheme, code: a.code })),
    ...claims.assignments.map(a => ({ scheme: a.scheme, code: a.code }))];
  const conditional = batch.conditionalReview;
  if (conditional) {
    if (!conditional.basis || !conditional.remainingBlockers.length)
      throw new Error("Conditional scenario requires evidence basis and disclosed blockers");
    allConditionalIds.push(...conditional.assignmentIds);
  }
  return { batchId: batch.batchId, eventGroupIds: batch.eventGroupIds, claimsSha256: hash(batch.claimsPath),
    candidateAssignments: claims.assignments.length,
    comparisons: Object.fromEntries(["IATA", "ICAO", "IATA+ICAO"].map(mode => [mode,
      measure(baseline, append(baseline, claims, new Set(mode.split("+"))), codes)])),
    conditionalReview: conditional ? { ...conditional, officialCoverage: false,
      meaning: "In-memory counterfactual only: review statuses change only for the explicitly listed evidence-qualified claims; date bounds stay unchanged. This calculation grants no authority and publishes no records.",
      comparisons: Object.fromEntries(["IATA", "ICAO", "IATA+ICAO"].map(mode => {
        const schemes = new Set(mode.split("+"));
        const ids = conditional.assignmentIds.filter(id => claims.assignments.some(a => a.assignmentId === id && schemes.has(a.scheme)));
        return [mode, measure(baseline, conditionalReview(append(baseline, claims, schemes), ids), codes)];
      })) } : null };
});
const allCodes = [...input.batches.flatMap(b => b.codes), ...baseline.assignments.map(a => ({ scheme: a.scheme, code: a.code })),
  ...allClaims.assignments.map(a => ({ scheme: a.scheme, code: a.code }))];
const formalComparison = measure(baseline, formal, allCodes);
if (formalComparison.changedResolvedAnswers || formalComparison.newConflicts) throw new Error("Published resolution changed");
const report = { formatVersion: 1, baseline: { path: input.baselinePath, sha256: input.baselineSha256, dataVersion: baseline.dataVersion },
  formal: { path: "data/airports.json", sha256: input.formalSha256, dataVersion: formal.dataVersion },
  publication: { state: input.publicationState, publishedBaselineCommit: input.publishedBaselineCommit,
    actualPublishedNewResolvedQueries: 0,
    meaning: "The serialized 0.12.0 data PR is measured with the production resolver. It remains unmerged; these gains are not yet published production coverage." },
  scope: { from: input.from, toExclusive: input.toExclusive,
    unit: "Unique scheme + code + local Gregorian date, not a flight-traffic coverage percentage",
    measurement: "Production resolveAirport() at both ends of every constant boundary partition; date counts are exact within the stated period.",
    candidates: "Candidate comparisons preserve pending states. Separate counterfactual review comparisons change only whitelisted review states in memory, with disclosed blockers and unchanged date bounds." },
  formalComparison, batches: batchReports,
  combinedCandidateComparisons: Object.fromEntries(["IATA", "ICAO", "IATA+ICAO"].map(mode => [mode,
    measure(baseline, append(baseline, allClaims, new Set(mode.split("+"))), allCodes)])),
  combinedConditionalComparisons: { officialCoverage: false,
    assignmentIds: [...new Set(allConditionalIds)].sort(),
    comparisons: Object.fromEntries(["IATA", "ICAO", "IATA+ICAO"].map(mode => {
      const schemes = new Set(mode.split("+"));
      const ids = allConditionalIds.filter(id => allClaims.assignments.some(a => a.assignmentId === id && schemes.has(a.scheme)));
      return [mode, measure(baseline, conditionalReview(append(baseline, allClaims, schemes), ids), allCodes)];
    })) } };
const output = json(report), path = `${directory}/resolver-diff.json`;
if (process.argv[2] === "build") writeFileSync(path, output);
else if (process.argv[2] === "validate") {
  if (readFileSync(path, "utf8") !== output) throw new Error("Stale global code resolver differential");
} else throw new Error("Expected build or validate");
console.log(json({ formalNewResolved: formalComparison.newResolved,
  formalChangedResolvedAnswers: formalComparison.changedResolvedAnswers, batches: batchReports.length }));
