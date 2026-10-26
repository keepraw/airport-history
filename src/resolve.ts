import { dateNumber, interval, overlaps } from "./time.ts";
import { hasReviewedEvidence } from "./evidence.ts";
import type { Candidate, Dataset, Resolution, Source } from "./types.ts";

/** Pure, offline, date-only resolver. Validate a dataset once before using it. */
export function resolveAirport(
  dataset: Dataset,
  code: string,
  date: string,
  scheme: "IATA" | "ICAO" = "IATA",
): Resolution {
  const normalized = code.trim().toUpperCase();
  const result: Resolution = {
    status: "not_found",
    dataVersion: dataset.dataVersion,
    query: { code: normalized, date, scheme },
    airport: null,
    candidates: [],
    evidence: [],
    reason: "",
  };
  const start = dateNumber(date);
  if (
    !Number.isFinite(start) ||
    !["IATA", "ICAO"].includes(scheme) ||
    !(scheme === "IATA" ? /^[A-Z]{3}$/ : /^[A-Z]{4}$/).test(normalized)
  ) {
    return {
      ...result,
      status: "invalid_input",
      reason:
        "Use a valid code and a local Gregorian YYYY-MM-DD date (no timestamp).",
    };
  }
  const day: [number, number] = [start, start + 1];
  const sources = new Map(dataset.sources.map((s) => [s.sourceId, s]));
  const evidenceFor = (ids: string[]): Source[] =>
    [...new Set(ids)]
      .sort()
      .flatMap((id) => (sources.has(id) ? [sources.get(id)!] : []));
  for (const assignment of dataset.assignments) {
    if (assignment.scheme !== scheme || assignment.code !== normalized)
      continue;
    const span = interval(assignment);
    if (!overlaps(day, span.possible)) continue;
    const airport = dataset.airports.find(
      (a) => a.airportId === assignment.airportId,
    );
    if (!airport)
      throw new Error(
        `Invalid dataset: missing airport ${assignment.airportId}`,
      );
    const candidate: Candidate = {
      airport,
      assignment,
      temporalMatch:
        span.certain[0] <= day[0] && span.certain[1] >= day[1]
          ? "certain"
          : "possible",
      evidence: evidenceFor([
        ...assignment.sourceIds,
        ...airport.name.sourceIds,
        ...airport.coordinates.sourceIds,
        ...airport.timezone.sourceIds,
      ]),
    };
    result.candidates.push(candidate);
  }
  result.candidates.sort((a, b) =>
    a.assignment.assignmentId < b.assignment.assignmentId
      ? -1
      : a.assignment.assignmentId > b.assignment.assignmentId
        ? 1
        : 0,
  );
  result.evidence = evidenceFor(
    result.candidates.flatMap((c) => c.evidence.map((s) => s.sourceId)),
  );
  if (!result.candidates.length)
    return {
      ...result,
      reason:
        "No historical assignment covers this date; no current-data fallback is performed.",
    };
  for (let i = 0; i < result.candidates.length; i++) {
    for (const other of result.candidates.slice(i + 1)) {
      const a = result.candidates[i]!;
      const left = interval(a.assignment).certain;
      const right = interval(other.assignment).certain;
      if (
        a.airport.airportId !== other.airport.airportId &&
        hasReviewedEvidence(a.assignment, sources) &&
        hasReviewedEvidence(other.assignment, sources) &&
        Math.max(left[0], right[0], day[0]) <
          Math.min(left[1], right[1], day[1])
      ) {
        return {
          ...result,
          status: "conflict",
          reason:
            "Different physical airports have conflicting confirmed assignments.",
        };
      }
    }
  }
  const certain = result.candidates.filter(
    (c) =>
      c.temporalMatch === "certain" &&
      hasReviewedEvidence(c.assignment, sources),
  );
  const first = certain[0];
  if (
    first &&
    result.candidates.every(
      (c) =>
        c.airport.airportId === first.airport.airportId &&
        hasReviewedEvidence(c.assignment, sources),
    )
  ) {
    return {
      ...result,
      status: "resolved",
      airport: first.airport,
      reason:
        "Verified assignment covers the whole local date. Attribute status remains independent.",
    };
  }
  return {
    ...result,
    status: "uncertain",
    reason:
      "Boundary, evidence coverage or verification is insufficient; inspect candidates and obtain more evidence or flight time.",
  };
}
