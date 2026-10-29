import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { loadDataset } from "../scripts/load.ts";
import { resolveAirport, resolveAirportName } from "../src/index.ts";
import { assertDataset, validateDataset } from "../src/validate.ts";
import type { Dataset } from "../src/types.ts";

const data = await loadDataset();
const read = (path: string) => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
const frozen = read("./curated-0.7.0.json") as Dataset;
const dossier = read("../research/admissions/0.8.0/dossier.json") as Array<{recordId: string; decision: string; reviewer: string; reviewedOn: string}>;
const sites = {
  KPFN: "apt_d3a329f9-73d0-43f5-90c2-0ba0a0a2e5be",
  KECP: "apt_74a05fd5-53fa-40f8-a3a6-de8cfd7d5e99",
  KISN: "apt_ba1f9f8c-1849-4092-9e91-d641bddb6bc6",
  KXWA: "apt_661b72ea-f84d-4cec-ae34-fddd5e579b3d",
} as const;
const windows = [
  ["KPFN", "proposal-icao-pfn", "2009-05-08", "2010-04-28", 355],
  ["KECP", "proposal-icao-ecp", "2010-05-24", "2014-07-24", 1522],
  ["KISN", "proposal-icao-isn", "2009-05-08", "2014-07-24", 1903],
] as const;

