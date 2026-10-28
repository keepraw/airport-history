import { describe, expect, it } from "vitest";
import { loadDataset } from "../scripts/load.ts";
import { resolveAirport } from "../src/index.ts";
import { validateDataset } from "../src/validate.ts";
import ids from "./pr8-identities.json" with { type: "json" };
import frozen from "./curated-0.4.0.json" with { type: "json" };
import frozenPr8 from "./curated-0.5.0.json" with { type: "json" };

const data = await loadDataset();
type Key = keyof typeof ids;

describe("0.4.0 curated facts are preserved unchanged", () => {
  it.each([
    ["airports", "airportId"],
    ["assignments", "assignmentId"],
    ["names", "nameId"],
    ["sources", "sourceId"],
  ] as const)("every 0.4.0 %s record survives byte-for-byte", (key, idKey) => {
    const current = new Map(
      (data[key] as unknown as Record<string, unknown>[]).map((r) => [r[idKey], r]),
    );
    for (const record of frozen[key] as unknown as Record<string, unknown>[])
      expect(current.get(record[idKey])).toEqual(record);
  });
  it("freezes the reviewed 0.5.0 expansion counts and schema", () => {
    expect(frozen.dataVersion).toBe("0.4.0");
    expect(frozenPr8.dataVersion).toBe("0.5.0");
    expect(data.schemaVersion).toBe(frozen.schemaVersion);
    expect([frozenPr8.airports.length, frozenPr8.assignments.length, frozenPr8.names.length, frozenPr8.sources.length])
      .toEqual([19, 29, 2, 43]);
  });
});

describe("PR #8 permanent identities", () => {
  it.each(Object.keys(ids) as Key[])("%s keeps its permanent ID and reference attributes", (key) => {
    const expected = ids[key];
    const airport = data.airports.find((a) => a.airportId === expected.airportId)!;
    expect(airport.externalIds.ourAirports).toBe(expected.ourAirports);
    expect(airport.coordinates.value).toEqual(expected.coordinates);
    expect(airport.coordinates.status).toBe("reference");
    expect(airport.name.status).toBe("reference");
    expect(airport.timezone.value).toBe(expected.timezone);
  });
  it("old and new sites are distinct physical identities, not renames", () => {
    for (const [a, b] of [["rostov-on-don", "platov"], ["laishan", "penglai"], ["pochentong", "techo"]] as const)
      expect(ids[a].airportId).not.toBe(ids[b].airportId);
  });
  it("adds no official-name interval and no ICAO for Rostov or Yantai", () => {
    const newIds = new Set(Object.values(ids).map((i) => i.airportId));
    expect(data.names.filter((n) => newIds.has(n.airportId))).toEqual([]);
    for (const code of ["URRR", "URRP", "ZSYT", "VDKT"])
      expect(data.assignments.some((a) => a.code === code)).toBe(false);
  });
});

