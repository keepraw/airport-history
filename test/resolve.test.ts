import { describe, expect, it } from "vitest";
import { loadDataset } from "../scripts/load.ts";
import { resolveAirport } from "../src/index.ts";
import { resolveAirport as resolveRecordedAssignment } from "../src/resolve.ts";
import ids from "./identities.json" with { type: "json" };
import type { Boundary, CodeAssignment, Dataset } from "../src/types.ts";
const data = await loadDataset();
const exact = (date: string): Boundary => ({
  earliest: date,
  latest: date,
  precision: "exact",
});

// Synthetic assignments exercise the engine, never serve as historical evidence.
function synthetic(): Dataset {
  const copy = structuredClone(data);
  copy.assignments = [
    {
      ...copy.assignments[0]!,
      validFrom: exact("2000-01-01"),
      validTo: exact("2001-01-01"),
    },
  ];
  return copy;
}
describe("recorded assignments, including dates before the public query horizon", () => {
  it.each([
    ["TAO", "2017-01-01", "liuting"],
    ["TAO", "2024-12-31", "jiaodong"],
    ["IST", "2017-01-01", "ataturk"],
    ["IST", "2024-12-31", "istanbul"],
    ["HKG", "1997-01-01", "kai-tak"],
    ["HKG", "2024-12-31", "chek-lap-kok"],
    ["DEN", "1994-01-01", "stapleton"],
    ["DEN", "2024-12-31", "denver"],
  ] as const)("%s on %s resolves to %s", (code, date, key) => {
    const r = resolveRecordedAssignment(data, code, date);
    expect(r.status).toBe("resolved");
    expect(r.airport?.airportId).toBe(ids[key].airportId);
    expect(r.airport?.coordinates.value).not.toBeNull();
    expect(r.airport?.timezone.value).not.toBeNull();
    expect(r.dataVersion).toBe(data.dataVersion);
    expect(r.airport?.coordinates.status).toBe("reference");
  });
  it.each([
    ["TAO", "2021-08-11", "resolved", "liuting"],
    ["TAO", "2021-08-12", "resolved", "jiaodong"],
    ["TAO", "2021-08-13", "resolved", "jiaodong"],
    ["IST", "2019-04-05", "resolved", "ataturk"],
    ["IST", "2019-04-06", "uncertain", null],
    ["IST", "2019-04-07", "resolved", "istanbul"],
    ["HKG", "1998-07-05", "resolved", "kai-tak"],
    ["HKG", "1998-07-06", "uncertain", null],
    ["HKG", "1998-07-07", "resolved", "chek-lap-kok"],
    ["DEN", "1995-02-27", "resolved", "stapleton"],
    ["DEN", "1995-02-28", "uncertain", null],
    ["DEN", "1995-03-01", "resolved", "denver"],
  ] as const)(
    "%s on transfer-adjacent date %s: %s",
    (code, date, status, key) => {
      const r = resolveRecordedAssignment(data, code, date);
      expect(r.status).toBe(status);
      expect(r.airport?.airportId ?? null).toBe(
        key ? ids[key].airportId : null,
      );
      if (status === "uncertain") expect(r.candidates).toHaveLength(2);
    },
  );
  it("freezes physical identities, including closed sites", () => {
    for (const identity of Object.values(ids)) {
      expect(
        data.airports.find((a) => a.airportId === identity.airportId)
          ?.externalIds.ourAirports,
      ).toBe(identity.ourAirports);
    }
    expect(new Set(Object.values(ids).map((i) => i.airportId)).size).toBe(8);
  });
  it.each(["TAO", "IST", "HKG", "DEN"])(
    "%s does not extrapolate beyond evidence",
    (code) => {
      expect(resolveRecordedAssignment(data, code, "1800-01-01").status).toBe(
        "uncertain",
      );
      expect(resolveRecordedAssignment(data, code, "2030-01-01").status).toBe(
        "uncertain",
      );
    },
  );
});

