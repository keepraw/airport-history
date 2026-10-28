/** Experimental read adapter. No Fly archive, code or timestamps are rewritten. */
import { resolveAirport } from "../../src/index.ts";
import type { Dataset, Resolution, Fact } from "../../src/types.ts";

// Structural subset of Keepraw-Fly's actual interfaces, checked in the pinned cross-repo experiment.
export interface FlyReference {
  iata: string;
  name: { en: string };
  city: { en: string };
  country: string;
  countryName: { en: string };
  latitude: number;
  longitude: number;
  timezone: string;
}
export interface FlyFlight {
  serviceDate: string;
  origin: { iata: string };
  destination: { iata: string };
  divertedTo?: { iata: string };
  scheduledDeparture: string;
  scheduledArrival: string;
  actualDeparture?: string;
  actualArrival?: string;
}
export interface EndpointView {
  result: Resolution;
  airportId: string | null;
  historicalIdentityVerified: boolean;
  coordinates: Fact<{ latitude: number; longitude: number }> | null;
  timezone: Fact<string> | null;
  displayName: Fact<string> | null;
  city: null; // Curated history currently has no historical city/country fields.
  country: null;
  referenceFallback: FlyReference | null;
  canCalculateDistance: boolean;
  notice: string;
}

export function fallbackPolicy(status: Resolution["status"]): "historical" | "reference_label_only" | "review_required" | "invalid" {
  if (status === "resolved") return "historical";
  if (status === "not_found") return "reference_label_only";
  if (status === "uncertain" || status === "conflict") return "review_required";
  return "invalid";
}

export function projectResolution(result: Resolution, reference: FlyReference | null): EndpointView {
  const airport = result.status === "resolved" ? result.airport : null;
  const point = airport?.coordinates.value;
  const validPoint = !!point && Number.isFinite(point.latitude) && Number.isFinite(point.longitude) &&
    Math.abs(point.latitude) <= 90 && Math.abs(point.longitude) <= 180;
  return {
    result, airportId: airport?.airportId ?? null,
    historicalIdentityVerified: airport !== null,
    coordinates: airport?.coordinates ?? null, timezone: airport?.timezone ?? null,
    displayName: airport?.name ?? null, city: null, country: null,
    referenceFallback: reference,
    canCalculateDistance: validPoint,
    notice: airport ? "Historical code/site resolved. Each attribute keeps its own reference/verified/unknown status; city and country unavailable in history."
      : `History ${result.status}; current-directory labels may be displayed with an unverified badge. Historical route coordinates are withheld.`,
  };
}

export function resolveEndpoint(dataset: Dataset, code: string, localDate: string, directory: ReadonlyMap<string, FlyReference>): EndpointView {
  return projectResolution(resolveAirport(dataset, code, localDate), directory.get(code.toUpperCase()) ?? null);
}

export function dateInZone(timestamp: string, timezone: string): string | null {
  if (!/(?:Z|[+-]\d{2}:\d{2})$/.test(timestamp) || !Number.isFinite(Date.parse(timestamp))) return null;
  try {
    const parts = new Intl.DateTimeFormat("en", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit" })
      .formatToParts(new Date(timestamp));
    const part = (key: string) => parts.find((p) => p.type === key)?.value;
    return `${part("year")}-${part("month")}-${part("day")}`;
  } catch { return null; }
}

export interface TimedEndpoint {
  code: string;
  localDate: string | null;
  dateBasis: "historical_site_timezone" | "current_reference_timezone" | "unknown";
  view: EndpointView | null;
}

export function resolveTimestampEndpoint(dataset: Dataset, code: string, timestamp: string | undefined,
  directory: ReadonlyMap<string, FlyReference>): TimedEndpoint {
  const reference = directory.get(code);
  if (!timestamp) return { code, localDate: null, dateBasis: "unknown", view: null };
  // Prefer an unambiguous timezone shared by every reviewed site for this code.
  // A reference zone can seed a query, but it cannot silently verify the date.
  const ids = new Set(dataset.assignments.filter((a) => a.scheme === "IATA" && a.code === code).map((a) => a.airportId));
  const zones = [...ids].map((id) => dataset.airports.find((a) => a.airportId === id)?.timezone.value);
  const unique = new Set(zones);
  const zone = zones.length && unique.size === 1 && zones[0] ? zones[0] : reference?.timezone;
  const seedDate = zone ? dateInZone(timestamp, zone) : null;
  if (!seedDate) return { code, localDate: null, dateBasis: "unknown", view: null };
  let localDate = seedDate;
  const seen = new Set<string>();
  for (let i = 0; i < 3; i++) {
    if (seen.has(localDate)) return { code, localDate: null, dateBasis: "unknown", view: null };
    seen.add(localDate);
    const view = resolveEndpoint(dataset, code, localDate, directory);
    const historicalZone = view.timezone?.value;
    if (!historicalZone) return { code, localDate, dateBasis: "current_reference_timezone", view };
    const corrected = dateInZone(timestamp, historicalZone);
    if (!corrected) return { code, localDate: null, dateBasis: "unknown", view: null };
    if (corrected === localDate) return { code, localDate, dateBasis: "historical_site_timezone", view };
    localDate = corrected;
  }
  return { code, localDate: null, dateBasis: "unknown", view: null };
}

export function resolveFlightEndpoints(dataset: Dataset, flight: FlyFlight, directory: ReadonlyMap<string, FlyReference>) {
  return {
    origin: resolveTimestampEndpoint(dataset, flight.origin.iata, flight.actualDeparture ?? flight.scheduledDeparture, directory),
    plannedDestination: resolveTimestampEndpoint(dataset, flight.destination.iata, flight.scheduledArrival, directory),
    actualDestination: flight.divertedTo
      // Planned arrival time belongs to the planned destination. With no actual diversion
      // arrival timestamp, the diversion's historical query date remains unknown.
      ? resolveTimestampEndpoint(dataset, flight.divertedTo.iata, flight.actualArrival, directory)
      : resolveTimestampEndpoint(dataset, flight.destination.iata, flight.actualArrival ?? flight.scheduledArrival, directory),
  };
}
