/** Global batch 5: measure formal and proposal-only effects with the unchanged production resolver. */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";
import { measure } from "../../../../scripts/evidence/policy_coverage.ts";
import { resolveAirport } from "../../../../src/resolve.ts";
import type { Dataset } from "../../../../src/types.ts";

const ROOT = resolve(fileURLToPath(new URL("../../../..", import.meta.url)));
const DIR = "research/evidence/global-batch-5";
const read = (path: string) => JSON.parse(readFileSync(resolve(ROOT, path), "utf8"));
const hash = (path: string) => createHash("sha256").update(readFileSync(resolve(ROOT, path))).digest("hex");
const shift = (day: string, n: number) => new Date(Date.parse(day + "T00:00:00Z") + n * 86400000).toISOString().slice(0, 10);

export function measureBatch() {
  const published: Dataset = read("test/curated-0.10.0.json");
  const formal: Dataset = read("data/airports.json");
  // Formal effect of this batch: the formal file must be byte-identical to the frozen 0.10.0 snapshot.
  const formalUnchanged = hash("data/airports.json") === hash("test/curated-0.10.0.json") && isDeepStrictEqual(formal, published);
  if (!formalUnchanged) throw new Error("Research batch changed formal data");
  const proposals = read(`${DIR}/proposals.json`);
  if (proposals.formal !== false || proposals.authorization !== null) throw new Error("Proposal claims authority");
  const hypothetical: Dataset = {
    ...formal,
    dataVersion: "0.11.0",
    airports: [...formal.airports, ...proposals.airports],
    assignments: [...formal.assignments, ...proposals.assignments],
    sources: [...formal.sources, ...proposals.sources],
  };
  const simulated = measure(formal, hypothetical);
  const rows = proposals.assignments.map((a: Dataset["assignments"][number]) => {
    const counts = simulated.byCode[`${a.scheme}:${a.code}`]!;
    const probes = [a.validFrom.latest, a.validTo.earliest].filter(Boolean).flatMap(d => [-1, 0].map(n => shift(d!, n)));
    return {
      assignmentId: a.assignmentId, scheme: a.scheme, code: a.code, airportId: a.airportId,
      certainWindow: [a.validFrom.latest, a.validTo.earliest],
      boundaryProbes: probes.map(localDate => {
        const r = resolveAirport(hypothetical, a.code, localDate, a.scheme);
        return { localDate, status: r.status, airportId: r.airport?.airportId ?? null };
      }),
      transitions: counts,
    };
  });
  return {
    formal: {
      dataVersion: formal.dataVersion, unchanged: true,
      counts: { airports: formal.airports.length, assignments: formal.assignments.length, sources: formal.sources.length, names: formal.names.length },
      newResolved: 0, newUncertain: 0, newConflicts: 0, changedPublishedAnswers: 0,
    },
    proposalSimulation: {
      meaning: "NOT formal coverage. Production resolveAirport() over formal 0.10.0 plus the unapproved proposal records only.",
      authorization: null, transitions: simulated.transitions, codeQueries: simulated.codeQueries,
      nameQueries: simulated.nameQueries, localDates: simulated.localDates, interval: simulated.interval,
      changedPublishedResolved: simulated.changedPublishedResolved, changedExistingAnswers: simulated.changedExistingAnswers,
      newConflicts: simulated.newConflicts, removedConflicts: simulated.removedConflicts, rows,
    },
    resolverSha256: hash("src/resolve.ts"), formalSha256: hash("data/airports.json"), proposalsSha256: hash(`${DIR}/proposals.json`),
  };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const value = JSON.stringify(measureBatch(), null, 2) + "\n";
  const output = resolve(ROOT, `${DIR}/coverage.json`);
  if (process.argv[2] === "build") writeFileSync(output, value);
  else if (process.argv[2] === "validate") {
    if (readFileSync(output, "utf8") !== value) throw new Error("Non-reproducible global batch 5 coverage");
  } else throw new Error("Use build or validate");
  const c = JSON.parse(value);
  console.log(`Global batch 5: formal new resolved 0; proposal-only simulation ${c.proposalSimulation.transitions["not_found->resolved"] ?? 0} resolved / ` +
    `${c.proposalSimulation.transitions["not_found->uncertain"] ?? 0} uncertain (not counted).`);
}
