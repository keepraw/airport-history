/** Actual schema, semantic, source and resolver checks for isolated Korean proposals. */
import { readFileSync, writeFileSync } from "node:fs";
import { isDeepStrictEqual } from "node:util";
import { assertDataset } from "../../src/validate.ts";
import { resolveAirport } from "../../src/resolve.ts";
import type { Dataset, Resolution } from "../../src/types.ts";

const read = <T>(p: string): T => JSON.parse(readFileSync(p, "utf8"));
const [basePath, candidatePath, evidencePath, outputPath] = process.argv.slice(2);
if (!basePath || !candidatePath || !evidencePath || !outputPath) throw new Error("Four paths required");
const base = read<Dataset>(basePath), candidate = read<Dataset>(candidatePath);
const published = read<Dataset>("test/curated-0.10.0.json");
type Evidence = { candidates: { code: string; window: { from: string; toExclusive: string } }[]; daysPerAirport: number };
const evidence = read<Evidence>(evidencePath);
assertDataset(base); assertDataset(candidate);
for (const collection of ["airports", "assignments", "sources", "names"] as const) {
  if (!isDeepStrictEqual(base[collection], candidate[collection].slice(0, base[collection].length)))
    throw new Error("Published records changed");
}
const answer = ({ dataVersion: _v, ...r }: Resolution) => r;
let formalRegressionQueries = 0;
for (const code of ["RKSI", "RKSS", "ICN", "GMP"]) {
  const scheme = code.length === 4 ? "ICAO" : "IATA";
  for (let t = Date.parse("2001-01-01"); t < Date.parse("2026-10-31"); t += 86400000) {
    const date = new Date(t).toISOString().slice(0, 10);
    if (!isDeepStrictEqual(answer(resolveAirport(published, code, date, scheme)), answer(resolveAirport(base, code, date, scheme))))
      throw new Error("Formal historical answer changed");
    formalRegressionQueries++;
  }
}
// All old code/date answers remain equal: additions must use a previously absent code.
const oldKeys = new Set(base.assignments.map(a => `${a.scheme}:${a.code}`));
for (const a of candidate.assignments.slice(base.assignments.length)) {
  if (oldKeys.has(`${a.scheme}:${a.code}`) || a.scheme !== "ICAO") throw new Error("Existing code or IATA expansion");
}
for (const a of base.assignments) {
  const dates = new Set(["2001-01-01", "2026-10-30", ...[a.validFrom, a.validTo].flatMap(b => [b.earliest, b.latest]).filter((s): s is string => !!s)]);
  for (const date of dates) if (!isDeepStrictEqual(answer(resolveAirport(base, a.code, date, a.scheme)), answer(resolveAirport(candidate, a.code, date, a.scheme))))
    throw new Error("Published assignment answer changed");
}
const outcomes: { code: string; date: string; status: string }[] = [];
for (const c of evidence.candidates) {
  for (let t = Date.parse(c.window.from); t < Date.parse(c.window.toExclusive); t += 86400000) {
    const date = new Date(t).toISOString().slice(0, 10);
    const result = resolveAirport(candidate, c.code, date, "ICAO");
    outcomes.push({ code: c.code, date, status: result.status });
    if (result.status !== "resolved") throw new Error(`Blocked candidate ${c.code} ${date}: ${result.status}`);
  }
  for (const date of [new Date(Date.parse(c.window.from) - 86400000).toISOString().slice(0, 10), c.window.toExclusive]) {
    if (resolveAirport(candidate, c.code, date, "ICAO").status === "resolved") throw new Error("Extra boundary day resolved");
  }
}
for (const code of ["ICN", "GMP"]) if (resolveAirport(candidate, code, "2025-05-01", "IATA").status !== resolveAirport(base, code, "2025-05-01", "IATA").status)
  throw new Error("IATA answer changed");
if (outcomes.length !== evidence.daysPerAirport * evidence.candidates.length) throw new Error("Candidate count mismatch");
writeFileSync(outputPath, JSON.stringify({ formalRegressionQueries, formalChangedAnswers: 0, formalNewResolved: 0,
  conditionalResolved: outcomes.length, boundaryExtraResolved: 0, outcomes }, null, 2) + "\n");
