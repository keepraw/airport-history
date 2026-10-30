/** Measure the real policy admission with the unchanged production resolver gate. */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";
import { measure } from "./policy_coverage.ts";
import { resolveAirport } from "../../src/resolve.ts";
import type { Dataset } from "../../src/types.ts";

const ROOT = resolve(fileURLToPath(new URL("../..", import.meta.url)));
const DIRECTORY = "research/admissions/0.10.0";
const SNAPSHOT = "test/curated-0.10.0.json";
const read = (path: string) => JSON.parse(readFileSync(resolve(ROOT, path), "utf8"));
const hash = (path: string) => createHash("sha256").update(readFileSync(resolve(ROOT, path))).digest("hex");
const shift = (day: string, n: number) => new Date(Date.parse(day + "T00:00:00Z") + n * 86400000).toISOString().slice(0, 10);

export function measureFormalAdmission(candidatePath = SNAPSHOT) {
  const receipt = read(`${DIRECTORY}/policy-receipt.json`);
  const base: Dataset = read(receipt.baseline.path), candidate: Dataset = read(candidatePath);
  if (hash(receipt.baseline.path) !== receipt.baseline.sha256 || candidate.dataVersion !== "0.10.0" ||
      hash(candidatePath) !== hash(SNAPSHOT) || !isDeepStrictEqual(candidate, read(`${DIRECTORY}/proposed-data.json`)))
    throw new Error("Formal candidate, immutable snapshot and policy bundle differ");
  const measured = measure(base, candidate);
  const rows = candidate.assignments.slice(base.assignments.length).map(a => {
    const counts = measured.byCode[`${a.scheme}:${a.code}`]!;
    const dates = [...new Set([-2, -1, 0, 1].flatMap(n =>
      [shift(a.validFrom.latest!, n), shift(a.validTo.earliest!, n)]))].sort();
    const boundaries = dates.map(localDate => {
      const result = resolveAirport(candidate, a.code, localDate, a.scheme);
      const expected = localDate >= a.validFrom.latest! && localDate < a.validTo.earliest! ? "resolved" : "uncertain";
      if (result.status !== expected || (expected === "resolved" && result.airport?.airportId !== a.airportId))
        throw new Error(`Unexpected formal boundary/identity: ${a.code} ${localDate}`);
      return { localDate, status: result.status, airportId: result.airport?.airportId ?? null };
    });
    return { assignmentId: a.assignmentId, code: a.code, scheme: a.scheme, airportId: a.airportId,
      certainWindow: [a.validFrom.latest, a.validTo.earliest], boundaries,
      newResolved: counts["not_found->resolved"] ?? 0, newUncertain: counts["not_found->uncertain"] ?? 0 };
  });
  const counts = (data: Dataset) => ({ airports: data.airports.length, assignments: data.assignments.length,
    sources: data.sources.length, names: data.names.length });
  return { ...measured, mode: "formal_policy_admission", authorization: receipt.authorizationSource,
    measurement: "Production resolver on the exact formal 0.10.0 candidate, replayable from its immutable snapshot.",
    baselineFileSha256: hash(receipt.baseline.path), candidateFileSha256: hash(candidatePath),
    snapshot: SNAPSHOT, baseCommit: receipt.baseline.baseCommit,
    policySha256: receipt.policySha256, executorSha256: receipt.executorSha256,
    resolverSha256: hash("src/resolve.ts"), schemaVersion: candidate.schemaVersion, dataVersion: candidate.dataVersion,
    beforeCounts: counts(base), afterCounts: counts(candidate), rows };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const command = process.argv[2];
  // Build measures actual formal bytes; later validation replays the unchanged admission snapshot.
  const coverage = measureFormalAdmission(command === "build" ? "data/airports.json" : SNAPSHOT);
  const output = resolve(ROOT, `${DIRECTORY}/coverage.json`);
  const value = JSON.stringify(coverage, null, 2) + "\n";
  if (command === "build") writeFileSync(output, value);
  else if (command === "validate") {
    if (readFileSync(output, "utf8") !== value) throw new Error("Non-reproducible formal policy admission coverage");
  } else throw new Error("Use build or validate");
  console.log(`Actual formal 0.10.0: ${coverage.transitions["not_found->resolved"] ?? 0} new resolved; ` +
    `${coverage.transitions["not_found->uncertain"] ?? 0} new uncertain; published answers and conflicts preserved.`);
}
