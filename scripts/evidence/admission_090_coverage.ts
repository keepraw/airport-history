/** Measurements from the actual admitted database; no review hypothesis. */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { isDeepStrictEqual } from "node:util";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { resolveAirport, resolveAirportName } from "../../src/index.ts";
import { assertDataset } from "../../src/validate.ts";
import type { Dataset, Resolution } from "../../src/types.ts";

const ROOT = resolve(fileURLToPath(new URL("../..", import.meta.url)));
const DIRECTORY = "research/admissions/0.9.0";
const read = (path: string) => JSON.parse(readFileSync(resolve(ROOT, path), "utf8"));
const hash = (path: string) => createHash("sha256").update(readFileSync(resolve(ROOT, path))).digest("hex");
const DAY = 86400000, START = "2015-01-01", END = "2026-10-29";
const date = (n: number) => new Date(n).toISOString().slice(0, 10);
const shift = (d: string, n: number) => date(Date.parse(d) + n * DAY);
const answer = ({ dataVersion: _version, ...result }: Resolution) => result;

export function measureFormalAdmission() {
  const base: Dataset = read("test/curated-0.8.0.json"), data: Dataset = read("data/airports.json");
  const approval = read(`${DIRECTORY}/approval.json`);
  if (hash("test/curated-0.8.0.json") !== approval.baseSha256 || data.dataVersion !== "0.9.0")
    throw new Error("Unexpected formal admission baseline/version");
  assertDataset(base); assertDataset(data);
  const transitions: Record<string, number> = {};
  let protectedQueries = 0, protectedNameQueries = 0, changedExistingAnswers = 0;
  let changedPublishedResolved = 0, newConflicts = 0, removedConflicts = 0;
  const rows = approval.approvedAssignments.map((approved: { recordId: string }) => {
    const a = data.assignments.find(a => a.assignmentId === approved.recordId)!;
    let resolvedQueries = 0, uncertainQueries = 0;
    for (let day = Date.parse(START); day <= Date.parse(END); day += DAY) {
      const before = resolveAirport(base, a.code, date(day), a.scheme);
      const after = resolveAirport(data, a.code, date(day), a.scheme);
      const transition = `${before.status}->${after.status}`;
      transitions[transition] = (transitions[transition] ?? 0) + 1;
      if (after.status === "resolved" && before.status !== "resolved") resolvedQueries++;
      if (after.status === "uncertain" && before.status !== "uncertain") uncertainQueries++;
      if (after.status === "conflict" && before.status !== "conflict") newConflicts++;
      if (before.status === "conflict" && after.status !== "conflict") removedConflicts++;
      if (before.status === "resolved" && (after.status !== "resolved" || before.airport?.airportId !== after.airport?.airportId))
        changedPublishedResolved++;
      const expected = date(day) >= a.validFrom.latest! && date(day) < a.validTo.earliest! ? "resolved" : "uncertain";
      if (after.status !== expected || (after.status === "resolved" && after.airport?.airportId !== a.airportId))
        throw new Error(`Unexpected formal window/identity: ${a.code} ${date(day)}`);
    }
    const boundaries = [...new Set([-2, -1, 0, 1].map(n => shift(a.validFrom.latest!, n))
      .concat([-1, 0, 1].map(n => shift(a.validTo.earliest!, n))))].map(localDate => {
      const result = resolveAirport(data, a.code, localDate, a.scheme);
      return { localDate, status: result.status, airportId: result.airport?.airportId ?? null };
    });
    return { assignmentId: a.assignmentId, scheme: a.scheme, code: a.code, airportId: a.airportId,
      certainWindow: [a.validFrom.latest, a.validTo.earliest], resolvedQueries, uncertainQueries, boundaries };
  });
  // Exactly the PR16 benchmark: unique formal scheme/code/date keys and all
  // existing boundaries plus adjacent days, including pre-2015 dates.
  const keys = new Map(base.assignments.map(a => [`${a.scheme}:${a.code}`, a]));
  for (const a of keys.values()) {
    const dates = new Set<string>();
    for (let day = Date.parse(START); day <= Date.parse(END); day += DAY) dates.add(date(day));
    for (const old of base.assignments.filter(old => old.scheme === a.scheme && old.code === a.code))
      for (const d of [old.validFrom.earliest, old.validFrom.latest, old.validTo.earliest, old.validTo.latest])
        if (d) for (const n of [-1, 0, 1]) dates.add(shift(d, n));
    for (const d of dates) {
      const before = resolveAirport(base, a.code, d, a.scheme), after = resolveAirport(data, a.code, d, a.scheme);
      if (!isDeepStrictEqual(answer(before), answer(after))) changedExistingAnswers++;
      if (before.status === "resolved" && (after.status !== "resolved" || before.airport?.airportId !== after.airport?.airportId))
        changedPublishedResolved++;
      if (after.status === "conflict" && before.status !== "conflict") newConflicts++;
      if (before.status === "conflict" && after.status !== "conflict") removedConflicts++;
      protectedQueries++;
    }
  }
  const nameDates = new Set<string>();
  for (let day = Date.parse(START); day <= Date.parse(END); day += DAY) nameDates.add(date(day));
  for (const old of base.names)
    for (const d of [old.validFrom.earliest, old.validFrom.latest, old.validTo.earliest, old.validTo.latest])
      if (d) for (const n of [-1, 0, 1]) nameDates.add(shift(d, n));
  for (const a of base.airports) for (const d of nameDates) {
    const { dataVersion: _before, ...before } = resolveAirportName(base, a.airportId, d);
    const { dataVersion: _after, ...after } = resolveAirportName(data, a.airportId, d);
    if (!isDeepStrictEqual(before, after)) throw new Error("Published name result changed");
    protectedNameQueries++;
  }
  if (changedExistingAnswers || changedPublishedResolved || newConflicts || removedConflicts)
    throw new Error("Published resolver answer/conflict changed");
  const deferred = ["LEMI", "RMU", "MJV"];
  for (const code of deferred) for (let day = Date.parse(START); day <= Date.parse(END); day += DAY) {
    const scheme = code.length === 4 ? "ICAO" : "IATA";
    if (!isDeepStrictEqual(answer(resolveAirport(base, code, date(day), scheme)), answer(resolveAirport(data, code, date(day), scheme))))
      throw new Error("Deferred code changed");
  }
  return { measurement: "Actual production resolveAirport() against formal data/airports.json; no hypothetical accepted dataset",
    baseCommit: approval.baseCommit, baseDatasetSha256: hash("test/curated-0.8.0.json"), formalDatasetSha256: hash("data/airports.json"),
    resolverSha256: hash("src/resolve.ts"), schemaVersion: data.schemaVersion, dataVersion: data.dataVersion,
    period: [START, END], unit: "Unique (scheme, code, whole local date); end of benchmark inclusive",
    beforeCounts: { airports: base.airports.length, assignments: base.assignments.length, names: base.names.length, sources: base.sources.length },
    afterCounts: { airports: data.airports.length, assignments: data.assignments.length, names: data.names.length, sources: data.sources.length },
    rows, transitions, netNewResolved: rows.reduce((n: number, r: { resolvedQueries: number }) => n + r.resolvedQueries, 0),
    newOutsideWindowUncertain: rows.reduce((n: number, r: { uncertainQueries: number }) => n + r.uncertainQueries, 0),
    protectedQueries, protectedNameQueries, changedExistingAnswers, changedPublishedResolved, newConflicts, removedConflicts,
    deferredUnchangedQueries: deferred.length * ((Date.parse(END) - Date.parse(START)) / DAY + 1) };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const output = resolve(ROOT, `${DIRECTORY}/coverage.json`);
  const value = JSON.stringify(measureFormalAdmission(), null, 2) + "\n";
  if (process.argv[2] === "validate") {
    if (readFileSync(output, "utf8") !== value) throw new Error("Non-reproducible actual formal resolver measurement");
  } else if (process.argv[2] === "build") writeFileSync(output, value);
  else throw new Error("Use build or validate");
  console.log("Actual 0.9.0 formal resolver coverage and published-answer regression reproduced.");
}
