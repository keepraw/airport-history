import { resolveAirport as resolveCodeAssignment } from "./resolve.ts";
import { resolveAirportName as resolveOfficialName } from "./names.ts";
import horizon from "./query-horizon.json" with { type: "json" };
import type { AirportNameResolution, Dataset, Resolution } from "./types.ts";

export const queryHorizon = Object.freeze(horizon);
const outsideHorizon = `Local date is outside the supported range [${queryHorizon.fromInclusive}, ${queryHorizon.toExclusive}).`;

function isOutsideHorizon(date: string): boolean {
  return date < queryHorizon.fromInclusive || date >= queryHorizon.toExclusive;
}

export function resolveAirport(
  dataset: Dataset,
  code: string,
  date: string,
  scheme: "IATA" | "ICAO" = "IATA",
): Resolution {
  if (!isOutsideHorizon(date))
    return resolveCodeAssignment(dataset, code, date, scheme);
  const result = resolveCodeAssignment(
    { ...dataset, assignments: [] },
    code,
    date,
    scheme,
  );
  return result.status === "invalid_input"
    ? result
    : { ...result, reason: outsideHorizon };
}

export function resolveAirportName(
  dataset: Dataset,
  airportId: string,
  date: string,
): AirportNameResolution {
  if (!isOutsideHorizon(date))
    return resolveOfficialName(dataset, airportId, date);
  const result = resolveOfficialName(
    { ...dataset, airports: [] },
    airportId,
    date,
  );
  return result.status === "invalid_input"
    ? result
    : { ...result, reason: outsideHorizon };
}

export type {
  AirportName,
  AirportNameCandidate,
  AirportNameResolution,
  Boundary,
  Candidate,
  CodeAssignment,
  Dataset,
  Fact,
  PhysicalAirport,
  Resolution,
} from "./types.ts";
