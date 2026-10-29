import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { describe, expect, it } from "vitest";
import { resolveAirport, resolveAirportName } from "../src/index.ts";
import type { Dataset } from "../src/types.ts";
import { validateDataset } from "../src/validate.ts";
import baseline from "../research/discovery/curated-baseline.json" with { type: "json" };
import coverage from "./pr10-coverage.json" with { type: "json" };
import frozen04 from "./curated-0.4.0.json" with { type: "json" };
import frozen05 from "./curated-0.5.0.json" with { type: "json" };
import frozen06 from "./curated-0.6.0.json" with { type: "json" };
import frozen07 from "./curated-0.7.0.json" with { type: "json" };

// Version-specific admission assertions; current-data preservation is tested separately.
const data = frozen07 as Dataset;
const previous = frozen06 as Dataset;
const sites = {
  OPRN: "apt_d28173b7-5c8b-4012-8eed-18f96c13a0ce",
  OPIS: "apt_896e8191-7c0b-4a94-bc14-9dcd7e35feac",
  LTBA: "apt_d8f290d3-11cc-4441-af6d-f4dd52d3b8dc",
  LTFM: "apt_92a92544-1808-487a-85e0-0fa995e1de82",
  EDDB: "apt_f642eef8-1864-43c4-8944-47aaa7ac35ce",
  UACC: "apt_99f19660-7609-49c5-b221-ed4a37046566",
} as const;
const nextDate = (date: string, delta = 1) => {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + delta);
  return d.toISOString().slice(0, 10);
};
const added = data.assignments.filter((a) => !previous.assignments.some((p) => p.assignmentId === a.assignmentId));

describe("0.7.0 preserves all three reviewed datasets", () => {
  it.each([frozen04, frozen05, frozen06])("preserves every $dataVersion record", (frozen) => {
    for (const [key, idKey] of [["airports", "airportId"], ["assignments", "assignmentId"],
      ["names", "nameId"], ["sources", "sourceId"]] as const) {
      const current = new Map((data[key] as unknown as Record<string, unknown>[]).map((r) => [r[idKey], r]));
      for (const r of frozen[key] as unknown as Record<string, unknown>[]) expect(current.get(r[idKey])).toEqual(r);
    }
  });
  it("pins immutable bytes independently of the editable baseline manifest", async () => {
    const pins = [
      ["0.4.0", "17aa754e7868db145aa002e4c765fc593f8066c8b4566a4a4ac6eb7738b91c6a"],
      ["0.5.0", "43bb532977cc5df61e6f34b55cab86c7aad3518d5a33ec89745ceccd49d3b67e"],
      ["0.6.0", "a64086c6864cdf6e2d3ab3df72ffec704a3bdef3cc3d70f1c29cb2d7eeeabe80"],
    ] as const;
    expect(baseline.preservedBaselines.map((b) => b.dataVersion)).toEqual(pins.map(([version]) => version));
    for (const [version, hash] of pins) {
      const b = baseline.preservedBaselines.find((b) => b.dataVersion === version)!;
      expect(b.record).toBe(`test/curated-${version}.json`);
      expect(b.sha256).toBe(hash);
      const bytes = await readFile(new URL(`../${b.record}`, import.meta.url));
      expect(createHash("sha256").update(bytes).digest("hex")).toBe(hash);
    }
    expect(baseline.preservedBaselines[2]!.baseCommit).toBe("cb0f003c21f0cb77cf4576dbe915cee1c9971a91");
    const bytes = await readFile(new URL("./curated-0.7.0.json", import.meta.url));
    expect(createHash("sha256").update(bytes).digest("hex")).toBe(baseline.sha256);
    expect(data.dataVersion).toBe("0.7.0");
    expect(data.schemaVersion).toBe("3.0.0");
    expect([data.airports.length, data.assignments.length, data.names.length, data.sources.length]).toEqual([23, 40, 3, 70]);
    expect(data.assignments.filter((a) => a.scheme === "ICAO")).toHaveLength(12);
    expect(data.airports).toEqual(previous.airports);
    expect(data.names).toEqual(previous.names);
  });
  it("preserves every old code and name result at every old boundary and adjacent day", () => {
    const dates = new Set(["1900-01-01", "2011-10-15", "2016-04-29", "2018-05-03", "2019-04-06",
      "2020-06-08", "2020-10-25", "2020-10-31", "2025-07-22", "2025-07-23", "2026-10-24", "2026-10-25", "2030-01-01"]);
    for (const r of [...previous.assignments, ...previous.names])
      for (const date of [r.validFrom.earliest, r.validFrom.latest, r.validTo.earliest, r.validTo.latest])
        if (date) for (const delta of [-1, 0, 1]) dates.add(nextDate(date, delta));
    // The new records use six previously absent ICAO keys. Exact preservation of all
    // old records plus an unchanged resolver also protects every other old query date.
    const oldKeys = new Set(previous.assignments.map((a) => `${a.scheme}:${a.code}`));
    expect(added).toHaveLength(6);
    for (const a of added) expect(oldKeys.has(`${a.scheme}:${a.code}`)).toBe(false);
    for (const a of previous.assignments) for (const date of dates) {
      const old = resolveAirport(previous, a.code, date, a.scheme);
      expect({ ...resolveAirport(data, a.code, date, a.scheme), dataVersion: old.dataVersion }).toEqual(old);
    }
    for (const a of previous.airports) for (const date of dates) {
      const old = resolveAirportName(previous, a.airportId, date);
      expect({ ...resolveAirportName(data, a.airportId, date), dataVersion: old.dataVersion }).toEqual(old);
    }
    expect(validateDataset(data)).toEqual(validateDataset(previous));
  });
});

