import { describe, expect, it } from "vitest";
import { loadDataset } from "../scripts/load.ts";
import { resolveAirport, resolveAirportName } from "../src/index.ts";
import { validateDataset } from "../src/validate.ts";
import type { AirportName, Boundary, Dataset } from "../src/types.ts";

const data = await loadDataset();
const astanaId = "apt_99f19660-7609-49c5-b221-ed4a37046566";
const oldName = "Международный аэропорт Астана";
const newName = "Международный аэропорт Нурсултан Назарбаев";
const exact = (date: string): Boundary => ({
  earliest: date,
  latest: date,
  precision: "exact",
});

// Synthetic names exercise policies, without adding historical assertions.
function synthetic(): Dataset {
  const airportIds = new Set([astanaId, data.airports[0]!.airportId]);
  const d: Dataset = {
    ...data,
    airports: data.airports.filter((a) => airportIds.has(a.airportId)),
    assignments: data.assignments.filter((a) => airportIds.has(a.airportId)),
    names: [],
  };
  d.names = [
    {
      ...data.names[0]!,
      nameId: "synthetic-old",
      name: "Synthetic Old Name",
      language: "en",
      validFrom: exact("2000-01-01"),
      validTo: exact("2001-01-01"),
    },
    {
      ...data.names[1]!,
      nameId: "synthetic-new",
      name: "Synthetic New Name",
      language: "en",
      validFrom: exact("2001-01-01"),
      validTo: exact("2002-01-01"),
    },
  ];
  return d;
}

describe("Astana's formal name history", () => {
  it.each([
    ["2015-06-01", oldName],
    ["2017-06-20", oldName], // Signing is not first official publication.
    ["2017-06-22", newName],
    ["2019-03-24", newName], // City rename does not rename the airport.
    ["2020-06-08", newName], // IATA change does not rename the airport.
    ["2020-07-10", newName], // Corporate wording amendment is not another rename.
    ["2022-09-18", newName],
    ["2026-10-24", newName],
  ])("resolves %s to its reviewed Russian name", (date, name) => {
    const r = resolveAirportName(data, astanaId, date!);
    expect(r.status).toBe("resolved");
    expect(r.name).toBe(name);
    expect(r.language).toBe("ru");
    expect(r.historicallyVerified).toBe(true);
    expect(r.airport).toBe(data.airports.find((a) => a.airportId === astanaId));
  });

  it("preserves uncertainty on the effective day without inventing midnight", () => {
    const r = resolveAirportName(data, astanaId, "2017-06-21");
    expect(r.status).toBe("uncertain");
    expect(r.name).toBeNull();
    expect(r.historicallyVerified).toBe(false);
    expect(r.candidates.map((c) => [c.record.name, c.temporalMatch])).toEqual([
      [oldName, "possible"],
      [newName, "possible"],
    ]);
  });

  it.each(["2000-01-01", "2006-11-20", "2026-10-25", "2026-11-18"])(
    "does not extrapolate verified history to %s",
    (date) => {
      const r = resolveAirportName(data, astanaId, date);
      expect(r.status).toBe("uncertain");
      expect(r.name).toBeNull();
      expect(r.historicallyVerified).toBe(false);
    },
  );
  it("begins certain coverage after the earliest name observation, not at an invented naming date", () => {
    const r = resolveAirportName(data, astanaId, "2006-11-21");
    expect(r.status).toBe("resolved");
    expect(r.name).toBe(oldName);
    expect(r.candidates[0]!.record.validFrom.earliest).toBeNull();
  });

  it("keeps code resolution, static name, coordinates and identity independent", () => {
    const before = structuredClone(data);
    const tse = resolveAirport(data, "TSE", "2020-05-01");
    const nqz = resolveAirport(data, "NQZ", "2024-01-01");
    expect(tse.status).toBe("resolved");
    expect(nqz.status).toBe("resolved");
    expect(tse.airport).toBe(nqz.airport);
    for (const date of ["2015-01-01", "2018-01-01"])
      expect(resolveAirportName(data, astanaId, date).airport).toBe(
        nqz.airport,
      );
    expect(nqz.airport?.name).toEqual({
      ...before.airports.find((a) => a.airportId === astanaId)!.name,
      status: "reference",
    });
    const withoutNames = { ...data, names: [] };
    for (const [code, date] of [
      ["TSE", "2020-05-01"],
      ["NQZ", "2024-01-01"],
      ["TSE", "2020-06-08"],
    ])
      expect(resolveAirport(data, code!, date!)).toEqual(
        resolveAirport(withoutNames, code!, date!),
      );
    expect(data).toEqual(before);
  });
});

