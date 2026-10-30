import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { resolveAirport } from "../src/resolve.ts";
import { validateDataset } from "../src/validate.ts";
import type { Dataset } from "../src/types.ts";

const read = (path: string) => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
const data: Dataset = read("./curated-0.9.0.json");
const current: Dataset = read("../data/airports.json");
const old: Dataset = read("./curated-0.8.0.json");
const approval = read("../research/admissions/0.9.0/approval.json");

describe("formal 0.9.0 admission", () => {
  it("preserves all released records and admits only exact separately authorized identities/scopes", () => {
    expect(data).toEqual(read("./curated-0.9.0.json"));
    for (const collection of ["airports", "assignments", "sources", "names"] as const)
      expect(data[collection].slice(0, old[collection].length)).toEqual(old[collection]);
    for (const collection of ["airports", "assignments", "sources", "names"] as const)
      expect(current[collection].slice(0, data[collection].length)).toEqual(data[collection]);
    expect(data.assignments.slice(old.assignments.length).map(a => a.code)).toEqual(["VOSR", "VOGB", "VEKI", "VEPY", "VOKU", "LELC"]);
    for (const p of approval.approvedPhysicalAirports) {
      const { scope: _scope, ...record } = p.exactAuthorization;
      expect(data.airports.find(a => a.airportId === p.recordId)).toEqual(record);
    }
    expect(data.assignments.some(a => a.airportId === "apt_f50aecf6-9778-4db7-9027-0e751ffab63a")).toBe(false);
    expect(data.assignments.filter(a => a.scheme === "IATA")).toEqual(old.assignments.filter(a => a.scheme === "IATA"));
    expect(data.names).toEqual(old.names);
  });

  it("resolves exact half-open windows and becomes uncertain when required evidence is unreviewed", () => {
    for (const p of approval.approvedAssignments) {
      const a = p.exactAuthorization;
      const shift = (d: string, n: number) => new Date(Date.parse(d) + n * 86400000).toISOString().slice(0, 10);
      for (const [date, status] of [[shift(a.validFrom.latest, -1), "uncertain"], [a.validFrom.latest, "resolved"],
        [shift(a.validTo.earliest, -1), "resolved"], [a.validTo.earliest, "uncertain"]]) {
        const result = resolveAirport(data, a.code, date!, a.scheme);
        expect(result.status).toBe(status);
        if (status === "resolved") expect(result.airport?.airportId).toBe(a.airportId);
      }
      const broken = structuredClone(data);
      for (const sid of a.sourceIds) broken.sources.find(s => s.sourceId === sid)!.verificationStatus = "pending";
      expect(resolveAirport(broken, a.code, a.validFrom.latest, a.scheme).status).toBe("uncertain");
      expect(validateDataset(broken).errors.some(error => error.includes("unreviewed evidence"))).toBe(true);
    }
  });

  it("binds the actual measured formal gains and full benchmark to the admitted bytes", () => {
    const coverage = read("../research/admissions/0.9.0/coverage.json");
    expect(coverage.formalDatasetSha256).toBe(createHash("sha256").update(readFileSync(new URL("./curated-0.9.0.json", import.meta.url))).digest("hex"));
    expect(coverage.netNewResolved).toBe(4530);
    expect(coverage.newOutsideWindowUncertain).toBe(21390);
    expect(coverage.rows.map((r: { resolvedQueries: number }) => r.resolvedQueries)).toEqual([867, 867, 867, 867, 867, 195]);
    expect(coverage.protectedQueries).toBe(146938);
    expect(coverage.changedExistingAnswers).toBe(0);
    expect(coverage.changedPublishedResolved).toBe(0);
    expect(coverage.newConflicts).toBe(0);
    expect(coverage.removedConflicts).toBe(0);
  });
});
