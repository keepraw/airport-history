/** Formal before/after comparison and separately labelled unauthorized hypotheses. */
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { isDeepStrictEqual } from "node:util";
import { measure } from "./policy_coverage.ts";
import { assertDataset } from "../../src/validate.ts";
import { resolveAirport } from "../../src/resolve.ts";
import type { Dataset } from "../../src/types.ts";

const baseDir = "research/evidence/priority-markets";
const read = <T>(path: string): T => JSON.parse(readFileSync(path, "utf8"));
const base = read<Dataset>("test/curated-0.10.0.json");
const formal = read<Dataset>("data/airports.json");
if (!isDeepStrictEqual(base, formal)) throw new Error("Published 0.10.0 data changed");
const actual = measure(base, formal);
type Decision = {
  status: string; code: string; label: string; arp: string; simulationAirportId: string;
  sourceIds: string[]; proposedWindow: { from: string; toExclusive: string };
};
type LockedSource = { sourceId: string; title: string; url: string; accessedAt: string };
const decisions = read<{ decisions: Decision[] }>(`${baseDir}/generated/dry-run.json`).decisions;
const sources = read<{ sources: LockedSource[] }>(`${baseDir}/source-lock.json`).sources;
const simulation = structuredClone(formal);
function coordinate(arp: string): { latitude: number; longitude: number } {
  const m = /^(\d{2})(\d{2})(\d{2})N (\d{3})(\d{2})(\d{2})E$/.exec(arp);
  if (!m) throw new Error("Unsupported research ARP");
  return { latitude: +m[1]! + +m[2]! / 60 + +m[3]! / 3600,
    longitude: +m[4]! + +m[5]! / 60 + +m[6]! / 3600 };
}
for (const d of decisions.filter(d => d.status === "draft_window")) {
  for (const sid of d.sourceIds) if (!simulation.sources.some(s => s.sourceId === sid)) {
    const s = sources.find(s => s.sourceId === sid)!;
    simulation.sources.push({ sourceId: sid, title: s.title, url: s.url, accessedOn: s.accessedAt.slice(0, 10),
      sourceType: "primary", verificationStatus: "verified",
      license: { id: "LicenseRef-Quotation-Only", url: s.url, note: "Only short factual citations retained; full redistribution not established." },
      note: "IN-MEMORY UNAUTHORIZED HYPOTHESIS; no human review or production verification is claimed." });
  }
  if (simulation.airports.some(a => a.airportId === d.simulationAirportId)) throw new Error("Duplicate hypothesis ID");
  simulation.airports.push({ airportId: d.simulationAirportId,
    name: { value: d.label, status: "reference", sourceIds: d.sourceIds, note: "Disposable simulation label; no legal name timeline." },
    coordinates: { value: coordinate(d.arp), status: "reference", sourceIds: d.sourceIds,
      note: "Research AIP ARP, pending physical identity review." },
    timezone: { value: null, status: "unknown", sourceIds: [], note: "Asia/Seoul used only for disclosed date arithmetic; no timezone admission." },
    externalIds: {} });
  simulation.assignments.push({ assignmentId: `dry-run-${d.code.toLowerCase()}`, airportId: d.simulationAirportId,
    scheme: "ICAO", code: d.code, verificationStatus: "verified", verifiedOn: "2026-10-30",
    validFrom: { earliest: null, latest: d.proposedWindow.from, precision: "unknown" },
    validTo: { earliest: d.proposedWindow.toExclusive, latest: null, precision: "unknown" },
    evidenceType: "continuity_inference", sourceIds: d.sourceIds,
    note: "UNAUTHORIZED IN-MEMORY DRY RUN. Physical identity and intervening NOTAM screening remain pending. First allocation and withdrawal unknown." });
}
assertDataset(simulation);
const hypothetical = measure(formal, simulation);
const boundaryChecks = decisions.filter(d => d.status === "draft_window").map(d => {
  const dates = ["2025-04-16", "2025-04-17", "2025-04-18", "2025-05-14", "2025-05-15", "2025-05-16"];
  const statuses = dates.map(date => ({ date, formal: resolveAirport(formal, d.code, date, "ICAO").status,
    hypothetical: resolveAirport(simulation, d.code, date, "ICAO").status }));
  if (statuses.some(s => s.hypothetical !== (["2025-04-18", "2025-05-14"].includes(s.date) ? "resolved" : "uncertain")))
    throw new Error("Partial Korean edge date was resolved");
  return { code: d.code, statuses };
});
const cases = read<{ cases: { codes: string[] }[] }>(`${baseDir}/assessments.json`).cases;
const focused = new Map(cases.flatMap(c => c.codes).filter(k => !k.startsWith("FAA:")).map(k => [k, k.split(":")]));
let focusedQueries = 0;
for (const [, [scheme, code]] of focused) for (let t = Date.parse("2015-01-01"); t < Date.parse("2026-10-30"); t += 86400000) {
  const date = new Date(t).toISOString().slice(0, 10);
  const before = resolveAirport(base, code!, date, scheme as "IATA" | "ICAO");
  const after = resolveAirport(formal, code!, date, scheme as "IATA" | "ICAO");
  if (!isDeepStrictEqual(before, after)) throw new Error("Focused formal answer changed");
  focusedQueries++;
}
const hash = (path: string) => createHash("sha256").update(readFileSync(path)).digest("hex");
const formalNewResolved = Object.entries(actual.transitions).reduce((total, [transition, count]) =>
  total + (transition.endsWith("->resolved") && !transition.startsWith("resolved->") ? count : 0), 0);
const report = { baselineSha256: hash("test/curated-0.10.0.json"), formalSha256: hash("data/airports.json"),
  formalComparison: { ...actual, mode: "actual_unchanged_formal_data", newResolvedQueries: formalNewResolved },
  focusedFormalRegressionQueries: focusedQueries,
  hypotheticalComparison: { ...hypothetical, mode: "in_memory_unauthorized_draft_only",
    physicalIdentityReviewCompleted: false, interveningNotamScreeningCompleted: false }, boundaryChecks };
const output = JSON.stringify(report, null, 2) + "\n";
const path = `${baseDir}/generated/coverage.json`;
if (process.argv[2] === "build") writeFileSync(path, output);
else if (process.argv[2] === "validate") {
  if (readFileSync(path, "utf8") !== output) throw new Error("Stale priority-market resolver measurements");
} else throw new Error("Expected build or validate");
console.log(`Priority markets: 0 formal new resolved; ${hypothetical.transitions["not_found->resolved"] ?? 0} unauthorized hypothetical resolved.`);
