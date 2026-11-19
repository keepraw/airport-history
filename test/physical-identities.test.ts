import { describe, expect, it } from "vitest";
import { loadDataset } from "../scripts/load.ts";
import { queryHorizon, resolveAirport } from "../src/index.ts";
import { resolveAirport as resolveRecordedAssignment } from "../src/resolve.ts";
import initialIds from "./identities.json" with { type: "json" };
import batchIds from "./batch-1-identities.json" with { type: "json" };

const data = await loadDataset();
const identities = {
  ...batchIds,
  istanbul: {
    ...initialIds.istanbul,
    coordinates: { latitude: 41.274874, longitude: 28.732136 },
    timezone: "Europe/Istanbul",
  },
  ataturk: {
    ...initialIds.ataturk,
    coordinates: { latitude: 40.971913, longitude: 28.823714 },
    timezone: "Europe/Istanbul",
  },
};

describe("physical identity and reference coordinates", () => {
  it.each([
    ["ISL", "2018-12-01", "istanbul"],
    ["ISL", "2024-06-01", "ataturk"],
    ["ISB", "2017-06-01", "benazir-bhutto"],
    ["ISB", "2019-06-01", "islamabad"],
    ["SXF", "2020-06-01", "schonefeld-brandenburg"],
    ["BER", "2024-06-01", "schonefeld-brandenburg"],
    ["TSE", "2020-05-01", "astana"],
    ["NQZ", "2024-06-01", "astana"],
    ["KIV", "2024-01-01", "chisinau"],
    ["RMO", "2024-06-01", "chisinau"],
  ] as const)("%s on %s identifies %s", (code, date, key) => {
    const expected = identities[key];
    const result = resolveAirport(data, code, date);
    expect(result.status).toBe("resolved");
    expect(result.airport?.airportId).toBe(expected.airportId);
    expect(result.airport?.externalIds.ourAirports).toBe(expected.ourAirports);
    expect(result.airport?.coordinates.value).toEqual(expected.coordinates);
    expect(result.airport?.coordinates.status).toBe("reference");
    expect(result.airport?.timezone.value).toBe(expected.timezone);
  });

  it("preserves all thirteen permanent identities", () => {
    const allIds = [...Object.values(initialIds), ...Object.values(batchIds)];
    expect(new Set(allIds.map((i) => i.airportId)).size).toBe(13);
    for (const identity of allIds) {
      expect(
        data.airports.find((a) => a.airportId === identity.airportId)
          ?.externalIds.ourAirports,
      ).toBe(identity.ourAirports);
    }
  });

  it.each([
    ["SXF", "BER", "schonefeld-brandenburg"],
    ["TSE", "NQZ", "astana"],
    ["KIV", "RMO", "chisinau"],
  ] as const)(
    "%s to %s preserves the %s physical identity",
    (oldCode, newCode, key) => {
      const pair = data.assignments.filter(
        (a) => a.code === oldCode || a.code === newCode,
      );
      expect(pair).toHaveLength(2);
      expect(pair.map((a) => a.airportId)).toEqual([
        batchIds[key].airportId,
        batchIds[key].airportId,
      ]);
    },
  );
});