describe("historical ICAO observations and conservative boundaries", () => {
  it.each([
    ["OPRN", "2016-08-07", "uncertain"], ["OPRN", "2016-08-08", "uncertain"],
    ["OPRN", "2016-08-09", "resolved"], ["OPRN", "2018-05-03", "resolved"],
    ["OPRN", "2021-03-24", "resolved"], ["OPRN", "2021-03-25", "uncertain"],
    ["OPRN", "2024-01-01", "uncertain"], ["OPRN", "2026-10-24", "uncertain"],
    ["OPIS", "2017-04-27", "uncertain"], ["OPIS", "2017-06-21", "uncertain"],
    ["OPIS", "2017-06-22", "uncertain"], ["OPIS", "2017-06-23", "resolved"],
    ["OPIS", "2018-05-03", "resolved"], ["OPIS", "2026-06-11", "resolved"],
    ["LTBA", "2011-10-14", "uncertain"], ["LTBA", "2011-10-15", "uncertain"],
    ["LTBA", "2011-10-16", "uncertain"], ["LTBA", "2011-10-17", "resolved"],
    ["LTBA", "2018-10-29", "resolved"], ["LTBA", "2019-04-06", "resolved"],
    ["LTBA", "2026-03-19", "resolved"],
    ["LTFM", "2018-09-11", "uncertain"], ["LTFM", "2018-10-10", "uncertain"],
    ["LTFM", "2018-10-11", "uncertain"], ["LTFM", "2018-10-12", "resolved"],
    ["LTFM", "2018-10-29", "resolved"], ["LTFM", "2019-04-06", "resolved"],
    ["LTFM", "2019-12-31", "resolved"], ["LTFM", "2026-03-19", "resolved"],
    ["EDDB", "2016-07-07", "uncertain"], ["EDDB", "2016-07-08", "uncertain"],
    ["EDDB", "2016-07-09", "resolved"], ["EDDB", "2020-10-24", "resolved"],
    ["EDDB", "2020-10-25", "resolved"], ["EDDB", "2020-10-31", "resolved"],
    ["EDDB", "2026-04-01", "resolved"],
    ["UACC", "2016-04-28", "uncertain"], ["UACC", "2016-04-29", "uncertain"],
    ["UACC", "2016-04-30", "uncertain"], ["UACC", "2016-05-01", "resolved"],
    ["UACC", "2018-05-22", "resolved"], ["UACC", "2020-06-07", "resolved"],
    ["UACC", "2020-06-08", "resolved"], ["UACC", "2020-06-09", "resolved"],
    ["UACC", "2026-10-01", "resolved"],
  ] as const)("%s on %s is %s at the existing permanent site", (code, date, status) => {
    expect(resolveAirport(previous, code, date, "ICAO").status).toBe("not_found");
    const result = resolveAirport(data, code, date, "ICAO");
    expect(result.status).toBe(status);
    expect(result.airport?.airportId ?? null).toBe(status === "resolved" ? sites[code] : null);
    expect(result.candidates.map((c) => c.airport.airportId)).toEqual([sites[code]]);
  });
  it.each(Object.keys(sites) as (keyof typeof sites)[])("keeps %s uncertainty and the evidence horizon", (code) => {
    const a = added.find((a) => a.code === code)!;
    expect(a.airportId).toBe(sites[code]);
    expect(a.scheme).toBe("ICAO");
    expect(a.validFrom.earliest).toBeNull();
    expect(a.validFrom.precision).toBe("unknown");
    expect(a.validTo.latest).toBeNull();
    expect(a.evidenceType).toBe("continuity_inference");
    expect(a.verificationStatus).toBe("verified");
    for (const id of a.sourceIds) expect(data.sources.find((s) => s.sourceId === id)?.verificationStatus).toBe("verified");
    for (const date of ["1900-01-01", "2026-10-25", "2030-01-01"]) {
      const result = resolveAirport(data, code, date, "ICAO");
      expect(result.status).toBe("uncertain");
      expect(result.airport).toBeNull();
    }
    expect(resolveAirport(data, code, "2026-10-24", "ICAO").status).toBe(code === "OPRN" ? "uncertain" : "resolved");
  });
  it("does not use GPS-only OPRN to extend the last AIP observation", () => {
    const a = added.find((a) => a.code === "OPRN")!;
    expect(a.validTo).toEqual({ earliest: "2021-03-25", latest: null, precision: "unknown" });
    expect(a.sourceIds).toEqual(["oprn-bea-2016", "oprn-aip-2021"]);
  });
  it("distinguishes administrative AIP designation from observed flights and future bookings", () => {
    // AIP designations identify sites before commissioning; no IATA history is added or rewritten.
    expect(data.assignments.filter((a) => a.scheme === "IATA")).toEqual(previous.assignments.filter((a) => a.scheme === "IATA"));
    for (const date of ["2025-07-22", "2025-07-23"])
      expect(resolveAirport(data, "KTI", date).status).toBe("uncertain");
  });
  it("keeps distinct replacement sites and retained same-site identifiers", () => {
    for (const date of ["2018-05-03", "2019-04-06", "2020-01-01"]) {
      for (const [oldCode, newCode] of [["OPRN", "OPIS"], ["LTBA", "LTFM"]] as const) {
        const old = resolveAirport(data, oldCode, date, "ICAO");
        const current = resolveAirport(data, newCode, date, "ICAO");
        expect(old.airport?.airportId).toBe(sites[oldCode]);
        if (current.status === "resolved") expect(current.airport?.airportId).toBe(sites[newCode]);
        expect(current.candidates.every((c) => c.airport.airportId !== sites[oldCode])).toBe(true);
      }
    }
    expect(added.filter((a) => a.code === "EDDB")).toHaveLength(1);
    expect(added.filter((a) => a.code === "UACC")).toHaveLength(1);
    expect(resolveAirport(data, "SXF", "2020-10-24").airport?.airportId).toBe(sites.EDDB);
    expect(resolveAirport(data, "BER", "2020-10-26").airport?.airportId).toBe(sites.EDDB);
    expect(resolveAirport(data, "TSE", "2020-06-07").airport?.airportId).toBe(sites.UACC);
    expect(resolveAirport(data, "NQZ", "2020-06-09").airport?.airportId).toBe(sites.UACC);
  });
  it("leaves unverified reused identifiers and recently deferred histories unadmitted", () => {
    for (const code of ["ZSQD", "KDEN", "LUKK", "ZSYT", "URRR", "URRP", "WALS"])
      for (const date of ["1995-02-27", "1995-02-28", "2021-08-11", "2021-08-12", "2024-01-01"])
        expect(resolveAirport(data, code, date, "ICAO").status).toBe("not_found");
  });
});

