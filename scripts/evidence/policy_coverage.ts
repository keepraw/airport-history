/** Real production resolver comparison. No coverage values are imported from policy decisions. */
import { readFileSync, writeFileSync } from "node:fs";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";
import { createHash } from "node:crypto";
import { assertDataset } from "../../src/validate.ts";
import { resolveAirport } from "../../src/resolve.ts";
import { resolveAirportName } from "../../src/names.ts";
import type { Dataset, Resolution } from "../../src/types.ts";

const ROOT = resolve(fileURLToPath(new URL("../..", import.meta.url)));
const DIR = join(ROOT, "research/policy/generated");
const read = <T>(path: string): T => JSON.parse(readFileSync(path, "utf8"));
const hash = (path: string) => createHash("sha256").update(readFileSync(path)).digest("hex");
const json = (value: unknown) => JSON.stringify(value, null, 2) + "\n";
const DAY = 86400000;
const date = (n: number) => new Date(n * DAY).toISOString().slice(0, 10);
const number = (s: string) => Date.parse(s + "T00:00:00Z") / DAY;
const answer = ({ dataVersion: _version, ...value }: Resolution) => value;

export function measure(base: Dataset, candidate: Dataset) {
  assertDataset(base); assertDataset(candidate);
  for (const collection of ["airports", "assignments", "names", "sources"] as const) {
    if (!isDeepStrictEqual(candidate[collection].slice(0, base[collection].length), base[collection]))
      throw new Error("Published records changed");
  }
  const keys = new Map([...base.assignments, ...candidate.assignments].map(a => [`${a.scheme}:${a.code}`, a]));
  const transitions: Record<string, number> = {};
  const byCode: Record<string, Record<string, number>> = {};
  let changedPublishedResolved = 0, changedExistingAnswers = 0, newConflicts = 0, removedConflicts = 0;
  let codeQueries = 0, nameQueries = 0;
  const days = new Set<number>();
  // These are local calendar-date strings. UTC arithmetic is used only to enumerate dates.
  for (let n = number("2015-01-01"); n <= number("2026-10-29"); n++) days.add(n);
  for (const a of [...base.assignments, ...base.names, ...candidate.assignments, ...candidate.names]) {
    for (const bound of [a.validFrom.earliest, a.validFrom.latest, a.validTo.earliest, a.validTo.latest]) {
      if (bound) for (const offset of [-1, 0, 1]) days.add(number(bound) + offset);
    }
  }
  const check = (before: Resolution, after: Resolution) => {
    if (before.status === "resolved" && !isDeepStrictEqual(answer(before), answer(after))) changedPublishedResolved++;
    if (before.status !== "not_found" && !isDeepStrictEqual(answer(before), answer(after))) changedExistingAnswers++;
    if (before.status !== "conflict" && after.status === "conflict") newConflicts++;
    if (before.status === "conflict" && after.status !== "conflict") removedConflicts++;
  };
  for (const [key, a] of keys) {
    const counts: Record<string, number> = {};
    for (const n of [...days].sort((a, b) => a - b)) {
      const before = resolveAirport(base, a.code, date(n), a.scheme);
      const after = resolveAirport(candidate, a.code, date(n), a.scheme);
      const t = `${before.status}->${after.status}`;
      transitions[t] = (transitions[t] ?? 0) + 1; counts[t] = (counts[t] ?? 0) + 1;
      check(before, after); codeQueries++;
    }
    byCode[key] = counts;
  }
  for (const airport of base.airports) for (const n of days) {
    const before = resolveAirportName(base, airport.airportId, date(n));
    const after = resolveAirportName(candidate, airport.airportId, date(n));
    if (!isDeepStrictEqual({ ...before, dataVersion: "" }, { ...after, dataVersion: "" }))
      throw new Error("Existing formal name query changed");
    nameQueries++;
  }
  if (changedPublishedResolved || changedExistingAnswers || newConflicts || removedConflicts)
    throw new Error("Policy admission changes a published answer or conflict");
  return { transitions, byCode, changedPublishedResolved, changedExistingAnswers, newConflicts, removedConflicts,
    codeQueries, nameQueries, localDates: days.size, interval: ["2015-01-01", "2026-10-29"],
    additionalBoundaryDates: days.size - (number("2026-10-29") - number("2015-01-01") + 1),
    mode: "simulation_only", authorization: null };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const command = process.argv[2];
  const lock = read<{ baseline: { path: string; sha256: string } }>(join(ROOT, "research/policy/input-lock.json"));
  const basePath = join(ROOT, lock.baseline.path);
  if (hash(basePath) !== lock.baseline.sha256) throw new Error("Frozen policy baseline changed");
  const base = read<Dataset>(basePath);
  const candidatePath = command === "gate" ? process.argv[3]! : join(DIR, "simulation-data.json");
  const coverage = { ...measure(base, read<Dataset>(candidatePath)),
    baselineFileSha256: hash(basePath), candidateFileSha256: hash(candidatePath) };
  if (command !== "gate") {
    const mediumPath = join(DIR, "medium-simulation-data.json");
    const medium = { ...measure(base, read<Dataset>(mediumPath)),
      baselineFileSha256: hash(basePath), candidateFileSha256: hash(mediumPath) };
    if (command === "build") writeFileSync(join(DIR, "medium-coverage.json"), json(medium));
    else if (command === "validate" && readFileSync(join(DIR, "medium-coverage.json"), "utf8") !== json(medium))
      throw new Error("Stale medium resolver measurements");
  }
  if (command === "build") writeFileSync(join(DIR, "coverage.json"), json(coverage));
  else if (command === "validate") {
    if (readFileSync(join(DIR, "coverage.json"), "utf8") !== json(coverage)) throw new Error("Stale resolver measurements");
  } else if (command !== "gate") throw new Error("Expected build, validate or gate");
  console.log(`Policy resolver check: ${coverage.transitions["not_found->resolved"] ?? 0} new resolved; published answers preserved.`);
}
