import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { expect, test } from "vitest";
import { resolveAirport } from "../src/index.ts";
import type { Dataset } from "../src/types.ts";

const load = (path: string) => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8")) as Dataset;
const current = load("../data/airports.json");
const frozen = load("./curated-0.7.0.json");

test("reference import preserves every reviewed 0.7.0 record and historical result", () => {
  expect(createHash("sha256").update(readFileSync(new URL("./curated-0.7.0.json", import.meta.url))).digest("hex"))
    .toBe("31c5735b333881d7afdd527fe4af1db8e28413d5bba114fbf88a4aad0809cff7");
  for (const [collection, key] of [["airports", "airportId"], ["assignments", "assignmentId"],
    ["names", "nameId"], ["sources", "sourceId"]] as const) {
    const records = new Map((current[collection] as unknown as Record<string, unknown>[]).map(r => [r[key], r]));
    for (const record of frozen[collection] as unknown as Record<string, unknown>[]) expect(records.get(record[key])).toEqual(record);
  }
  const dates = ["1994-01-01", "1998-07-06", "2017-11-27", "2018-05-03", "2021-08-12", "2025-09-09", "2026-10-25", "2028-01-01"];
  for (const assignment of frozen.assignments)
    for (const date of dates)
      expect({ ...resolveAirport(current, assignment.code, date, assignment.scheme), dataVersion: frozen.dataVersion })
        .toEqual(resolveAirport(frozen, assignment.code, date, assignment.scheme));
  for (const code of ["JFK", "LAX", "SYD"])
    expect(resolveAirport(current, code, "2024-06-01").status).toBe("not_found");
});