describe("name resolution policies", () => {
  it("applies the same public date range to official names", () => {
    const d = synthetic();
    d.names.pop();
    d.names[0]!.validFrom = exact("1999-12-31");
    d.names[0]!.validTo = exact("2026-11-20");
    for (const date of ["2000-01-01", "2026-11-18"])
      expect(resolveAirportName(d, astanaId, date).status).toBe("resolved");
    for (const date of ["1999-12-31", "2026-11-19"])
      expect(resolveAirportName(d, astanaId, date)).toMatchObject({
        status: "not_found",
        airport: null,
        name: null,
        historicallyVerified: false,
        candidates: [],
        reason:
          "Local date is outside the supported range [2000-01-01, 2026-11-19).",
      });
  });

  it("returns an explicitly unverified reference when a timeline is absent", () => {
    const d = structuredClone(data);
    const airport = d.airports[0]!;
    // Even a verified static fact says nothing about this historical date.
    airport.name.status = "verified";
    const r = resolveAirportName(d, airport.airportId, "2000-01-01");
    expect(r.status).toBe("reference");
    expect(r.name).toBe(airport.name.value);
    expect(r.historicallyVerified).toBe(false);
    expect(r.language).toBeNull();
    expect(r.candidates).toEqual([]);
  });

  it("handles exact half-open boundaries and gaps", () => {
    const d = synthetic();
    expect(validateDataset(d).errors).toEqual([]);
    expect(resolveAirportName(d, astanaId, "2000-12-31").name).toBe(
      "Synthetic Old Name",
    );
    expect(resolveAirportName(d, astanaId, "2001-01-01").name).toBe(
      "Synthetic New Name",
    );
    d.names[1]!.validFrom = exact("2001-02-01");
    expect(resolveAirportName(d, astanaId, "2001-01-15").status).toBe(
      "reference",
    );
    expect(resolveAirportName(d, astanaId, "2002-01-01").status).toBe(
      "reference",
    );
  });

  it.each(["day", "month", "year"] as const)(
    "preserves %s boundary uncertainty",
    (precision) => {
      const d = synthetic();
      const latest =
        precision === "day"
          ? "2001-01-02"
          : precision === "month"
            ? "2001-02-01"
            : "2002-01-01";
      const boundary: Boundary = { earliest: "2001-01-01", latest, precision };
      d.names[0]!.validTo = boundary;
      d.names[1]!.validFrom = boundary;
      d.names[1]!.validTo = exact("2003-01-01");
      expect(validateDataset(d).errors).toEqual([]);
      expect(resolveAirportName(d, astanaId, "2001-01-01").status).toBe(
        "uncertain",
      );
      expect(resolveAirportName(d, astanaId, latest).name).toBe(
        "Synthetic New Name",
      );
    },
  );

  it.each(["alias", "translation"] as const)(
    "never promotes a verified %s to an official name",
    (kind) => {
      const d = synthetic();
      const extra: AirportName = {
        ...d.names[0]!,
        nameId: "alternate",
        name: "Alternate Label",
        kind,
        language: "fr",
      };
      d.names.push(extra);
      expect(validateDataset(d).errors).toEqual([]);
      const r = resolveAirportName(d, astanaId, "2000-06-01");
      expect(r.status).toBe("resolved");
      expect(r.name).toBe("Synthetic Old Name");
      expect(r.candidates).toHaveLength(1);
      d.names = [extra];
      expect(resolveAirportName(d, astanaId, "2000-06-01").status).toBe(
        "reference",
      );
    },
  );

  it.each(["2023-02-29", "0000-01-01", "2024-01", "2024-01-01T00:00:00Z"])(
    "rejects invalid date %s",
    (date) => {
      const r = resolveAirportName(data, astanaId, date);
      expect(r.status).toBe("invalid_input");
      expect(r.name).toBeNull();
    },
  );
  it("distinguishes a missing airport from a missing timeline", () => {
    expect(resolveAirportName(data, "absent", "2024-01-01").status).toBe(
      "not_found",
    );
    expect(resolveAirportName(data, " ", "2024-01-01").status).toBe(
      "invalid_input",
    );
  });
  it("does not mutate inputs and returns the same result regardless of collection order", () => {
    const d = structuredClone(data);
    const before = structuredClone(d);
    const r = resolveAirportName(d, astanaId, "2017-06-21");
    expect(d).toEqual(before);
    d.names.reverse();
    d.airports.reverse();
    expect(resolveAirportName(d, astanaId, "2017-06-21")).toEqual(r);
  });
});

