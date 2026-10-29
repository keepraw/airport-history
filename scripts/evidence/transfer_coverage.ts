/** Whole local-date transfer checks using the production resolver, in memory only. */
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { isDeepStrictEqual } from "node:util";
import { resolveAirport } from "../../src/resolve.ts";
import { assertDataset } from "../../src/validate.ts";
import type { Dataset } from "../../src/types.ts";

type Site = { airportId: string };
type Case = { caseKey: string; codes: string[]; oldSite: Site; newSite: Site };
type Window = { from: string; toExclusive: string; status: string; airportId: string | null };
const directory = resolve(process.argv[2] ?? "research/evidence/transfers/generated");
const load = <T>(path: string): T => JSON.parse(readFileSync(path, "utf8"));
const base = load<Dataset>("data/airports.json");
const current = load<Dataset>(`${directory}/proposed-data.json`);
const previous = load<Dataset>("research/evidence/markets/generated/proposed-data.json");
const cases = load<Case[]>(`${directory}/matrix.json`);
const original = new Set(base.assignments.map(a => a.assignmentId));
function hypothesis(data: Dataset): Dataset {
  const result = structuredClone(data);
  for (const s of result.sources) if (s.verificationStatus === "pending") s.verificationStatus = "verified";
  for (const a of result.assignments) if (!original.has(a.assignmentId)) {
    a.verificationStatus = "verified"; a.verifiedOn = "2026-10-29";
  }
  assertDataset(result);
  return result;
}
assertDataset(base); assertDataset(current);
const after = hypothesis(current), prior = hypothesis(previous);
const start = Date.parse("2015-01-01"), end = Date.parse("2026-10-30"), day = 86400000;
const totals = { incrementalResolvedDates: 0, previousHypotheticalResolvedDatesNowUncertain: 0,
  focusedPotentialResolvedDates: 0, formalNewResolvedQueries: 0, changedPublishedResolvedQueries: 0,
  changedPublishedPendingQueries: 0, confirmedConflictDates: 0 };
const reports: Record<string, unknown> = {};
for (const c of cases) {
  let gains = 0, losses = 0, potential = 0, conflicts = 0;
  const byCode: Record<string, unknown> = {};
  for (const code of c.codes) {
    const windows: Window[] = [];
    let oldResolvedDates = 0, newResolvedDates = 0, uncertainDates = 0;
    let crossSitePossibleDates = 0;
    for (let t = start; t < end; t += day) {
      const date = new Date(t).toISOString().slice(0, 10), next = new Date(t + day).toISOString().slice(0, 10);
      const official = resolveAirport(base, code, date, "IATA");
      const pending = resolveAirport(current, code, date, "IATA");
      const old = resolveAirport(prior, code, date, "IATA");
      const now = resolveAirport(after, code, date, "IATA");
      if (official.status === "resolved") {
        if (now.status !== "resolved" || now.airport?.airportId !== official.airport?.airportId) totals.changedPublishedResolvedQueries++;
        if (pending.status !== "resolved" || pending.airport?.airportId !== official.airport?.airportId) totals.changedPublishedPendingQueries++;
      }
      if (now.status === "resolved" && old.status !== "resolved") gains++;
      if (old.status === "resolved" && now.status !== "resolved") losses++;
      if (official.status !== "resolved" && now.status === "resolved") potential++;
      if (now.status === "conflict") conflicts++;
      if (now.status === "uncertain") uncertainDates++;
      const id = now.status === "resolved" ? now.airport!.airportId : null;
      if (id === c.oldSite.airportId) oldResolvedDates++;
      if (id === c.newSite.airportId) newResolvedDates++;
      const possible = new Set(now.candidates.map(x => x.airport.airportId));
      if (possible.has(c.oldSite.airportId) && possible.has(c.newSite.airportId)) crossSitePossibleDates++;
      const status = `${official.status}->${now.status}`;
      if (windows.at(-1)?.status === status && windows.at(-1)?.airportId === id) windows.at(-1)!.toExclusive = next;
      else windows.push({ from: date, toExclusive: next, status, airportId: id });
    }
    byCode[code] = { oldResolvedDates, newResolvedDates, uncertainDates, crossSitePossibleDates, windows };
  }
  totals.incrementalResolvedDates += gains; totals.previousHypotheticalResolvedDatesNowUncertain += losses;
  totals.focusedPotentialResolvedDates += potential; totals.confirmedConflictDates += conflicts;
  reports[c.caseKey] = { incrementalResolvedDates: gains, previousHypotheticalResolvedDatesNowUncertain: losses,
    potentialResolvedDatesAgainstFormal: potential, confirmedConflictDates: conflicts, byCode };
}
let formalRegressionDates = 0;
for (const code of ["TAO", "YNT", "IST", "ISL"]) {
  for (let t = start; t < end; t += day) {
    const date = new Date(t).toISOString().slice(0, 10);
    const before = resolveAirport(base, code, date, "IATA"), now = resolveAirport(after, code, date, "IATA");
    // The hypothetical dataset has a research dataVersion. Compare every answer
    // field after removing that expected metadata difference, including candidates.
    const { dataVersion: _beforeVersion, ...beforeAnswer } = before;
    const { dataVersion: _afterVersion, ...afterAnswer } = now;
    if (!isDeepStrictEqual(beforeAnswer, afterAnswer)) throw new Error(`Published reference changed: ${code} ${date}`);
    formalRegressionDates++;
  }
}
if (totals.changedPublishedResolvedQueries || totals.changedPublishedPendingQueries || totals.confirmedConflictDates)
  throw new Error("Transfer supplement changes a published answer or creates confirmed conflicts");
writeFileSync(`${directory}/transfer-coverage.json`, JSON.stringify({
  period: ["2015-01-01", "2026-10-29"],
  hypothesis: "Only in-memory pending approval; actual resolver enumerates every whole local date. No published records revised.",
  totals, formalReferenceRegressionQueries: formalRegressionDates, cases: reports,
}, null, 2) + "\n");
console.log(JSON.stringify(totals));