describe("offline resolver contract", () => {
  it.each([
    ["IATA", "TAO"],
    ["ICAO", "TEST"],
  ] as const)("enforces the public date range for %s", (scheme, code) => {
    const d = synthetic();
    const assignment = d.assignments[0]!;
    Object.assign(assignment, {
      scheme,
      code,
      validFrom: exact("1999-12-31"),
      validTo: exact("2026-11-20"),
    });
    for (const date of ["1999-12-31", "2026-11-19"]) {
      expect(resolveRecordedAssignment(d, code, date, scheme).status).toBe(
        "resolved",
      );
      expect(resolveAirport(d, code, date, scheme)).toMatchObject({
        status: "not_found",
        query: { code, date, scheme },
        airport: null,
        candidates: [],
        reason:
          "Local date is outside the supported range [2000-01-01, 2026-11-19).",
      });
    }
    for (const date of ["2000-01-01", "2026-11-18"])
      expect(resolveAirport(d, code, date, scheme).status).toBe("resolved");
  });
  it("normalizes code whitespace/case and leaves caller data untouched", () => {
    const before = JSON.stringify(data);
    expect(resolveAirport(data, " tao ", "2017-06-01").airport?.airportId).toBe(
      ids.liuting.airportId,
    );
    expect(JSON.stringify(data)).toBe(before);
  });
  it.each([
    "2023-02-29",
    "2024-02-30",
    "2024-13-01",
    "2024-00-01",
    "2024-1-01",
    "2024",
    "0000-01-01",
    "2024-01-01T00:00:00Z",
  ])("rejects invalid/non-local date %s", (date) => {
    expect(resolveAirport(data, "TAO", date).status).toBe("invalid_input");
  });
  it("accepts Gregorian leap day", () =>
    expect(resolveAirport(data, "TAO", "2024-02-29").status).toBe("resolved"));
  it("resolves both Heathrow code namespaces from the cutoff", () => {
    const iata = resolveAirport(data, "LHR", "2000-01-01", "IATA");
    const icao = resolveAirport(data, "EGLL", "2000-01-01", "ICAO");
    expect(iata.status).toBe("resolved");
    expect(icao.status).toBe("resolved");
    expect(iata.airport?.externalIds.ourAirports).toBe("2434");
    expect(icao.airport?.airportId).toBe(iata.airport?.airportId);
  });
  it.each([
    ["BLR", "2008-05-24", "2008-05-23", "2008-05-25", "26603", "35145"],
    ["CAN", "2004-08-05", "2004-08-03", "2004-08-06", "35146", "27194"],
    ["ATH", "2001-03-29", "2001-03-27", "2001-03-30", "29673", "4251"],
  ])(
    "preserves distinct sites around the %s transfer on %s",
    (code, transition, before, after, formerSite, currentSite) => {
      const boundary = resolveAirport(data, code, transition);
      expect(boundary.status).toBe("uncertain");
      expect(boundary.airport).toBeNull();
      expect(boundary.candidates).toHaveLength(2);
      expect(
        resolveAirport(data, code, before).airport?.externalIds.ourAirports,
      ).toBe(formerSite);
      expect(
        resolveAirport(data, code, after).airport?.externalIds.ourAirports,
      ).toBe(currentSite);
    },
  );
  it("does not use any fallback for missing codes", () =>
    expect(resolveAirport(data, "NYC", "2024-01-01").status).toBe("not_found"));
  it("rejects malformed codes and schemes", () => {
    expect(resolveAirport(data, "T4O", "2024-01-01").status).toBe(
      "invalid_input",
    );
    expect(resolveAirport(data, "T4O", "1999-12-31").status).toBe(
      "invalid_input",
    );
    expect(
      resolveAirport(data, "TAO", "2024-01-01", "FAA" as "IATA").status,
    ).toBe("invalid_input");
  });
  it("implements half-open intervals and genuine gaps", () => {
    const d = synthetic();
    expect(resolveAirport(d, "TAO", "1999-12-31").status).toBe("not_found");
    expect(resolveAirport(d, "TAO", "2000-01-01").status).toBe("resolved");
    expect(resolveAirport(d, "TAO", "2000-12-31").status).toBe("resolved");
    expect(resolveAirport(d, "TAO", "2001-01-01").status).toBe("not_found");
  });
  it("separates ICAO and IATA namespaces", () => {
    const d = synthetic();
    d.assignments[0]!.scheme = "ICAO";
    d.assignments[0]!.code = "TEST";
    expect(resolveAirport(d, "TEST", "2000-06-01", "ICAO").status).toBe(
      "resolved",
    );
    expect(resolveAirport(d, "TAO", "2000-06-01").status).toBe("not_found");
    expect(
      resolveRecordedAssignment(data, "VHHH", "1997-01-01", "ICAO").airport
        ?.airportId,
    ).toBe(ids["kai-tak"].airportId);
    expect(
      resolveRecordedAssignment(data, "VHHH", "1998-07-06", "ICAO").status,
    ).toBe("uncertain");
    expect(
      resolveAirport(data, "VHHH", "2024-01-01", "ICAO").airport?.airportId,
    ).toBe(ids["chek-lap-kok"].airportId);
  });
  it("reports contradictions without choosing the first row", () => {
    const d = synthetic();
    const second: CodeAssignment = {
      ...d.assignments[0]!,
      assignmentId: "contradiction",
      airportId: ids.jiaodong.airportId,
    };
    d.assignments.push(second);
    const r = resolveAirport(d, "TAO", "2000-06-01");
    expect(r.status).toBe("conflict");
    expect(r.airport).toBeNull();
    expect(r.candidates).toHaveLength(2);
    d.assignments.reverse();
    expect(resolveAirport(d, "TAO", "2000-06-01")).toEqual(r);
  });
  it("an uncertain competitor prevents a unique answer", () => {
    const d = synthetic();
    d.assignments.push({
      ...d.assignments[0]!,
      assignmentId: "possible-competitor",
      airportId: ids.jiaodong.airportId,
      validFrom: { earliest: null, latest: null, precision: "unknown" },
    });
    expect(resolveAirport(d, "TAO", "2000-06-01").status).toBe("uncertain");
  });
  it("unknown metadata is not invented and renaming preserves identity", () => {
    const d = synthetic();
    d.airports[0]!.timezone = {
      value: null,
      status: "unknown",
      note: "Not established.",
    };
    d.airports[0]!.name.value = "Another display name";
    const r = resolveAirport(d, "TAO", "2000-06-01");
    expect(r.airport?.airportId).toBe(ids.liuting.airportId);
    expect(r.airport?.timezone.value).toBeNull();
  });
  it.each([
    ["month", "2000-05-01", "2000-06-01"],
    ["year", "2000-01-01", "2001-01-01"],
  ] as const)("preserves %s uncertainty", (precision, earliest, latest) => {
    const d = synthetic();
    d.assignments[0]!.validFrom = { earliest, latest, precision };
    d.assignments[0]!.validTo = exact("2002-01-01");
    expect(resolveAirport(d, "TAO", earliest).status).toBe("uncertain");
    expect(resolveAirport(d, "TAO", latest).status).toBe("resolved");
  });
});
