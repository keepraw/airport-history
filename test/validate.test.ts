import { expect, it } from "vitest";
import { loadDataset } from "../scripts/load.ts";
import { validateDataset } from "../src/validate.ts";
import type { Dataset } from "../src/types.ts";
const production = await loadDataset();
const data: Dataset = {
  ...production,
  airports: production.airports.slice(0, 4),
  assignments: production.assignments.slice(0, 4),
  names: [],
};
const rejected = (mutate: (d: Dataset) => void, message?: string) => {
  const d = structuredClone(data);
  mutate(d);
  const r = validateDataset(d);
  expect(r.errors.length).toBeGreaterThan(0);
  if (message) expect(r.errors.join("\n")).toContain(message);
};
it.each(["airportId", "assignmentId"] as const)("rejects duplicate %s", (key) =>
  rejected((d) => {
    if (key === "airportId") d.airports.push(d.airports[0]!);
    if (key === "assignmentId") d.assignments.push(d.assignments[0]!);
  }, `Duplicate ${key}`),
);
it.each(["2023-02-29", "2024-04-31", "0000-01-01", "2024-1-01"])(
  "rejects impossible date %s",
  (date) =>
    rejected((d) => {
      d.assignments[0]!.validFrom.latest = date;
    }),
);
it("rejects extra fields", () =>
  expect(
    validateDataset({ ...data, surprise: true }).errors.length,
  ).toBeGreaterThan(0));
it("rejects missing required fields", () =>
  expect(validateDataset({ airports: [] }).errors.length).toBeGreaterThan(0));
it("rejects broken airport references", () =>
  rejected((d) => {
    d.assignments[0]!.airportId = "absent";
  }, "missing airport"));
it("rejects coordinates outside Earth", () =>
  rejected((d) => {
    d.airports[0]!.coordinates.value!.latitude = 91;
  }));
it("rejects invalid timezone", () =>
  rejected((d) => {
    d.airports[0]!.timezone.value = "Earth/Moon";
  }, "IANA timezone"));
it("rejects unknown/null mismatch", () =>
  rejected((d) => {
    d.airports[0]!.timezone.value = null;
  }, "unknown status"));
it("rejects IATA/ICAO format mismatches", () =>
  rejected((d) => {
    d.assignments[0]!.scheme = "ICAO";
  }));
it("rejects reused external physical identity", () =>
  rejected((d) => {
    d.airports[1]!.externalIds.ourAirports =
      d.airports[0]!.externalIds.ourAirports!;
  }, "OurAirports identity"));
it("rejects reversed boundary range", () =>
  rejected((d) => {
    d.assignments[0]!.validTo.earliest = "2022-01-01";
  }, "reversed boundary"));
it("rejects empty half-open interval", () =>
  rejected((d) => {
    d.assignments[0]!.validFrom = d.assignments[0]!.validTo;
  }, "impossible"));
it("rejects unsupported precision claims", () =>
  rejected((d) => {
    d.assignments[0]!.validFrom.precision = "day";
  }, "requires both"));
it("rejects a day range spanning two days", () =>
  rejected((d) => {
    d.assignments[2]!.validTo.latest = "2019-04-08";
  }, "day precision"));
it("rejects definite conflicts, retains possible overlaps as warnings", () =>
  rejected((d) => {
    d.assignments.push({
      ...d.assignments[0]!,
      assignmentId: "bad-overlap",
      airportId: d.airports[1]!.airportId,
    });
  }, "Conflicting assignments"));
it("allows entirely unknown boundaries without treating them as exact", () => {
  const d = structuredClone(data);
  d.assignments[0]!.validFrom = {
    earliest: null,
    latest: null,
    precision: "unknown",
  };
  expect(validateDataset(d).errors).toEqual([]);
});

it("allows physical entities absent from a current directory", () => {
  const d = structuredClone(data);
  d.airports[0]!.externalIds = {};
  expect(validateDataset(d).errors).toEqual([]);
});

it("rejects fixed offsets masquerading as IANA timezone rules", () =>
  rejected((d) => {
    d.airports[0]!.timezone.value = "+08:00";
  }));

it("detects duplicate assignment intervals regardless of object key order", () =>
  rejected((d) => {
    const a = d.assignments[0]!;
    d.assignments.push({
      ...a,
      assignmentId: "same-fact-again",
      validFrom: {
        precision: a.validFrom.precision,
        latest: a.validFrom.latest,
        earliest: a.validFrom.earliest,
      },
    });
  }, "Duplicate assignment"));

it("preserves verified, reference and unknown attribute quality", () => {
  const d = structuredClone(data);
  d.airports[0]!.name.status = "verified";
  d.airports[0]!.timezone = {
    value: null,
    status: "unknown",
    note: "Unknown zone.",
  };
  expect(validateDataset(d).errors).toEqual([]);
  expect(d.airports[0]!.coordinates.status).toBe("reference");
});
