import { readFileSync } from "node:fs";
import { describe, it, expect } from "vitest";
import type { Dataset } from "../src/types.ts";
import { resolveAirport } from "../src/resolve.ts";
import { assertDataset } from "../src/validate.ts";
import { measure } from "../scripts/evidence/policy_coverage.ts";

const read = (path: string): Dataset => JSON.parse(readFileSync(path, "utf8"));
const lock = JSON.parse(readFileSync("research/policy/input-lock.json", "utf8"));
const base = read(lock.baseline.path);
const simulation = read("research/policy/generated/simulation-data.json");
const pending = read("research/policy/generated/pending-data.json");

describe("real policy resolver scopes", () => {
  it("uses frozen 0.9.0 and Schema 3.0.0, with pending candidates separate", () => {
    expect(base.dataVersion).toBe("0.9.0");
    expect(base.schemaVersion).toBe("3.0.0");
    assertDataset(simulation); assertDataset(pending);
    expect(simulation.names).toEqual(base.names);
    expect(simulation.assignments.slice(0, base.assignments.length)).toEqual(base.assignments);
  });
  for (const code of ["VASD", "VEHO", "VOKN"]) {
    it(`${code}: resolves only the 83 complete local dates and preserves unknown sides`, () => {
      for (const [day, status] of [["2026-04-16", "uncertain"], ["2026-04-17", "resolved"],
        ["2026-07-08", "resolved"], ["2026-07-09", "uncertain"]] as const)
        expect(resolveAirport(simulation, code, day, "ICAO").status).toBe(status);
      expect(resolveAirport(pending, code, "2026-05-01", "ICAO").status).toBe("uncertain");
      expect(resolveAirport(base, code, "2026-05-01", "ICAO").status).toBe("not_found");
      const a = simulation.assignments.find(a => a.code === code)!;
      expect(a.validFrom).toEqual({ earliest: null, latest: "2026-04-17", precision: "unknown" });
      expect(a.validTo).toEqual({ earliest: "2026-07-09", latest: null, precision: "unknown" });
      expect(a.evidenceType).toBe("continuity_inference");
    });
  }
  it("rejects a changed published record", () => {
    const changed = structuredClone(simulation);
    changed.airports[0]!.name.note += " changed";
    expect(() => measure(base, changed)).toThrow("Published records changed");
  });
  it("rejects a competing physical site and new resolver conflict", () => {
    const changed = structuredClone(simulation);
    const a = structuredClone(changed.assignments.at(-1)!);
    a.assignmentId = "policy-conflict-test";
    a.airportId = base.airports[0]!.airportId;
    changed.assignments.push(a);
    expect(() => measure(base, changed)).toThrow();
  });
});
