import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { describe, expect, it } from "vitest";
import { resolveAirport } from "../src/resolve.ts";
import { validateDataset } from "../src/validate.ts";
import type { Dataset } from "../src/types.ts";

const read = (path: string) => JSON.parse(readFileSync(path, "utf8"));
const before: Dataset = read("test/curated-0.11.0.json");
const after: Dataset = read("test/curated-0.12.0.json");
const additions = after.assignments.slice(before.assignments.length);

describe("AAI 0.12.0 bounded code admission", () => {
  it("appends three ICAO claims and preserves every published identity, code and source", () => {
    expect(validateDataset(after).errors).toEqual([]);
    expect(after).toEqual(read("research/admissions/0.12.0/proposed-data.json"));
    for (const key of ["airports", "assignments", "names", "sources"] as const)
      expect(after[key].slice(0, before[key].length)).toEqual(before[key]);
    expect(additions.map(a => a.code).sort()).toEqual(["VANM", "VEAY", "VOSH"]);
    expect(after.assignments.filter(a => a.scheme === "IATA"))
      .toEqual(before.assignments.filter(a => a.scheme === "IATA"));
    expect(after.names).toEqual(before.names);
    for (const a of after.airports.slice(before.airports.length)) {
      expect(a.name.status).toBe("reference");
      expect(a.coordinates.status).toBe("reference");
      expect(a.timezone.status).toBe("unknown");
      expect(a.timezone.value).toBeNull();
    }
  });

  for (const a of additions) it(`${a.code}: resolves only the 27 whole days between controlled editions`, () => {
    expect(a.validFrom).toEqual({ earliest: null, latest: "2026-06-12", precision: "unknown" });
    expect(a.validTo).toEqual({ earliest: "2026-07-09", latest: null, precision: "unknown" });
    expect(a.evidenceType).toBe("continuity_inference");
    expect(a.verificationStatus).toBe("verified");
    expect(a.sourceIds).toHaveLength(2);
    let gains = 0;
    for (let day = Date.parse("2026-06-10"); day <= Date.parse("2026-07-10"); day += 86400000) {
      const date = new Date(day).toISOString().slice(0, 10);
      const result = resolveAirport(after, a.code, date, "ICAO");
      const certain = date >= "2026-06-12" && date < "2026-07-09";
      expect(resolveAirport(before, a.code, date, "ICAO").status).toBe("not_found");
      expect(result.status).toBe(certain ? "resolved" : "uncertain");
      if (certain) { expect(result.airport?.airportId).toBe(a.airportId); gains++; }
    }
    expect(gains).toBe(27);
    const unreviewed = structuredClone(after);
    unreviewed.sources.find(s => s.sourceId === a.sourceIds[0])!.verificationStatus = "pending";
    expect(resolveAirport(unreviewed, a.code, "2026-06-20", "ICAO").status).toBe("uncertain");
    expect(validateDataset(unreviewed).errors.some(e => e.includes("unreviewed evidence"))).toBe(true);
  });

  it("uses the existing policy and original replay receipt without fabricating personal review", () => {
    const receipt = read("research/admissions/0.12.0/policy-receipt.json");
    const previous = read("research/admissions/0.10.0/policy-receipt.json");
    expect(receipt.reviewer).toBeNull();
    expect(receipt.authorizationSource).toBe(previous.authorizationSource);
    expect(receipt.policySha256).toBe(previous.policySha256);
    expect(receipt.executorSha256).toBe(previous.executorSha256);
    expect(receipt.baseline.dataVersion).toBe("0.11.0");
    const original = read("research/admissions/0.12.0/original-verification.json");
    expect(receipt.originalVerification).toEqual(original);
    expect(original.verificationMode).toBe("private_original_replay");
    expect(original.sources).toHaveLength(7);
    expect(new Set(original.sources.map((s: { originalSha256: string }) => s.originalSha256)).size).toBe(7);
    expect(read("research/policy/batch-authorizations.json").authorizations).toEqual([]);
  });

  it.each([
    ["target", "scripts/evidence/policy_gate.py", "Unexpected or missing data-only intake target"],
    ["sha256", "0".repeat(64), "Changed data-only intake file"],
  ])("rejects a substituted replay manifest %s before running the isolated gate", (field, value, expected) => {
    const result = execFileSync("python3", ["-c", `
import copy, sys
from pathlib import Path
sys.path.insert(0, 'scripts/evidence')
import global_code_admission as admission
original_load = admission.load
def changed_load(path):
    document = original_load(path)
    if Path(path).name == 'replay-manifest.json':
        document = copy.deepcopy(document)
        document['overlayFiles'][0][${JSON.stringify(field)}] = ${JSON.stringify(value)}
    return document
admission.load = changed_load
try:
    admission.check_inputs(Path('data/airports.json'))
except ValueError as error:
    assert ${JSON.stringify(expected)} in str(error), str(error)
    print('rejected')
else:
    raise AssertionError('Substituted replay manifest was accepted')
`], { encoding: "utf8" });
    expect(result.trim()).toBe("rejected");
  });
});
