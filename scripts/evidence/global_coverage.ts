/** Test-only review hypothesis. Never serializes verified source/record states. */
import { readFileSync, writeFileSync } from "node:fs";
import { resolveAirport } from "../../src/resolve.ts";
import { assertDataset } from "../../src/validate.ts";
import type { Dataset, CodeAssignment } from "../../src/types.ts";
import { resolve } from "node:path";

type Window = { from: string; toExclusive: string; status: string };
const directory = resolve(process.argv[2] ?? "research/evidence/global/generated");
const base: Dataset = JSON.parse(readFileSync("data/airports.json", "utf8"));
const proposed: Dataset = JSON.parse(readFileSync(`${directory}/proposed-data.json`, "utf8"));
assertDataset(base);
assertDataset(proposed);
const original = new Set(base.assignments.map(a => a.assignmentId));
const additions = proposed.assignments.filter(a => !original.has(a.assignmentId));
const hypothetical = structuredClone(proposed);
for (const s of hypothetical.sources) {
  if (s.verificationStatus === "pending") s.verificationStatus = "verified";
}
for (const a of hypothetical.assignments) {
  if (!original.has(a.assignmentId)) {
    a.verificationStatus = "verified";
    a.verifiedOn = "2026-10-29";
  }
}
assertDataset(hypothetical);
const key = (a: CodeAssignment) => `${a.scheme}:${a.code}`;
const keys = new Map([...base.assignments, ...additions].map(a => [key(a), a]));
const perCode: Record<string, unknown> = {};
const perAssignment = new Map(additions.map(a => [a.assignmentId, {assignmentId:a.assignmentId, airportId:a.airportId,
  scheme:a.scheme, code:a.code, newlyResolvedDays:0, resolvedWindows:[] as Window[],
  firstResolvedDate:null as string|null, lastResolvedDate:null as string|null,
  unresolvedCrossSiteDays:0}]));
let potentialNewResolvedQueries = 0, changedPublishedResolvedQueries = 0, changedPendingResolvedQueries = 0;
const start = Date.parse("2015-01-01"), end = Date.parse("2026-10-30"), day = 86400000;
for (const [k, a] of keys) {
  const windows: Window[] = [];
  let gains = 0, conflicts = 0;
  for (let timestamp = start; timestamp < end; timestamp += day) {
    const date = new Date(timestamp).toISOString().slice(0,10);
    const next = new Date(timestamp+day).toISOString().slice(0,10);
    const before = resolveAirport(base,a.code,date,a.scheme);
    const pending = resolveAirport(proposed,a.code,date,a.scheme);
    const after = resolveAirport(hypothetical,a.code,date,a.scheme);
    if (before.status === "resolved") {
      if (after.status !== "resolved" || after.airport?.airportId !== before.airport?.airportId) changedPublishedResolvedQueries++;
      if (pending.status !== "resolved" || pending.airport?.airportId !== before.airport?.airportId) changedPendingResolvedQueries++;
    }
    const added = after.status === "resolved" && before.status !== "resolved";
    if (added) { gains++; potentialNewResolvedQueries++; }
    if (after.status === "conflict") conflicts++;
    const status = `${before.status}->${after.status}`;
    if (windows.at(-1)?.status === status) windows.at(-1)!.toExclusive = next;
    else windows.push({from:date,toExclusive:next,status});
    const identities = new Set(after.candidates.map(c => c.airport.airportId));
    for (const candidate of additions.filter(x => key(x) === k)) {
      const row = perAssignment.get(candidate.assignmentId)!;
      if (identities.size > 1 && after.status === "uncertain") row.unresolvedCrossSiteDays++;
      if (added && after.airport?.airportId === candidate.airportId) {
        row.newlyResolvedDays++;
        row.firstResolvedDate ??= date;
        row.lastResolvedDate = date;
        if (row.resolvedWindows.at(-1)?.toExclusive === date) row.resolvedWindows.at(-1)!.toExclusive = next;
        else row.resolvedWindows.push({from:date,toExclusive:next,status:"resolved"});
      }
    }
  }
  if (additions.some(x => key(x) === k)) perCode[k] = {potentialNewResolvedQueries:gains, confirmedConflictDays:conflicts, windows};
}
if (changedPublishedResolvedQueries || changedPendingResolvedQueries) throw new Error("Research would change a published resolved result");
const report = {period:["2015-01-01","2026-10-29"], hypothesis:"All new pending sources and assignments approved in memory only; physical coordinates retain reference status.",
  formalNewResolvedQueries:0, potentialNewResolvedQueries, changedPublishedResolvedQueries, changedPendingResolvedQueries,
  codeDateUnit:"One namespace + code + whole local Gregorian date; unique across the combined proposal, not a completeness percentage.",
  byAssignment:[...perAssignment.values()],byCode:perCode};
writeFileSync(`${directory}/query-coverage.json`,JSON.stringify(report,null,2)+"\n");
console.log(JSON.stringify({potentialNewResolvedQueries,changedPublishedResolvedQueries,changedPendingResolvedQueries}));
