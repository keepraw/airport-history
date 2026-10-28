import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { describe, expect, it } from "vitest";
import { loadDataset } from "../scripts/load.ts";
import { resolveAirport, resolveAirportName } from "../src/index.ts";
import type { Dataset } from "../src/types.ts";
import { validateDataset } from "../src/validate.ts";
import baseline from "../research/discovery/curated-baseline.json" with { type: "json" };
import ids from "./pr9-identities.json" with { type: "json" };
import coverage from "./pr9-coverage.json" with { type: "json" };
import frozen04 from "./curated-0.4.0.json" with { type: "json" };
import frozen05 from "./curated-0.5.0.json" with { type: "json" };

const data = await loadDataset();
const previous = frozen05 as Dataset;
type Site = keyof typeof ids;
const nextDate = (date: string, delta = 1) => {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + delta);
  return d.toISOString().slice(0, 10);
};

describe("reviewed baselines survive the 0.6.0 expansion", () => {
  it.each([frozen04, frozen05])("preserves every record in $dataVersion", (frozen) => {
    for (const [key, idKey] of [["airports", "airportId"], ["assignments", "assignmentId"],
      ["names", "nameId"], ["sources", "sourceId"]] as const) {
      const current = new Map((data[key] as unknown as Record<string, unknown>[]).map((r) => [r[idKey], r]));
      for (const r of frozen[key] as unknown as Record<string, unknown>[])
        expect(current.get(r[idKey])).toEqual(r);
    }
  });
  it("pins both immutable snapshots and the current data bytes", async () => {
    expect(baseline.preservedBaselines.map((b) => b.dataVersion)).toEqual(["0.4.0", "0.5.0"]);
    for (const b of baseline.preservedBaselines) {
      const raw = await readFile(new URL(`../${b.record}`, import.meta.url));
      expect(createHash("sha256").update(raw).digest("hex")).toBe(b.sha256);
    }
    const raw = await readFile(new URL("../data/airports.json", import.meta.url));
    expect(createHash("sha256").update(raw).digest("hex")).toBe(baseline.sha256);
    expect(data.dataVersion).toBe("0.6.0");
    expect(data.schemaVersion).toBe("3.0.0");
    expect([data.airports.length, data.assignments.length, data.names.length, data.sources.length])
      .toEqual([23, 34, 3, 56]);
  });
  it("preserves previous resolver results at every old boundary and adjacent day", () => {
    const dates = new Set(["1900-01-01", "2017-06-01", "2024-06-01", "2026-10-24", "2026-10-25", "2030-01-01"]);
    for (const a of previous.assignments)
      for (const date of [a.validFrom.earliest, a.validFrom.latest, a.validTo.earliest, a.validTo.latest])
        if (date) for (const delta of [-1, 0, 1]) dates.add(nextDate(date, delta));
    for (const a of previous.assignments)
      for (const date of dates) {
        const old = resolveAirport(previous, a.code, date, a.scheme);
        expect({ ...resolveAirport(data, a.code, date, a.scheme), dataVersion: old.dataVersion }).toEqual(old);
      }
  });
});

describe("separate Dakar and Samarinda physical identities", () => {
  it.each(Object.keys(ids) as Site[])("keeps %s identity and reference attributes", (site) => {
    const expected = ids[site];
    const airport = data.airports.find((a) => a.airportId === expected.airportId)!;
    expect(airport.coordinates.value).toEqual(expected.coordinates);
    expect(airport.coordinates.status).toBe("reference");
    expect(airport.name.status).toBe("reference");
    expect(airport.timezone.value).toBe(expected.timezone);
    expect(airport.externalIds.ourAirports ?? null).toBe(expected.ourAirports);
  });
  it("does not merge replacement sites or reuse the repurposed external ID", () => {
    for (const [old, current] of [["yoff", "diass"], ["temindung", "pranoto"]] as const) {
      expect(ids[old].airportId).not.toBe(ids[current].airportId);
      expect(ids[old].coordinates).not.toEqual(ids[current].coordinates);
    }
    expect(data.airports.find((a) => a.airportId === ids.temindung.airportId)?.externalIds).toEqual({});
    expect(data.assignments.filter((a) => a.airportId === ids.temindung.airportId)).toEqual([]);
    expect(data.airports.find((a) => a.externalIds.ourAirports === "26763")?.airportId).toBe(ids.pranoto.airportId);
  });
});

