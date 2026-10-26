import { describe, expect, it } from "vitest";
import { loadDataset } from "../scripts/load.ts";
import { resolveAirport } from "../src/index.ts";
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
describe("curated historical regressions", () => {
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
    const r = resolveAirport(data, code, date);
    expect(r.status).toBe("resolved");
    expect(r.airport?.airportId).toBe(ids[key].airportId);
    expect(r.airport?.coordinates.value).not.toBeNull();
    expect(r.airport?.timezone.value).not.toBeNull();
    expect(r.evidence.length).toBeGreaterThan(1);
    expect(r.dataVersion).toBe("0.4.0");
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
      const r = resolveAirport(data, code, date);
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
      expect(resolveAirport(data, code, "1800-01-01").status).toBe("uncertain");
      expect(resolveAirport(data, code, "2030-01-01").status).toBe("uncertain");
    },
  );
});

describe("offline resolver contract", () => {
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
  it("does not use any fallback for missing codes", () =>
    expect(resolveAirport(data, "LHR", "2024-01-01").status).toBe("not_found"));
  it("rejects malformed codes and schemes", () => {
    expect(resolveAirport(data, "T4O", "2024-01-01").status).toBe(
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
      resolveAirport(data, "VHHH", "1997-01-01", "ICAO").airport?.airportId,
    ).toBe(ids["kai-tak"].airportId);
    expect(resolveAirport(data, "VHHH", "1998-07-06", "ICAO").status).toBe(
      "uncertain",
    );
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
  it.each(["pending", "disputed"] as const)(
    "%s evidence cannot resolve",
    (status) => {
      const d = synthetic();
      d.assignments[0]!.verificationStatus = status;
      expect(resolveAirport(d, "TAO", "2000-06-01").status).toBe("uncertain");
    },
  );
  it("pending sources cannot be laundered through a verified assignment", () => {
    const d = synthetic();
    d.sources.find(
      (s) => s.sourceId === d.assignments[0]!.sourceIds[0],
    )!.verificationStatus = "pending";
    expect(resolveAirport(d, "TAO", "2000-06-01").status).toBe("uncertain");
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
      sourceIds: [],
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
