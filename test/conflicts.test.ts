import { expect, it } from "vitest";
import { loadDataset } from "../scripts/load.ts";
import { resolveAirport } from "../src/index.ts";
import { validateDataset } from "../src/validate.ts";
import type { Boundary, Dataset } from "../src/types.ts";

const data = await loadDataset();
const exact = (date: string): Boundary => ({
  earliest: date,
  latest: date,
  precision: "exact",
});

function competing(): Dataset {
  return {
    ...data,
    airports: data.airports.slice(0, 3),
    names: [],
    assignments: data.assignments.slice(0, 2).map((row) => ({
      ...row,
      validFrom: exact("2000-01-01"),
      validTo: exact("2002-01-01"),
    })),
  };
}

it("reports conflicts only within the overlap of certain coverage", () => {
  const dataset = competing();
  dataset.assignments[1]!.validFrom = {
    earliest: "2000-01-01",
    latest: "2001-01-01",
    precision: "year",
  };
  expect(validateDataset(dataset).errors.join("\n")).toContain(
    "confirmed conflict",
  );
  const uncertain = resolveAirport(dataset, "TAO", "2000-06-01");
  expect(uncertain.status).toBe("uncertain");
  expect(uncertain.candidates.map((row) => row.temporalMatch)).toEqual([
    "possible",
    "certain",
  ]);
  const conflict = resolveAirport(dataset, "TAO", "2001-06-01");
  expect(conflict).toMatchObject({ status: "conflict", airport: null });
  expect(conflict.candidates).toHaveLength(2);
  dataset.assignments.reverse();
  expect(resolveAirport(dataset, "TAO", "2001-06-01")).toEqual(conflict);
});

it("reports a confirmed conflict with a third, only possible candidate", () => {
  const dataset = competing();
  dataset.assignments.unshift({
    ...dataset.assignments[0]!,
    assignmentId: "a-possible",
    airportId: dataset.airports[2]!.airportId,
    validFrom: { earliest: null, latest: null, precision: "unknown" },
  });
  const validation = validateDataset(dataset);
  expect(validation.errors).toHaveLength(1);
  expect(validation.warnings).toHaveLength(2);
  expect(resolveAirport(dataset, "TAO", "2000-06-01").status).toBe("conflict");
});

it("accepts exact, half-open reuse by distinct physical sites", () => {
  const dataset = competing();
  dataset.assignments[0]!.validTo = exact("2001-01-01");
  dataset.assignments[1]!.validFrom = exact("2001-01-01");
  expect(validateDataset(dataset)).toEqual({ errors: [], warnings: [] });
  expect(resolveAirport(dataset, "TAO", "2000-12-31").airport?.airportId).toBe(
    dataset.airports[0]!.airportId,
  );
  expect(resolveAirport(dataset, "TAO", "2001-01-01").airport?.airportId).toBe(
    dataset.airports[1]!.airportId,
  );
});
