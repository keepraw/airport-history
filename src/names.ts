import { hasReviewedEvidence } from "./evidence.ts";
import { dateNumber, interval, overlaps } from "./time.ts";
import type {
  AirportName,
  AirportNameResolution,
  Dataset,
  Source,
} from "./types.ts";

/** Pure, offline canonical official-name resolution. Validate the dataset first.
 * Aliases and translations never establish an official-name interval.
 */
export function resolveAirportName(
  dataset: Dataset,
  airportId: string,
  date: string,
): AirportNameResolution {
  const result: AirportNameResolution = {
    status: "not_found",
    dataVersion: dataset.dataVersion,
    query: { airportId, date },
    airport: null,
    name: null,
    language: null,
    historicallyVerified: false,
    candidates: [],
    evidence: [],
    reason: "",
  };
  const start = dateNumber(date);
  if (!Number.isFinite(start) || !airportId.trim())
    return {
      ...result,
      status: "invalid_input",
      reason: "Use an airportId and a valid local Gregorian YYYY-MM-DD date.",
    };
  const airport = dataset.airports.find((a) => a.airportId === airportId);
  if (!airport)
    return { ...result, reason: "No physical airport has this permanent ID." };
  result.airport = airport;
  const sources = new Map(dataset.sources.map((s) => [s.sourceId, s]));
  const evidenceFor = (ids: string[]): Source[] =>
    [...new Set(ids)]
      .sort()
      .flatMap((id) => (sources.has(id) ? [sources.get(id)!] : []));
  const day: [number, number] = [start, start + 1];
  for (const record of dataset.names) {
    if (record.airportId !== airportId || record.kind !== "official") continue;
    const span = interval(record);
    if (!overlaps(day, span.possible)) continue;
    result.candidates.push({
      record,
      temporalMatch:
        span.certain[0] <= start && span.certain[1] >= start + 1
          ? "certain"
          : "possible",
      evidence: evidenceFor(record.sourceIds),
    });
  }
  result.candidates.sort((a, b) =>
    a.record.nameId < b.record.nameId
      ? -1
      : a.record.nameId > b.record.nameId
        ? 1
        : 0,
  );
  result.evidence = evidenceFor(
    result.candidates.flatMap((c) => c.record.sourceIds),
  );
  if (!result.candidates.length)
    return {
      ...result,
      status: "reference",
      name: airport.name.value,
      evidence: evidenceFor(airport.name.sourceIds),
      reason:
        "Reference label only: no official-name record covers this date. The label is not historically verified for the query date, regardless of its static fact status.",
    };
  const sameName = (a: AirportName, b: AirportName) =>
    a.name === b.name && a.language === b.language;
  for (let i = 0; i < result.candidates.length; i++) {
    const a = result.candidates[i]!.record;
    for (const { record: b } of result.candidates.slice(i + 1)) {
      if (
        !sameName(a, b) &&
        hasReviewedEvidence(a, sources) &&
        hasReviewedEvidence(b, sources) &&
        Math.max(interval(a).certain[0], interval(b).certain[0], day[0]) <
          Math.min(interval(a).certain[1], interval(b).certain[1], day[1])
      )
        return {
          ...result,
          status: "conflict",
          reason:
            "Different canonical official names have conflicting reviewed intervals on this date.",
        };
    }
  }
  const certain = result.candidates.find(
    (c) =>
      c.temporalMatch === "certain" && hasReviewedEvidence(c.record, sources),
  );
  if (
    certain &&
    result.candidates.every(
      (c) =>
        sameName(c.record, certain.record) &&
        hasReviewedEvidence(c.record, sources),
    )
  )
    return {
      ...result,
      status: "resolved",
      name: certain.record.name,
      language: certain.record.language,
      historicallyVerified: true,
      reason:
        "A reviewed canonical official name covers the whole local date; physical identity and reference attributes are unchanged.",
    };
  return {
    ...result,
    status: "uncertain",
    reason:
      "Official-name boundaries, evidence coverage or review do not establish one name for the whole date. Inspect candidates; no name is selected.",
  };
}
