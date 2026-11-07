/** Daily production-resolver replay of the exact authorized 0.12.0 proposal. */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { isDeepStrictEqual } from "node:util";
import { measure } from "./policy_coverage.ts";
import { resolveAirport } from "../../src/resolve.ts";
import type { Dataset } from "../../src/types.ts";

const directory = "research/admissions/0.12.0";
const read = <T>(path: string): T => JSON.parse(readFileSync(path, "utf8"));
const hash = (path: string) => createHash("sha256").update(readFileSync(path)).digest("hex");
const base = read<Dataset>("test/curated-0.11.0.json");
const candidate = read<Dataset>("data/airports.json");
const receipt = read<{ authorizationSource: string; executorSha256: string;
  originalVerification: unknown }>(`${directory}/policy-receipt.json`);
if (base.dataVersion !== "0.11.0" || candidate.dataVersion !== "0.12.0" ||
    hash("data/airports.json") !== hash("test/curated-0.12.0.json") ||
    !isDeepStrictEqual(candidate, read<Dataset>(`${directory}/proposed-data.json`)))
  throw new Error("Exact admitted proposal, candidate and immutable snapshot differ");
const measured = measure(base, candidate);
const counts = (data: Dataset) => ({ airports: data.airports.length,
  iataAssignments: data.assignments.filter(a => a.scheme === "IATA").length,
  icaoAssignments: data.assignments.filter(a => a.scheme === "ICAO").length,
  sources: data.sources.length, names: data.names.length });
const additions = candidate.assignments.slice(base.assignments.length);
const rows = additions.map(a => {
  let resolved = 0;
  for (let n = Date.parse("2026-06-12"); n < Date.parse("2026-07-09"); n += 86400000) {
    const date = new Date(n).toISOString().slice(0, 10);
    const before = resolveAirport(base, a.code, date, a.scheme);
    const after = resolveAirport(candidate, a.code, date, a.scheme);
    if (before.status !== "not_found" || after.status !== "resolved" || after.airport?.airportId !== a.airportId)
      throw new Error("Admitted whole-day query did not resolve to the exact physical site");
    resolved++;
  }
  const boundaryChecks = ["2026-06-10", "2026-06-11", "2026-07-09", "2026-07-10"].map(date => {
    const status = resolveAirport(candidate, a.code, date, a.scheme).status;
    if (status !== "uncertain") throw new Error("Excluded observation/outer day was resolved");
    return { date, status };
  });
  return { assignmentId: a.assignmentId, airportId: a.airportId, scheme: a.scheme, code: a.code,
    from: "2026-06-12", toExclusive: "2026-07-09", newResolved: resolved,
    evidenceType: a.evidenceType, sourceIds: a.sourceIds, boundaryChecks };
});
const newResolved = Object.entries(measured.transitions).reduce((n, [k, count]) =>
  n + (k.endsWith("->resolved") && !k.startsWith("resolved->") ? count : 0), 0);
if (newResolved !== 81 || rows.reduce((n, r) => n + r.newResolved, 0) !== newResolved)
  throw new Error("0.12.0 measured gain differs from three independently proven 27-day windows");
const report = { ...measured, mode: "authorized_formal_data_proposal_not_merged",
  authorization: receipt.authorizationSource, executorSha256: receipt.executorSha256,
  publishedMainDataVersion: "0.11.0", publishedMainGrowth: 0,
  measurement: "Unchanged policy_coverage.measure() enumerates the daily corpus and additional boundaries through production resolveAirport(). The exact 0.12.0 bytes are a PR proposal until human merge.",
  baselinePath: "test/curated-0.11.0.json", baselineFileSha256: hash("test/curated-0.11.0.json"),
  candidateFileSha256: hash("data/airports.json"), resolverSha256: hash("src/resolve.ts"),
  policyReceiptSha256: hash(`${directory}/policy-receipt.json`),
  originalVerificationSha256: hash(`${directory}/original-verification.json`),
  beforeCounts: counts(base), afterCounts: counts(candidate), newResolvedQueries: newResolved,
  newResolvedCrossSiteReuses: 0, historicalBoundaryUncertaintyIntervalsNarrowed: 0,
  uncertainToResolved: measured.transitions["uncertain->resolved"] ?? 0,
  notFoundToResolved: measured.transitions["not_found->resolved"] ?? 0, rows };
const output = JSON.stringify(report, null, 2) + "\n", path = `${directory}/coverage.json`;
if (process.argv[2] === "build") writeFileSync(path, output);
else if (process.argv[2] === "validate") {
  if (readFileSync(path, "utf8") !== output) throw new Error("Stale authoritative 0.12.0 resolver measurement");
} else throw new Error("Expected build or validate");
console.log(`Authorized 0.12.0 proposal: ${newResolved} new resolved; current published main growth is 0 until merge.`);