describe("conservative code history", () => {
  it.each([
    ["DKR", "2013-03-29", "IATA", "uncertain", null],
    ["DKR", "2013-03-30", "IATA", "resolved", "yoff"],
    ["DKR", "2017-12-06", "IATA", "resolved", "yoff"],
    ["DKR", "2017-12-07", "IATA", "uncertain", null],
    ["DKR", "2024-01-01", "IATA", "uncertain", null],
    ["DSS", "2017-11-21", "IATA", "uncertain", null],
    ["DSS", "2017-11-22", "IATA", "resolved", "diass"],
    ["DSS", "2017-12-07", "IATA", "resolved", "diass"],
    ["GOOY", "2013-03-29", "ICAO", "uncertain", null],
    ["GOOY", "2013-03-30", "ICAO", "resolved", "yoff"],
    ["GOOY", "2017-12-07", "ICAO", "resolved", "yoff"],
    ["GOOY", "2024-01-01", "ICAO", "resolved", "yoff"],
    ["GOBD", "2017-10-12", "ICAO", "uncertain", null],
    ["GOBD", "2017-12-06", "ICAO", "uncertain", null],
    ["GOBD", "2017-12-07", "ICAO", "resolved", "diass"],
    ["AAP", "1997-01-01", "IATA", "uncertain", null],
    ["AAP", "2017-07-28", "IATA", "uncertain", null],
    ["AAP", "2018-05-24", "IATA", "uncertain", null],
    ["AAP", "2018-10-25", "IATA", "uncertain", null],
    ["AAP", "2018-11-19", "IATA", "uncertain", null],
    ["AAP", "2018-11-20", "IATA", "uncertain", null],
    ["AAP", "2019-08-20", "IATA", "uncertain", null],
    ["AAP", "2019-08-21", "IATA", "resolved", "pranoto"],
    ["AAP", "2026-10-24", "IATA", "resolved", "pranoto"],
    ["AAP", "2026-10-25", "IATA", "uncertain", null],
  ] as const)("%s %s (%s) is %s", (code, date, scheme, status, site) => {
    const result = resolveAirport(data, code, date, scheme);
    expect(result.status).toBe(status);
    expect(result.airport?.airportId ?? null).toBe(site ? ids[site].airportId : null);
  });
  it("keeps original allocations and disputed withdrawals open", () => {
    const added = data.assignments.filter((a) => !previous.assignments.some((p) => p.assignmentId === a.assignmentId));
    expect(added).toHaveLength(5);
    for (const a of added) {
      expect(a.validFrom.earliest).toBeNull();
      expect(a.validFrom.precision).toBe("unknown");
      expect(a.validTo.latest).toBeNull();
      expect(a.evidenceType).toBe("continuity_inference");
      expect(a.verificationStatus).toBe("verified");
      expect(a.sourceIds.length).toBeGreaterThan(1);
      for (const id of a.sourceIds) expect(data.sources.find((s) => s.sourceId === id)?.verificationStatus).toBe("verified");
      expect(resolveAirport(data, a.code, "2026-10-25", a.scheme).status).toBe("uncertain");
    }
    expect(data.assignments.find((a) => a.assignmentId === "iata-dkr-yoff")?.validTo)
      .toEqual({ earliest: "2017-12-07", latest: null, precision: "unknown" });
  });
  it("leaves blocked histories unadmitted and prior booking regression unchanged", () => {
    for (const code of ["SRI", "LYG", "JNG", "YBP", "LZO"])
      expect(resolveAirport(data, code, "2017-01-01").status).toBe("not_found");
    for (const code of ["WALS", "ZSLG", "ZSJG"])
      expect(resolveAirport(data, code, "2024-01-01", "ICAO").status).toBe("not_found");
    expect(resolveAirport(data, "KTI", "2025-07-22").status).toBe("uncertain");
    expect(resolveAirport(data, "KTI", "2025-07-23").status).toBe("uncertain");
    expect(validateDataset(data).warnings).toEqual(validateDataset(previous).warnings);
    expect(validateDataset(data).errors).toEqual([]);
  });
});

describe("Pranoto official name is independent of code allocation", () => {
  it.each([
    ["2017-07-26", "reference"], ["2017-07-27", "uncertain"],
    ["2017-07-28", "resolved"], ["2017-09-20", "resolved"],
    ["2018-01-27", "resolved"], ["2026-10-24", "resolved"], ["2026-10-25", "uncertain"],
  ] as const)("%s is %s", (date, status) => {
    const result = resolveAirportName(data, ids.pranoto.airportId, date);
    expect(result.status).toBe(status);
    if (status === "resolved") {
      expect(result.name).toBe("Bandar Udara Aji Pangeran Tumenggung Pranoto");
      expect(result.language).toBe("id");
      expect(result.historicallyVerified).toBe(true);
    }
  });
  it("does not attach the new site's legal name to Temindung", () => {
    expect(resolveAirportName(data, ids.temindung.airportId, "2024-01-01").status).toBe("reference");
    expect(resolveAirport(data, "AAP", "2017-07-28").status).toBe("uncertain");
  });
});

it("measures actual resolver statuses, with uncertainty separate from new certain coverage", () => {
  let totalResolved = 0, totalUncertain = 0;
  for (const expected of coverage.rows) {
    const scheme = expected.scheme as "IATA" | "ICAO";
    let resolved = 0, uncertain = 0, firstResolved: string | null = null, lastResolved: string | null = null;
    for (let date = coverage.window.startInclusive; date < coverage.window.endExclusive; date = nextDate(date)) {
      // All these distinct queries were absent from the reviewed baseline.
      if (resolveAirport(previous, expected.code, date, scheme).status !== "not_found") throw new Error("Previously covered query counted");
      const result = resolveAirport(data, expected.code, date, scheme);
      if (result.status === "resolved") {
        resolved++; firstResolved ??= date; lastResolved = date;
      } else if (result.status === "uncertain") uncertain++;
      else throw new Error(`Unexpected coverage status ${result.status}`);
    }
    expect({ resolved, uncertain, firstResolved, lastResolved }).toEqual({
      resolved: expected.resolved, uncertain: expected.uncertain,
      firstResolved: expected.firstResolved, lastResolved: expected.lastResolved,
    });
    totalResolved += resolved; totalUncertain += uncertain;
  }
  expect(totalResolved).toBe(15795);
  expect(totalUncertain).toBe(8995);
  expect(coverage.totalResolved).toBe(totalResolved);
  expect(coverage.totalUncertain).toBe(totalUncertain);
});