describe("seven explicitly user-approved formal admissions", () => {
  it("ships exactly the approved scope with the same schema and frozen records", () => {
    assertDataset(data);
    expect(data.schemaVersion).toBe("3.0.0");
    expect(data.dataVersion).toBe("0.8.0");
    expect([data.airports.length, data.assignments.length, data.names.length, data.sources.length]).toEqual([27, 43, 3, 77]);
    expect(data.airports.slice(23).map(a => a.airportId)).toEqual(Object.values(sites));
    expect(data.assignments.slice(40).map(a => a.assignmentId)).toEqual(windows.map(w => w[1]));
    expect(data.assignments.filter(a => a.scheme === "IATA")).toEqual(frozen.assignments.filter(a => a.scheme === "IATA"));
    expect(data.names).toEqual(frozen.names);
    expect(createHash("sha256").update(readFileSync(new URL("./curated-0.7.0.json", import.meta.url))).digest("hex"))
      .toBe("31c5735b333881d7afdd527fe4af1db8e28413d5bba114fbf88a4aad0809cff7");
    expect(data).toEqual(read("./curated-0.8.0.json"));
    for (const version of ["0.4.0", "0.5.0", "0.6.0", "0.7.0"]) {
      const old = read(`./curated-${version}.json`) as Dataset;
      for (const collection of ["airports", "assignments", "names", "sources"] as const)
        expect(data[collection].slice(0, old[collection].length)).toEqual(old[collection]);
    }
  });

  it("records the real approving user and retains unknown allocation boundaries", () => {
    expect(dossier).toHaveLength(7);
    expect(dossier.every(d => d.decision === "accepted" && d.reviewer === "keepraw" && d.reviewedOn === "2026-10-28")).toBe(true);
    for (const [code, id, start, end] of windows) {
      const a = data.assignments.find(a => a.assignmentId === id)!;
      expect(a.airportId).toBe(sites[code]);
      expect(a.scheme).toBe("ICAO");
      expect(a.evidenceType).toBe("continuity_inference");
      expect(a.validFrom).toEqual({ earliest: null, latest: start, precision: "unknown" });
      expect(a.validTo).toEqual({ earliest: end, latest: null, precision: "unknown" });
      expect(a.verificationStatus).toBe("verified");
      expect(a.verifiedOn).toBe("2026-10-28");
    }
    for (const a of data.airports.slice(23)) {
      const original = (read("../research/evidence/direct/generated/proposed-data.json") as Dataset)
        .airports.find(p => p.airportId === a.airportId)!;
      expect(a.coordinates.value).toEqual(original.coordinates.value);
      expect(a.coordinates.sourceIds).toEqual(original.coordinates.sourceIds);
      expect(a.name).toEqual(original.name);
      expect(a.externalIds).toEqual(original.externalIds);
      expect(a.name.status).toBe("reference");
      expect(a.coordinates.status).toBe("reference");
      expect(a.timezone).toMatchObject({ value: null, status: "unknown", sourceIds: [] });
    }
  });

  it.each([
    ["KPFN", "2009-05-07", false], ["KPFN", "2009-05-08", true],
    ["KPFN", "2010-04-27", true], ["KPFN", "2010-04-28", false],
    ["KECP", "2010-05-23", false], ["KECP", "2010-05-24", true],
    ["KECP", "2014-07-23", true], ["KECP", "2014-07-24", false],
    ["KISN", "2009-05-08", true], ["KISN", "2014-07-23", true],
    ["KISN", "2014-07-24", false],
  ] as const)("%s on %s respects the approved whole-day window", (code, date, resolved) => {
    const result = resolveAirport(data, code, date, "ICAO");
    expect(result.status === "resolved").toBe(resolved);
    if (resolved) {
      expect(result.airport?.airportId).toBe(sites[code]);
      expect(result.airport?.coordinates.status).toBe("reference");
      expect(result.airport?.timezone.status).toBe("unknown");
    } else expect(result.airport).toBeNull();
  });

  it("independently enumerates all 3,780 actual newly resolved code-date queries", () => {
    let total = 0;
    for (const [code, , start, end, expected] of windows) {
      expect((Date.parse(end) - Date.parse(start)) / 86400000).toBe(expected);
      let resolved = 0;
      for (let day = Date.parse("2000-01-01"); day < Date.parse("2021-01-01"); day += 86400000) {
        const date = new Date(day).toISOString().slice(0, 10);
        const before = resolveAirport(frozen, code, date, "ICAO");
        const after = resolveAirport(data, code, date, "ICAO");
        if (after.status === "resolved") {
          expect(before.status).not.toBe("resolved");
          expect(date >= start && date < end).toBe(true);
          resolved++;
        }
      }
      expect(resolved).toBe(expected);
      total += resolved;
    }
    expect(total).toBe(3780);
    const measured = read("../research/admissions/0.8.0/coverage.json");
    expect(measured.rows.map((r: {resolvedCodeDateQueries: number}) => r.resolvedCodeDateQueries)).toEqual([355, 1522, 1903]);
    expect(measured.totalResolvedCodeDateQueries).toBe(total);
    expect(measured.formalDatasetSha256).toBe(createHash("sha256").update(readFileSync(new URL("../data/airports.json", import.meta.url))).digest("hex"));
  });

  it("cannot resolve an unreviewed source and never promotes blocked codes", () => {
    const broken = structuredClone(data);
    broken.sources.find(s => s.sourceId === "nws-panama")!.verificationStatus = "pending";
    expect(resolveAirport(broken, "KPFN", "2010-01-01", "ICAO").status).toBe("uncertain");
    expect(validateDataset(broken).errors.some(e => e.includes("unreviewed evidence"))).toBe(true);
    for (const code of ["KXWA", "KSGU", "KDXZ", "KHDI", "KRZR"])
      for (const date of ["2010-01-01", "2011-01-13", "2011-06-30", "2013-01-01", "2014-03-14", "2019-10-10", "2020-01-01"])
        expect({ ...resolveAirport(data, code, date, "ICAO"), dataVersion: frozen.dataVersion })
          .toEqual(resolveAirport(frozen, code, date, "ICAO"));
    expect(data.assignments.some(a => a.airportId === sites.KXWA)).toBe(false);
  });

  it("preserves every released code/name result at all old boundaries and adjacent dates", () => {
    const dates = new Set(["1900-01-01", "1997-01-01", "2017-01-01", "2024-01-01", "2030-01-01"]);
    for (const r of [...frozen.assignments, ...frozen.names])
      for (const date of [r.validFrom.earliest, r.validFrom.latest, r.validTo.earliest, r.validTo.latest])
        if (date) for (const delta of [-1, 0, 1]) dates.add(new Date(Date.parse(date) + delta * 86400000).toISOString().slice(0, 10));
    for (const a of frozen.assignments) for (const date of dates)
      expect({ ...resolveAirport(data, a.code, date, a.scheme), dataVersion: frozen.dataVersion })
        .toEqual(resolveAirport(frozen, a.code, date, a.scheme));
    for (const a of frozen.airports) for (const date of dates)
      expect({ ...resolveAirportName(data, a.airportId, date), dataVersion: frozen.dataVersion })
        .toEqual(resolveAirportName(frozen, a.airportId, date));
  });
});
