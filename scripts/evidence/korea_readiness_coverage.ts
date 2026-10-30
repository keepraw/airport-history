/** Real resolver measurements; every candidate exists only in memory. */
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { isDeepStrictEqual } from "node:util";
import { resolveAirport } from "../../src/resolve.ts";
import { assertDataset } from "../../src/validate.ts";
import type { Dataset } from "../../src/types.ts";

const dir = "research/evidence/code-dates/korea-readiness";
const read = <T>(p: string): T => JSON.parse(readFileSync(p, "utf8"));
const formal = read<Dataset>("data/airports.json");
const published = read<Dataset>("test/curated-0.10.0.json");
if (!isDeepStrictEqual(published, formal)) throw new Error("Published dataset changed");
type Decision = { code: string; label: string; arp: string; simulationAirportId: string; sourceIds: string[] };
const decisions = read<{ decisions: Decision[] }>("research/evidence/priority-markets/generated/dry-run.json")
  .decisions.filter(d => ["RKSI", "RKSS"].includes(d.code));
const sources = read<{ sources: { sourceId: string; title: string; url: string; accessedAt: string }[] }>(
  "research/evidence/priority-markets/source-lock.json").sources;
const conditional = structuredClone(formal);
for (const d of decisions) {
  const m = /^(\d{2})(\d{2})(\d{2})N (\d{3})(\d{2})(\d{2})E$/.exec(d.arp)!;
  for (const sid of d.sourceIds) if (!conditional.sources.some(s => s.sourceId === sid)) {
    const s = sources.find(s => s.sourceId === sid)!;
    conditional.sources.push({ sourceId: sid, title: s.title, url: s.url, accessedOn: s.accessedAt.slice(0, 10),
      sourceType: "primary", verificationStatus: "verified", license: { id: "LicenseRef-Quotation-Only", url: s.url,
        note: "Research quotation only; no complete original redistribution." },
      note: "UNAUTHORIZED IN-MEMORY HYPOTHESIS. No production source admission." });
  }
  conditional.airports.push({ airportId: d.simulationAirportId,
    name: { value: d.label, status: "reference", sourceIds: d.sourceIds, note: "Simulation only; permanent identity absent." },
    coordinates: { value: { latitude: +m[1]! + +m[2]! / 60 + +m[3]! / 3600,
      longitude: +m[4]! + +m[5]! / 60 + +m[6]! / 3600 }, status: "reference", sourceIds: d.sourceIds,
      note: "AIP ARP; independent evidence package remains unapproved." },
    timezone: { value: null, status: "unknown", sourceIds: [], note: "No formal timezone admission." }, externalIds: {} });
  conditional.assignments.push({ assignmentId: `pr24-conditional-${d.code.toLowerCase()}`, airportId: d.simulationAirportId,
    scheme: "ICAO", code: d.code, verificationStatus: "verified", verifiedOn: "2026-10-30",
    validFrom: { earliest: null, latest: "2025-04-18", precision: "unknown" },
    validTo: { earliest: "2025-05-15", latest: null, precision: "unknown" },
    evidenceType: "continuity_inference", sourceIds: d.sourceIds,
    note: "UNAUTHORIZED CONDITIONAL SIMULATION. Requires separate identities, policy authorization and a production adapter." });
}
const gated = structuredClone(conditional);
for (const a of gated.assignments.filter(a => a.assignmentId.startsWith("pr24-conditional-")))
  a.verificationStatus = "pending";
assertDataset(conditional);
assertDataset(gated);
let formalRegressionQueries = 0;
const transitions: Record<string, number> = {};
const gatedTransitions: Record<string, number> = {};
for (const code of ["RKSI", "RKSS", "ICN", "GMP"]) {
  const scheme = code.length === 4 ? "ICAO" : "IATA";
  for (let t = Date.parse("2001-01-01"); t < Date.parse("2026-10-31"); t += 86400000) {
    const date = new Date(t).toISOString().slice(0, 10);
    const before = resolveAirport(published, code, date, scheme);
    const actual = resolveAirport(formal, code, date, scheme);
    if (!isDeepStrictEqual(before, actual)) throw new Error("Formal historical answer changed");
    formalRegressionQueries++;
    for (const [dataset, counts] of [[conditional, transitions], [gated, gatedTransitions]] as const) {
      const key = `${actual.status}->${resolveAirport(dataset, code, date, scheme).status}`;
      counts[key] = (counts[key] ?? 0) + 1;
    }
  }
}
const boundaries = decisions.map(d => ({ code: d.code,
  dates: ["2025-04-16", "2025-04-17", "2025-04-18", "2025-04-30", "2025-05-01", "2025-05-14", "2025-05-15", "2025-05-16"].map(date => ({
    date, formal: resolveAirport(formal, d.code, date, "ICAO").status,
    gated: resolveAirport(gated, d.code, date, "ICAO").status,
    conditional: resolveAirport(conditional, d.code, date, "ICAO").status })) }));
for (const b of boundaries) for (const r of b.dates) {
  if (r.formal !== "not_found" || r.gated !== "uncertain" ||
      r.conditional !== (r.date >= "2025-04-18" && r.date < "2025-05-15" ? "resolved" : "uncertain"))
    throw new Error("Unexpected Korean boundary answer");
}
const h = (p: string) => createHash("sha256").update(readFileSync(p)).digest("hex");
const report = { mode: "actual_resolveAirport_in_memory_only", publishedSha256: h("test/curated-0.10.0.json"),
  formalSha256: h("data/airports.json"), policyFileSha256: h(`${dir}/policy.json`),
  identityBatchFileSha256: h(`${dir}/identity-batch.json`), formalRegressionQueries,
  formalNewResolved: 0, formalChangedAnswers: 0, formalNewConflicts: 0,
  gatedTransitions, conditionalTransitions: transitions, boundaries,
  conditionalResolved: transitions["not_found->resolved"] ?? 0,
  gatedResolved: gatedTransitions["not_found->resolved"] ?? 0,
  formalAirportIdsCreated: 0, productionEligible: false,
  limits: "Current formal data have no Korean identities or assignments. Pending and conditional simulations do not establish authorization or historical truth; date sweep is disclosed, not global coverage." };
const output = JSON.stringify(report, null, 2) + "\n";
if (process.argv[2] === "build") writeFileSync(`${dir}/coverage.json`, output);
else if (process.argv[2] !== "validate" || readFileSync(`${dir}/coverage.json`, "utf8") !== output)
  throw new Error("Stale Korean resolver measurement");
console.log(`Korea: ${formalRegressionQueries} formal regression queries; 0 formal / ${report.gatedResolved} gated / ${report.conditionalResolved} conditional resolved.`);
