import { dateNumber, interval, overlaps } from "./time.ts";
import type { Dataset, Resolution } from "./types.ts";

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
    result.candidates.push({
      airport,
      assignment,
      temporalMatch:
        span.certain[0] <= day[0] && span.certain[1] >= day[1]
          ? "certain"
          : "possible",
    });
  }
  result.candidates.sort((a, b) =>
    a.assignment.assignmentId < b.assignment.assignmentId
      ? -1
      : a.assignment.assignmentId > b.assignment.assignmentId
        ? 1
        : 0,
  );
  if (!result.candidates.length)
    return {
      ...result,
      reason: "No historical assignment covers this date.",
    };
  const first = result.candidates.find(
    (candidate) => candidate.temporalMatch === "certain",
  );
  if (first) {
    const competing = result.candidates.filter(
      (candidate) => candidate.airport.airportId !== first.airport.airportId,
    );
    if (competing.some((candidate) => candidate.temporalMatch === "certain"))
      return {
        ...result,
        status: "conflict",
        reason:
          "Assignments for different physical airports cover the whole date.",
      };
    if (!competing.length)
      return {
        ...result,
        status: "resolved",
        airport: first.airport,
        reason:
          "One physical airport has assignment coverage for the whole date.",
      };
  }
  return {
    ...result,
    status: "uncertain",
    reason: "The date bounds leave the physical airport uncertain.",
  };
}
