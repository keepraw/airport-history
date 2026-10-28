import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { fallbackPolicy, projectResolution, resolveEndpoint, resolveFlightEndpoints, dateInZone } from "../../scripts/compat/fly-adapter.ts";
import type { Dataset } from "../../src/types.ts";
import type { FlyFlight, FlyReference } from "../../scripts/compat/fly-adapter.ts";

const dataset = JSON.parse(readFileSync(new URL("../../data/airports.json", import.meta.url), "utf8")) as Dataset;
const sample = JSON.parse(readFileSync(new URL("./fly-directory-sample.json", import.meta.url), "utf8")) as [string, string, string, string, number, number, string][];
const directory = new Map<string, FlyReference>(sample.map(([iata, name, city, country, latitude, longitude, timezone]) =>
  [iata, { iata, name: { en: name }, city: { en: city }, country, countryName: { en: new Intl.DisplayNames(["en"], { type: "region" }).of(country) ?? country }, latitude, longitude, timezone }]));

describe("Fly adapter on real curated history", () => {
  it("selects distinct TAO sites before/after the transfer", () => {
    const before = resolveEndpoint(dataset, "TAO", "2021-08-11", directory);
    const after = resolveEndpoint(dataset, "TAO", "2021-08-13", directory);
    expect(before.result.status).toBe("resolved");
    expect(after.result.status).toBe("resolved");
    expect(before.airportId).not.toBe(after.airportId);
    expect(before.coordinates?.value).not.toEqual(after.coordinates?.value);
    expect(before.coordinates?.status).toBe("reference");
    expect(before.city).toBeNull();
  });
  it("retains HKG uncertain boundary, known old site, and absent coverage", () => {
    expect(resolveEndpoint(dataset, "HKG", "1997-01-01", directory).result.status).toBe("resolved");
    const boundary = resolveEndpoint(dataset, "HKG", "1998-07-06", directory);
    expect(boundary.result.status).toBe("uncertain");
    expect(boundary.airportId).toBeNull();
    expect(boundary.canCalculateDistance).toBe(false);
    expect(boundary.result.candidates).toHaveLength(2);
    expect(resolveEndpoint(dataset, "JFK", "2020-01-01", directory).result.status).toBe("not_found");
    expect(resolveEndpoint(dataset, "JFK", "2020-01-01", directory).referenceFallback?.iata).toBe("JFK");
    expect(resolveEndpoint(dataset, "KTI", "2025-09-09", directory).historicalIdentityVerified).toBe(false);
  });
  it("defines conflict policy without inventing assignments in production history", () => {
    expect(fallbackPolicy("conflict")).toBe("review_required");
    expect(fallbackPolicy("uncertain")).toBe("review_required");
    expect(fallbackPolicy("not_found")).toBe("reference_label_only");
    expect(fallbackPolicy("invalid_input")).toBe("invalid");
    // Resolver conflict behavior is exercised by the repository's existing conflicts.test.ts.
  });
  it("does not fill missing historic attributes from the present-day site", () => {
    const result = resolveEndpoint(dataset, "TAO", "2021-08-11", directory).result;
    // Project the existing resolver regression's missing-attribute condition only.
    // No code assignment or historical interval is added or changed.
    const missing = structuredClone(result);
    missing.airport!.coordinates = { value: null, status: "unknown", sourceIds: [], note: "Existing missing-attribute regression condition" };
    missing.airport!.timezone = { value: null, status: "unknown", sourceIds: [], note: "Existing missing-attribute regression condition" };
    const view = projectResolution(missing, directory.get("TAO")!);
    expect(view.historicalIdentityVerified).toBe(true);
    expect(view.canCalculateDistance).toBe(false);
    expect(view.timezone?.value).toBeNull();
    expect(view.referenceFallback?.timezone).toBe("Asia/Shanghai");
  });
  it("uses each endpoint's local date, UTC conversion, and diversion's actual arrival", () => {
    const flight: FlyFlight = { serviceDate: "2021-08-11", origin: { iata: "HKG" }, destination: { iata: "HKG" },
      divertedTo: { iata: "TAO" }, scheduledDeparture: "2021-08-11T15:00:00Z", scheduledArrival: "2021-08-11T17:00:00Z",
      actualArrival: "2021-08-12T17:00:00Z" };
    const original = JSON.stringify(flight);
    const result = resolveFlightEndpoints(dataset, flight, directory);
    expect(result.origin.localDate).toBe("2021-08-11");
    expect(result.plannedDestination.localDate).toBe("2021-08-12");
    expect(result.actualDestination.localDate).toBe("2021-08-13");
    expect(result.actualDestination.view?.airportId).toBe(resolveEndpoint(dataset, "TAO", "2021-08-13", directory).airportId);
    delete flight.actualArrival;
    expect(resolveFlightEndpoints(dataset, flight, directory).actualDestination.localDate).toBeNull();
    flight.actualArrival = "2021-08-12T17:00:00Z";
    expect(JSON.stringify(flight)).toBe(original);
    expect(dateInZone("2021-08-11T23:00:00-07:00", "Asia/Shanghai")).toBe("2021-08-12");
    expect(dateInZone("2021-08-11T23:00:00", "Asia/Shanghai")).toBeNull();
  });
});
