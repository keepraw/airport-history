import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { resolveAirport } from "../src/resolve.ts";
import { validateDataset } from "../src/validate.ts";
import type { Dataset } from "../src/types.ts";

const read = (path: string) => JSON.parse(readFileSync(path, "utf8"));
const base: Dataset = read("test/curated-0.9.0.json");
const data: Dataset = read("test/curated-0.10.0.json");
const current: Dataset = read("data/airports.json");
const receipt = read("research/admissions/0.10.0/policy-receipt.json");
const grant = read("research/policy/authorizations.json").authorizations[0];
const additions = data.assignments.slice(base.assignments.length);

describe("first formal policy admission, 0.10.0", () => {
  it("preserves every published record and permanent ID, with no extra claim scope", () => {
    expect(data.dataVersion).toBe("0.10.0");
    expect(data.schemaVersion).toBe("3.0.0");
    expect(data).toEqual(read("research/admissions/0.10.0/proposed-data.json"));
    for (const collection of ["airports", "assignments", "sources", "names"] as const) {
      expect(data[collection].slice(0, base[collection].length)).toEqual(base[collection]);
      expect(current[collection].slice(0, data[collection].length)).toEqual(data[collection]);
    }
    expect(additions.map(a => [a.assignmentId, a.code, a.airportId])).toEqual([
      ["global-proposal-hollongi-icao-veho", "VEHO", "apt_9acf6a6b-6e22-48c6-881c-d602429a9268"],
      ["global-proposal-kannur-icao-vokn", "VOKN", "apt_58a2554f-6a9b-4ad7-bc2c-2550ad21b962"],
      ["global-proposal-shirdi-icao-vasd", "VASD", "apt_fa1bf7a7-a97d-4676-9c9a-7871eda47767"],
    ]);
    expect(data.names).toEqual(base.names);
    expect(data.assignments.filter(a => a.scheme === "IATA")).toEqual(base.assignments.filter(a => a.scheme === "IATA"));
    for (const airport of data.airports.slice(base.airports.length)) {
      expect(airport.name.status).toBe("reference");
      expect(airport.coordinates.status).toBe("reference");
      expect(airport.timezone.status).toBe("unknown");
      expect(airport.timezone.value).toBeNull();
    }
  });

  it("records policy execution and the existing registry grant without claiming personal owner review", () => {
    expect(receipt.reviewMode).toBe("policy");
    expect(receipt.reviewer).toBeNull();
    expect(receipt.authorizedBy).toEqual(grant.authorizedBy);
    expect(receipt.authorizationSource).toBe(grant.authorizationSource);
    expect(receipt.policyId).toBe("official-aip-bounded-icao");
    expect(receipt.policyVersion).toBe("1.0.0");
    expect(receipt.policySha256).toBe("3c606e60766f0ec89090e2b382939da67be00a7e9070aefc7568fe5559e05958");
    expect(grant.scopeSha256).toBe("6242a7bfaa66700aefc925bc8a3532f9ad62ca81334b156509835616419d1cb3");
    expect(receipt.executorSha256).toBe("2415279526ff8c0eaf9ee1b3ee5afca8bde26e95bfac2c98930212f9f7992a3f");
    const dossier = read("research/admissions/0.10.0/dossier.json");
    expect(dossier).toHaveLength(6);
    expect(new Set(dossier.map((d: { recordId: string }) => d.recordId))).toEqual(new Set([
      ...additions.map(a => a.assignmentId), ...additions.map(a => a.airportId),
    ]));
    for (const d of dossier) {
      expect(d.reviewMode).toBe("policy");
      expect(d.reviewer).toBeNull();
      expect(d.policyVersion).toBe(receipt.policyVersion);
    }
    const proof = read("research/admissions/0.10.0/original-verification.json");
    expect(proof).toEqual(receipt.originalVerification);
    expect(proof.sources).toHaveLength(6);
    expect(new Set(proof.sources.map((s: { originalSha256: string }) => s.originalSha256)).size).toBe(6);
    expect(read("research/policy/batch-authorizations.json").authorizations).toEqual([]);
  });

  for (const a of additions) it(`${a.code}: protects both observation days, adjacent dates and source requirements`, () => {
    expect(a.validFrom).toEqual({ earliest: null, latest: "2026-04-17", precision: "unknown" });
    expect(a.validTo).toEqual({ earliest: "2026-07-09", latest: null, precision: "unknown" });
    expect(a.evidenceType).toBe("continuity_inference");
    expect(a.verificationStatus).toBe("verified");
    for (const [day, status] of [["2026-04-15", "uncertain"], ["2026-04-16", "uncertain"],
      ["2026-04-17", "resolved"], ["2026-04-18", "resolved"], ["2026-07-07", "resolved"],
      ["2026-07-08", "resolved"], ["2026-07-09", "uncertain"], ["2026-07-10", "uncertain"]] as const) {
      expect(resolveAirport(base, a.code, day, "ICAO").status).toBe("not_found");
      const result = resolveAirport(data, a.code, day, "ICAO");
      expect(result.status).toBe(status);
      if (status === "resolved") expect(result.airport?.airportId).toBe(a.airportId);
    }
    const unreviewed = structuredClone(data);
    unreviewed.sources.find(s => s.sourceId === a.sourceIds[0])!.verificationStatus = "pending";
    expect(resolveAirport(unreviewed, a.code, "2026-05-01", "ICAO").status).toBe("uncertain");
    expect(validateDataset(unreviewed).errors.some(error => error.includes("unreviewed evidence"))).toBe(true);
  });

  it("binds the actual formal measurement to the admitted bytes and unchanged published answers", () => {
    const coverage = read("research/admissions/0.10.0/coverage.json");
    expect(coverage.mode).toBe("formal_policy_admission");
    expect(coverage.authorization).toBe(receipt.authorizationSource);
    const snapshotSha256 = createHash("sha256").update(readFileSync("test/curated-0.10.0.json")).digest("hex");
    expect(snapshotSha256).toBe("2268bdd3426e0d459b7b46d1214b165e3ab90f3526d4f2528f60238f4ee94b13");
    expect(coverage.candidateFileSha256).toBe(snapshotSha256);
    expect(coverage.beforeCounts).toEqual({ airports: 34, assignments: 49, sources: 95, names: 3 });
    expect(coverage.afterCounts).toEqual({ airports: 37, assignments: 52, sources: 101, names: 3 });
    expect(coverage.transitions["not_found->resolved"]).toBe(249);
    expect(coverage.transitions["not_found->uncertain"]).toBe(12849);
    expect(coverage.rows.map((r: { newResolved: number }) => r.newResolved)).toEqual([83, 83, 83]);
    for (const key of ["changedPublishedResolved", "changedExistingAnswers", "newConflicts", "removedConflicts"])
      expect(coverage[key]).toBe(0);
  });
});