describe("PR #8 resolver behaviour around uncertain transitions", () => {
  it.each([
    // [code, date, scheme, status, expected airport key or null]
    ["ROV", "2016-06-01", "IATA", "resolved", "rostov-on-don"],
    ["ROV", "2017-11-26", "IATA", "resolved", "rostov-on-don"],
    ["ROV", "2017-11-27", "IATA", "uncertain", null],
    ["ROV", "2017-11-28", "IATA", "resolved", "platov"],
    ["ROV", "2017-12-07", "IATA", "resolved", "platov"],
    ["ROV", "2024-06-01", "IATA", "resolved", "platov"],
    ["ROV", "2015-01-01", "IATA", "uncertain", null],
    ["RVI", "2017-12-01", "IATA", "uncertain", null],
    ["RVI", "2019-01-01", "IATA", "uncertain", null],
    ["YNT", "2014-01-01", "IATA", "uncertain", null],
    ["YNT", "2014-12-11", "IATA", "uncertain", null],
    ["YNT", "2015-05-27", "IATA", "uncertain", null],
    ["YNT", "2015-05-28", "IATA", "resolved", "penglai"],
    ["YNT", "2020-01-01", "IATA", "resolved", "penglai"],
    ["PNH", "2015-01-01", "IATA", "resolved", "pochentong"],
    ["PNH", "2025-09-08", "IATA", "resolved", "pochentong"],
    ["PNH", "2025-09-09", "IATA", "uncertain", null],
    ["PNH", "2008-06-01", "IATA", "uncertain", null],
    ["KTI", "2025-09-10", "IATA", "resolved", "techo"],
    ["KTI", "2025-09-09", "IATA", "uncertain", null],
    ["KTI", "2025-09-08", "IATA", "uncertain", null],
    ["KTI", "2025-07-23", "IATA", "uncertain", null],
    ["KTI", "2025-07-22", "IATA", "uncertain", null],
    ["KTI", "2020-01-01", "IATA", "uncertain", null],
    ["VDTI", "2025-09-04", "ICAO", "resolved", "techo"],
    ["VDTI", "2025-09-03", "ICAO", "uncertain", null],
    ["VDPP", "2020-01-01", "ICAO", "resolved", "pochentong"],
    ["VDPP", "2025-09-07", "ICAO", "resolved", "pochentong"],
    ["VDPP", "2025-09-08", "ICAO", "uncertain", null],
    ["ZSYT", "2020-01-01", "ICAO", "not_found", null],
    ["URRR", "2016-01-01", "ICAO", "not_found", null],
  ] as const)("%s on %s (%s) is %s", (code, date, scheme, status, key) => {
    const r = resolveAirport(data, code, date, scheme);
    expect(r.status).toBe(status);
    if (key) {
      expect(r.airport?.airportId).toBe(ids[key].airportId);
      expect(r.candidates[0]!.assignment.evidenceType).toBe("continuity_inference");
    } else expect(r.airport).toBeNull();
  });
  it("transition days list both physical candidates as possible", () => {
    for (const [code, date, a, b] of [
      ["ROV", "2017-11-27", "rostov-on-don", "platov"],
      ["YNT", "2015-01-15", "laishan", "penglai"],
    ] as const) {
      const r = resolveAirport(data, code, date);
      expect(r.candidates.map((c) => c.airport.airportId).sort()).toEqual([ids[a].airportId, ids[b].airportId].sort());
      expect(r.candidates.every((c) => c.temporalMatch === "possible")).toBe(true);
    }
  });
  it("unknown withdrawals stay open-ended instead of inventing an end date", () => {
    for (const id of ["iata-rvi-rostov-on-don", "iata-pnh-pochentong", "icao-vdpp-pochentong"]) {
      const a = data.assignments.find((x) => x.assignmentId === id)!;
      expect(a.validTo.latest).toBeNull();
    }
    for (const id of ["iata-kti-techo", "icao-vdti-techo", "iata-rov-rostov-on-don", "iata-ynt-laishan", "iata-pnh-pochentong", "icao-vdpp-pochentong"]) {
      const a = data.assignments.find((x) => x.assignmentId === id)!;
      expect(a.validFrom.earliest).toBeNull();
    }
  });
  it("opening, planned and booking-availability dates are not code boundaries", () => {
    const platov = data.assignments.find((a) => a.assignmentId === "iata-rov-platov")!;
    expect(platov.validFrom).toEqual({ earliest: "2017-11-27", latest: "2017-11-28", precision: "day" });
    const kti = data.assignments.find((a) => a.assignmentId === "iata-kti-techo")!;
    expect(kti.validFrom).toEqual({ earliest: null, latest: "2025-09-10", precision: "unknown" });
    const penglai = data.assignments.find((a) => a.assignmentId === "iata-ynt-penglai")!;
    expect(penglai.validFrom).toEqual({ earliest: "2014-11-10", latest: "2015-05-28", precision: "unknown" });
  });
  it("only the expected possible-overlap warnings are added", () => {
    const warnings = validateDataset(data).warnings;
    expect(warnings).toContain("Possible boundary overlap: iata-rov-rostov-on-don / iata-rov-platov");
    expect(warnings).toContain("Possible boundary overlap: iata-ynt-laishan / iata-ynt-penglai");
    expect(validateDataset(data).errors).toEqual([]);
  });
});
