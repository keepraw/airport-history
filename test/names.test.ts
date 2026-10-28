import { describe, expect, it } from "vitest";
import { loadDataset } from "../scripts/load.ts";
import { resolveAirport, resolveAirportName } from "../src/index.ts";
import { validateDataset } from "../src/validate.ts";
import type {
  AirportName,
  Boundary,
  Dataset,
  VerificationStatus,
} from "../src/types.ts";

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
  const d = structuredClone(data);
  d.names = [
    {
      ...d.names[0]!,
      nameId: "synthetic-old",
      name: "Synthetic Old Name",
      language: "en",
      validFrom: exact("2000-01-01"),
      validTo: exact("2001-01-01"),
    },
    {
      ...d.names[1]!,
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
    expect(r.candidates[0]!.record.evidenceType).toBe("continuity_inference");
    expect(r.evidence.map((s) => s.sourceId)).toContain(
      "astana-name-original-2017",
    );
    expect(r.evidence.map((s) => s.sourceId)).toContain(
      "astana-name-publication",
    );
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

  it.each(["1931-01-01", "2006-11-20", "2026-10-25", "2030-01-01"])(
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
  it("returns an explicitly unverified reference when a timeline is absent", () => {
    const d = structuredClone(data);
    const airport = d.airports[0]!;
    // Even a verified static fact says nothing about this historical date.
    airport.name.status = "verified";
    const r = resolveAirportName(d, airport.airportId, "1900-01-01");
    expect(r.status).toBe("reference");
    expect(r.name).toBe(airport.name.value);
    expect(r.historicallyVerified).toBe(false);
    expect(r.language).toBeNull();
    expect(r.candidates).toEqual([]);
    expect(r.evidence.map((s) => s.sourceId)).toEqual(airport.name.sourceIds);
    expect(r.reason).toContain("not historically verified");
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

  it.each(["pending", "disputed"] as const)(
    "retains a %s candidate without selecting a name",
    (status) => {
      const d = synthetic();
      d.names[0]!.verificationStatus = status;
      expect(validateDataset(d).errors).toEqual([]);
      const r = resolveAirportName(d, astanaId, "2000-06-01");
      expect(r.status).toBe("uncertain");
      expect(r.name).toBeNull();
      expect(r.historicallyVerified).toBe(false);
      expect(r.candidates[0]!.record.verificationStatus).toBe(status);
      expect(resolveAirportName(d, astanaId, "2001-06-01").status).toBe(
        "resolved",
      );
    },
  );

  it.each([
    "pending",
    "disputed",
    "missing",
    "empty",
    "undated",
    "predates",
    "false-primary",
  ])("does not resolve a verified label with %s evidence", (problem) => {
    const d = synthetic();
    const n = d.names[0]!;
    n.sourceIds = ["ourairports-20261025"];
    if (problem === "pending" || problem === "disputed")
      d.sources.find((s) => s.sourceId === n.sourceIds[0])!.verificationStatus =
        problem;
    if (problem === "missing") n.sourceIds = ["absent"];
    if (problem === "empty") n.sourceIds = [];
    if (problem === "undated") n.verifiedOn = null;
    if (problem === "predates") n.verifiedOn = "2020-01-01";
    if (problem === "false-primary") n.evidenceType = "primary_direct";
    expect(validateDataset(d).errors.length).toBeGreaterThan(0);
    expect(resolveAirportName(d, astanaId, "2000-06-01").status).toBe(
      "uncertain",
    );
  });

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
    d.sources.reverse();
    d.airports.reverse();
    expect(resolveAirportName(d, astanaId, "2017-06-21")).toEqual(r);
  });
});

describe("official-name conflicts", () => {
  const statuses: VerificationStatus[] = ["verified", "pending", "disputed"];
  it.each(
    statuses.flatMap((left) =>
      statuses.flatMap((right) =>
        (["certain", "possible"] as const).map((overlap) => ({
          left,
          right,
          overlap,
        })),
      ),
    ),
  )("$left / $right with $overlap overlap", ({ left, right, overlap }) => {
    const d = synthetic();
    d.names[0]!.verificationStatus = left;
    d.names[1]!.verificationStatus = right;
    d.names[1]!.validFrom =
      overlap === "certain"
        ? exact("2000-01-01")
        : {
            earliest: "2000-01-01",
            latest: "2001-01-01",
            precision: "year",
          };
    const confirmed =
      left === "verified" && right === "verified" && overlap === "certain";
    const v = validateDataset(d);
    expect(v.errors.length).toBe(confirmed ? 1 : 0);
    expect(v.warnings.length).toBe(confirmed ? 8 : 9);
    if (confirmed) expect(v.errors[0]).toContain("Conflicting official names");
    else
      expect(v.warnings.at(-1)).toContain(
        left === "verified" && right === "verified"
          ? "Possible official-name boundary"
          : "Unconfirmed official-name",
      );
    const r = resolveAirportName(d, astanaId, "2000-06-01");
    expect(r.status).toBe(confirmed ? "conflict" : "uncertain");
    expect(r.name).toBeNull();
    expect(r.historicallyVerified).toBe(false);
    expect(r.candidates).toHaveLength(2);
    d.names.reverse();
    expect(resolveAirportName(d, astanaId, "2000-06-01")).toEqual(r);
  });

  it("does not confuse different physical airports or nonoverlapping intervals", () => {
    const d = synthetic();
    d.names[1]!.validFrom = exact("2000-01-01");
    d.names[1]!.airportId = d.airports[0]!.airportId;
    expect(validateDataset(d).errors).toEqual([]);
    expect(resolveAirportName(d, astanaId, "2000-06-01").name).toBe(
      "Synthetic Old Name",
    );
  });
  it("keeps a confirmed conflict ahead of an unreviewed third claim", () => {
    const d = synthetic();
    d.names[1]!.validFrom = exact("2000-01-01");
    d.names.unshift({
      ...d.names[0]!,
      nameId: "a-pending",
      name: "Pending",
      verificationStatus: "pending",
    });
    expect(resolveAirportName(d, astanaId, "2000-06-01").status).toBe(
      "conflict",
    );
  });
});

describe("name schema and semantic validation", () => {
  it("requires schema 3 and an explicit names collection, without inventing history", () => {
    const { names: _names, ...legacy } = data;
    expect(validateDataset(legacy).errors.join("\n")).toContain("names");
    expect(
      validateDataset({ ...data, schemaVersion: "2.0.0" }).errors.length,
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
      "broken source",
      (d: Dataset) => {
        d.names[0]!.sourceIds = ["absent"];
      },
      "missing source",
    ],
    [
      "missing review",
      (d: Dataset) => {
        d.names[0]!.verifiedOn = null;
      },
      "verifiedOn",
    ],
    [
      "early review",
      (d: Dataset) => {
        d.names[0]!.verifiedOn = "2000-01-01";
      },
      "predates",
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
  it.each([
    { name: " " },
    { name: null },
    { kind: "city" },
    { language: "" },
    { sourceIds: [] },
    { evidenceType: "official" },
    { verificationStatus: "reference" },
  ])("rejects malformed name fields %j", (changes) => {
    const d = synthetic();
    Object.assign(d.names[0]!, changes);
    expect(validateDataset(d).errors.length).toBeGreaterThan(0);
  });
});
