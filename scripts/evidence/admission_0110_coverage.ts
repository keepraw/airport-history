/** Production resolver comparison of the serialized China 0.11.0 admission. */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";
import { measure } from "./policy_coverage.ts";
import { resolveAirport } from "../../src/resolve.ts";
import type { Dataset } from "../../src/types.ts";

const ROOT = resolve(fileURLToPath(new URL("../..", import.meta.url)));
const DIRECTORY = "research/admissions/0.11.0";
const BASELINE = "test/curated-0.10.0.json";
const SNAPSHOT = "test/curated-0.11.0.json";
const read = <T>(path: string): T => JSON.parse(readFileSync(resolve(ROOT, path), "utf8"));
const hash = (path: string) => createHash("sha256").update(readFileSync(resolve(ROOT, path))).digest("hex");
const baselineSha256 = "2268bdd3426e0d459b7b46d1214b165e3ab90f3526d4f2528f60238f4ee94b13";

export function measureChinaAdmission(candidatePath = "data/airports.json") {
  const base = read<Dataset>(BASELINE), candidate = read<Dataset>(candidatePath);
  if (hash(BASELINE) !== baselineSha256 || candidate.dataVersion !== "0.11.0" ||
      hash(candidatePath) !== hash(SNAPSHOT) ||
      !isDeepStrictEqual(candidate, read<Dataset>(`${DIRECTORY}/proposed-data.json`)))
    throw new Error("China formal candidate, immutable snapshot and bundle differ");
  const measured = measure(base, candidate);
  const counts = (data: Dataset) => ({ airports: data.airports.length,
    iataAssignments: data.assignments.filter(a => a.scheme === "IATA").length,
    icaoAssignments: data.assignments.filter(a => a.scheme === "ICAO").length,
    sources: data.sources.length, names: data.names.length });
  const statuses = (side: "before" | "after", status: string) =>
    Object.entries(measured.transitions).reduce((total, [key, count]) =>
      total + (key.split("->")[side === "before" ? 0 : 1] === status ? count : 0), 0);
  // Probe deferred codes separately; these do not inflate the existing fixed query corpus.
  const deferredCodes = ["LYG", "YBP", "LZO", "ZSLG", "ZUYB", "ZULZ"];
  const deferredCodeChecks = deferredCodes.flatMap(code => ["2015-01-01", "2020-01-01", "2026-10-29"].map(localDate => {
    const scheme = code.length === 3 ? "IATA" : "ICAO";
    const before = resolveAirport(base, code, localDate, scheme).status;
    const after = resolveAirport(candidate, code, localDate, scheme).status;
    if (before !== "not_found" || after !== "not_found")
      throw new Error("Identity-only admission unexpectedly introduced code coverage");
    return { code, scheme, localDate, before, after };
  }));
  if (!isDeepStrictEqual(base.assignments, candidate.assignments) ||
      !isDeepStrictEqual(base.names, candidate.names))
    throw new Error("This identity-only batch must preserve all assignment and name records");
  return { ...measured, mode: "formal_china_identity_admission",
    measurement: "Exact formal data/airports.json and immutable admission snapshot; production resolveAirport(), not hypothetical candidates.",
    authorization: "Explicit China Batch 7 user task; machine physical-identity policy only.",
    baselineCommit: "1e35d424a42377ea80c5c4ab53e1ee3d492b5acf",
    baselinePath: BASELINE, baselineFileSha256: hash(BASELINE), candidateFileSha256: hash(candidatePath),
    snapshot: SNAPSHOT, resolverSha256: hash("src/resolve.ts"), dataVersion: candidate.dataVersion,
    schemaVersion: candidate.schemaVersion, beforeCounts: counts(base), afterCounts: counts(candidate),
    queryCounts: { before: { resolved: statuses("before", "resolved"), uncertain: statuses("before", "uncertain"),
      conflict: statuses("before", "conflict"), notFound: statuses("before", "not_found") },
      after: { resolved: statuses("after", "resolved"), uncertain: statuses("after", "uncertain"),
        conflict: statuses("after", "conflict"), notFound: statuses("after", "not_found") } },
    newResolvedQueries: measured.transitions["not_found->resolved"] ?? 0,
    newResolvedCrossSiteReuses: 0, historicalBoundaryUncertaintyIntervalsNarrowed: 0,
    identityOnly: true, deferredCodeChecks };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const command = process.argv[2];
  const coverage = measureChinaAdmission();
  const path = resolve(ROOT, `${DIRECTORY}/coverage.json`);
  const value = JSON.stringify(coverage, null, 2) + "\n";
  if (command === "build") writeFileSync(path, value);
  else if (command === "validate") {
    if (readFileSync(path, "utf8") !== value) throw new Error("Stale China production resolver measurements");
  } else throw new Error("Use build or validate");
  console.log(`China 0.11.0: +${coverage.afterCounts.airports - coverage.beforeCounts.airports} identities; ` +
    `+${coverage.newResolvedQueries} resolved queries; all published answers preserved.`);
}
