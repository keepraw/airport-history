import { expect, it } from "vitest";
import { loadDataset } from "../scripts/load.ts";
import { validateDataset } from "../src/validate.ts";
import type { Dataset } from "../src/types.ts";
const data = await loadDataset();
const rejected = (mutate: (d: Dataset) => void, message?: string) => {
  const d = structuredClone(data);
  mutate(d);
  const r = validateDataset(d);
  expect(r.errors.length).toBeGreaterThan(0);
  if (message) expect(r.errors.join("\n")).toContain(message);
};
it("accepts curated data and explicitly warns on four code-assignment boundary overlaps", () => {
  const r = validateDataset(data);
  expect(r.errors).toEqual([]);
  expect(r.warnings).toHaveLength(4);
});
it.each(["airportId", "assignmentId", "sourceId"] as const)(
  "rejects duplicate %s",
  (key) =>
    rejected((d) => {
      if (key === "airportId") d.airports.push(d.airports[0]!);
      if (key === "assignmentId") d.assignments.push(d.assignments[0]!);
      if (key === "sourceId") d.sources.push(d.sources[0]!);
    }, `Duplicate ${key}`),
);
it.each(["2023-02-29", "2024-04-31", "0000-01-01", "2024-1-01"])(
  "rejects impossible date %s",
  (date) =>
    rejected((d) => {
      d.sources[0]!.accessedOn = date;
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
it("rejects broken evidence references", () =>
  rejected((d) => {
    d.assignments[0]!.sourceIds = ["absent"];
  }, "missing source"));
it("rejects untraceable known metadata", () =>
  rejected((d) => {
    d.airports[0]!.coordinates.sourceIds = [];
  }, "needs evidence"));
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
it("rejects missing verification date", () =>
  rejected((d) => {
    d.assignments[0]!.verifiedOn = null;
  }, "verifiedOn"));
it("rejects verification earlier than source access", () =>
  rejected((d) => {
    d.assignments[0]!.verifiedOn = "2020-01-01";
  }, "predates"));
it("rejects unreviewed sources of verified assignment", () =>
  rejected((d) => {
    d.sources.find((s) => s.sourceId === "tao-transfer")!.verificationStatus =
      "pending";
  }, "unreviewed"));
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
it("rejects empty license information", () =>
  rejected((d) => {
    d.sources[0]!.license.id = "";
  }));
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