describe("transfers and conservative boundary behavior", () => {
  it("models the ISL exchange in the opposite direction to IST", () => {
    expect(resolveAirport(data, "ISL", "2019-04-05").airport?.airportId).toBe(
      initialIds.istanbul.airportId,
    );
    expect(resolveAirport(data, "IST", "2019-04-05").airport?.airportId).toBe(
      initialIds.ataturk.airportId,
    );
    for (const code of ["ISL", "IST"]) {
      const onDay = resolveAirport(data, code, "2019-04-06");
      expect(onDay.status).toBe("uncertain");
      expect(onDay.airport).toBeNull();
      expect(new Set(onDay.candidates.map((c) => c.airport.airportId))).toEqual(
        new Set([initialIds.istanbul.airportId, initialIds.ataturk.airportId]),
      );
    }
    expect(resolveAirport(data, "ISL", "2019-04-07").airport?.airportId).toBe(
      initialIds.ataturk.airportId,
    );
    expect(resolveAirport(data, "IST", "2019-04-07").airport?.airportId).toBe(
      initialIds.istanbul.airportId,
    );
  });

  it.each(["2018-05-01", "2018-05-02", "2018-05-03", "2018-05-31"])(
    "ISB on %s retains month uncertainty, including flight relocation day",
    (date) => {
      const result = resolveAirport(data, "ISB", date);
      expect(result.status).toBe("uncertain");
      expect(result.airport).toBeNull();
      expect(
        new Set(result.candidates.map((c) => c.airport.airportId)),
      ).toEqual(
        new Set([
          batchIds["benazir-bhutto"].airportId,
          batchIds.islamabad.airportId,
        ]),
      );
      for (const candidate of result.candidates)
        expect(candidate.temporalMatch).toBe("possible");
    },
  );

  it("ISB resolves outside the uncertain month and retains the old field", () => {
    expect(resolveAirport(data, "ISB", "2018-04-30").airport?.airportId).toBe(
      batchIds["benazir-bhutto"].airportId,
    );
    expect(resolveAirport(data, "ISB", "2018-06-01").airport?.airportId).toBe(
      batchIds.islamabad.airportId,
    );
    const oldField = data.airports.find(
      (a) => a.airportId === batchIds["benazir-bhutto"].airportId,
    )!;
    expect(oldField.coordinates.value).toEqual(
      batchIds["benazir-bhutto"].coordinates,
    );
    expect(
      resolveAirport(data, "OPRN", "2017-06-01", "ICAO").airport?.airportId,
    ).toBe(batchIds["benazir-bhutto"].airportId);
    expect(
      resolveAirport(data, "OPIS", "2019-06-01", "ICAO").airport?.airportId,
    ).toBe(batchIds.islamabad.airportId);
  });

  it.each([
    ["SXF", "BER", "2020-10-24", "2020-10-25", "2020-10-26"],
    ["TSE", "NQZ", "2020-06-07", "2020-06-08", "2020-06-09"],
    ["KIV", "RMO", "2024-01-17", "2024-01-18", "2024-01-19"],
  ] as const)(
    "%s to %s checks retirement, new assignment and change-day uncertainty",
    (oldCode, newCode, before, boundary, after) => {
      const oldResult = resolveAirport(data, oldCode, before);
      const newResult = resolveAirport(data, newCode, after);
      expect(oldResult.status).toBe("resolved");
      expect(newResult.status).toBe("resolved");
      expect(oldResult.airport?.airportId).toBe(newResult.airport?.airportId);
      for (const code of [oldCode, newCode]) {
        const result = resolveAirport(data, code, boundary);
        expect(result.status).toBe("uncertain");
        expect(result.airport).toBeNull();
        expect(result.candidates).toHaveLength(1);
      }
      expect(resolveAirport(data, oldCode, after).status).toBe("not_found");
      expect(resolveAirport(data, newCode, before).status).toBe("not_found");
    },
  );

  it("does not resolve the old BER city code as an airport or wait for T1 opening", () => {
    expect(resolveAirport(data, "BER", "2019-06-01").status).toBe("not_found");
    expect(resolveAirport(data, "BER", "2020-10-26").airport?.airportId).toBe(
      batchIds["schonefeld-brandenburg"].airportId,
    );
  });

  it.each(["ISL", "ISB", "SXF", "TSE", "KIV"])(
    "%s retains unknown first allocation instead of using an opening/rename date",
    (code) => {
      const assignment = data.assignments.find((a) => a.code === code)!;
      expect(assignment.validFrom.precision).toBe("unknown");
      expect(assignment.validFrom.earliest).toBeNull();
      expect(resolveRecordedAssignment(data, code, "1999-12-31").status).toBe(
        "uncertain",
      );
    },
  );

  it.each(["ISL", "ISB", "BER", "NQZ", "RMO"])(
    "%s stops certain coverage at the fixed snapshot horizon",
    (code) => {
      expect(resolveAirport(data, code, "2026-11-18").status).toBe("resolved");
      const end = queryHorizon.toExclusive;
      expect(resolveAirport(data, code, end).status).toBe("not_found");
      expect(resolveRecordedAssignment(data, code, end).status).toBe(
        "uncertain",
      );
    },
  );
});

it.each([
  [
    "YNT",
    "2014-11-10",
    "2015-05-28",
    "apt_7923bd7d-2855-4d5f-b979-63a5380cd3da",
    "apt_0f0ebbe2-ce55-4b70-8d22-c760fe94777e",
  ],
  [
    "LYG",
    "2021-09-22",
    "2023-06-01",
    "apt_6f1a6ff3-98db-4e58-95fc-cc78bd5aa836",
    "apt_64b5eaa6-a984-4816-86d9-d8eb71c91451",
  ],
  [
    "LZO",
    "2017-07-16",
    "2023-06-01",
    "apt_56b57bca-08d5-4b5e-944e-1e9cce968a0a",
    "apt_f11bdf7d-d81d-46fc-a94f-8c8c42d4e245",
  ],
  [
    "YBP",
    "2019-11-21",
    "2023-06-01",
    "apt_bbf9f2c1-fc01-4ed7-a4aa-74e6ed8ca45f",
    "apt_8354da99-7d18-4329-bf7b-4ed042a4ad72",
  ],
] as const)(
  "%s preserves both sites across its uncertain transfer window",
  (code, earliest, latest, formerId, replacementId) => {
    const before = new Date(Date.parse(earliest) - 86_400_000)
      .toISOString()
      .slice(0, 10);
    expect(resolveAirport(data, code, before).airport?.airportId).toBe(
      formerId,
    );
    const transfer = resolveAirport(data, code, earliest);
    expect(transfer).toMatchObject({ status: "uncertain", airport: null });
    expect(
      new Set(transfer.candidates.map((row) => row.airport.airportId)),
    ).toEqual(new Set([formerId, replacementId]));
    expect(
      transfer.candidates.every((row) => row.temporalMatch === "possible"),
    ).toBe(true);
    expect(resolveAirport(data, code, latest).airport?.airportId).toBe(
      replacementId,
    );
  },
);

it("keeps OPRN on the former site within its separate ICAO coverage", () => {
  const former = batchIds["benazir-bhutto"].airportId;
  expect(
    resolveAirport(data, "OPRN", "2021-03-24", "ICAO").airport?.airportId,
  ).toBe(former);
  expect(resolveAirport(data, "OPRN", "2021-03-25", "ICAO").status).toBe(
    "uncertain",
  );
  expect(
    resolveAirport(data, "OPIS", "2021-03-25", "ICAO").airport?.airportId,
  ).toBe(batchIds.islamabad.airportId);
});