it("measures new daily queries against 0.6.0 without counting uncertain days as coverage", () => {
  let totalResolved = 0, totalUncertain = 0;
  expect(coverage.window).toEqual({ startInclusive: "2011-10-15", endExclusive: "2026-10-25" });
  expect(coverage.rows.map((r) => r.code).sort()).toEqual(Object.keys(sites).sort());
  for (const row of coverage.rows) {
    let resolved = 0, uncertain = 0, firstResolved: string | null = null, lastResolved: string | null = null;
    for (let date = coverage.window.startInclusive; date < coverage.window.endExclusive; date = nextDate(date)) {
      if (resolveAirport(previous, row.code, date, "ICAO").status !== "not_found") throw new Error("Already covered in 0.6.0");
      const result = resolveAirport(data, row.code, date, "ICAO");
      if (result.status === "resolved") {
        resolved++; firstResolved ??= date; lastResolved = date;
        if (result.airport?.airportId !== sites[row.code as keyof typeof sites]) throw new Error("Wrong physical identity");
      } else if (result.status === "uncertain") {
        uncertain++;
        if (result.airport !== null) throw new Error("Uncertain result exposed an airport");
      } else throw new Error(`Unexpected ${result.status}`);
    }
    expect({ resolved, uncertain, firstResolved, lastResolved }).toEqual({
      resolved: row.resolved, uncertain: row.uncertain, firstResolved: row.firstResolved, lastResolved: row.lastResolved,
    });
    totalResolved += resolved; totalUncertain += uncertain;
  }
  expect(totalResolved).toBe(coverage.totalResolved);
  expect(totalUncertain).toBe(coverage.totalUncertain);
  expect(totalResolved).toBe(21111);
  expect(totalUncertain).toBe(11823);
});