describe("official-name conflicts", () => {
  it.each(["certain", "possible"] as const)(
    "distinguishes %s name overlap",
    (overlap) => {
      const d = synthetic();
      d.names[1]!.validFrom =
        overlap === "certain"
          ? exact("2000-01-01")
          : { earliest: "2000-01-01", latest: "2001-01-01", precision: "year" };
      const validation = validateDataset(d);
      if (overlap === "certain")
        expect(validation.errors.join("\n")).toContain(
          "Conflicting official names",
        );
      else
        expect(validation.warnings.join("\n")).toContain(
          "Possible official-name boundary",
        );
      const result = resolveAirportName(d, astanaId, "2000-06-01");
      expect(result).toMatchObject({
        status: overlap === "certain" ? "conflict" : "uncertain",
        name: null,
        historicallyVerified: false,
      });
      expect(result.candidates).toHaveLength(2);
      d.names.reverse();
      expect(resolveAirportName(d, astanaId, "2000-06-01")).toEqual(result);
    },
  );

  it("does not confuse different physical airports or nonoverlapping intervals", () => {
    const d = synthetic();
    d.names[1]!.validFrom = exact("2000-01-01");
    d.names[1]!.airportId = d.airports[0]!.airportId;
    expect(validateDataset(d).errors).toEqual([]);
    expect(resolveAirportName(d, astanaId, "2000-06-01").name).toBe(
      "Synthetic Old Name",
    );
  });
  it("keeps a confirmed conflict when a third official name is only possible", () => {
    const d = synthetic();
    d.names[1]!.validFrom = exact("2000-01-01");
    d.names.unshift({
      ...d.names[0]!,
      nameId: "a-possible",
      name: "Possible Name",
      validFrom: { earliest: null, latest: null, precision: "unknown" },
    });
    expect(resolveAirportName(d, astanaId, "2000-06-01").status).toBe(
      "conflict",
    );
  });
});

describe("name schema and semantic validation", () => {
  it("requires schema 4 and an explicit names collection, without inventing history", () => {
    const { names: _names, ...legacy } = data;
    expect(validateDataset(legacy).errors.join("\n")).toContain("names");
    expect(
      validateDataset({ ...data, schemaVersion: "3.0.0" }).errors.length,
    ).toBeGreaterThan(0);
    expect(validateDataset({ ...data, names: [] }).errors).toEqual([]);
  });
  it.each([
    [
      "duplicate ID",
      (d: Dataset) => {
        d.names.push(d.names[0]!);
      },
      "Duplicate nameId",
    ],
    [
      "duplicate interval",
      (d: Dataset) => {
        d.names.push({ ...d.names[0]!, nameId: "duplicate" });
      },
      "Duplicate airport name interval",
    ],
    [
      "broken airport",
      (d: Dataset) => {
        d.names[0]!.airportId = "absent";
      },
      "missing airport",
    ],
    [
      "reversed boundary",
      (d: Dataset) => {
        d.names[0]!.validFrom = {
          earliest: "2002-01-01",
          latest: "2000-01-01",
          precision: "unknown",
        };
      },
      "reversed",
    ],
    [
      "empty interval",
      (d: Dataset) => {
        d.names[0]!.validFrom = d.names[0]!.validTo;
      },
      "impossible",
    ],
    [
      "false precision",
      (d: Dataset) => {
        d.names[0]!.validFrom.precision = "day";
      },
      "day precision",
    ],
    [
      "invalid language",
      (d: Dataset) => {
        d.names[0]!.language = "invalid-language-tag";
      },
      "language",
    ],
    [
      "uncanonical language",
      (d: Dataset) => {
        d.names[0]!.language = "EN";
      },
      "canonical",
    ],
  ] as const)("rejects %s", (_label, mutate, message) => {
    const d = synthetic();
    mutate(d);
    expect(validateDataset(d).errors.join("\n")).toContain(message);
  });
  it.each([{ name: " " }, { name: null }, { kind: "city" }, { language: "" }])(
    "rejects malformed name fields %j",
    (changes) => {
      const d = synthetic();
      Object.assign(d.names[0]!, changes);
      expect(validateDataset(d).errors.length).toBeGreaterThan(0);
    },
  );
});

it("keeps the Pranoto official name on the replacement site independent of code allocation", () => {
  const pranoto = "apt_80ab4c35-b89f-40af-a368-bc71b3716d5a";
  const temindung = "apt_967383b9-116c-4c3b-a8fb-c67515a3eb83";
  expect(resolveAirportName(data, pranoto, "2017-07-27").status).toBe(
    "uncertain",
  );
  expect(resolveAirportName(data, pranoto, "2017-07-28")).toMatchObject({
    status: "resolved",
    name: "Bandar Udara Aji Pangeran Tumenggung Pranoto",
    language: "id",
  });
  expect(resolveAirportName(data, pranoto, "2026-10-25").status).toBe(
    "uncertain",
  );
  expect(resolveAirportName(data, temindung, "2017-07-28").status).toBe(
    "reference",
  );
});
