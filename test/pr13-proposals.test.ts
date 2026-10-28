import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { loadDataset } from "../scripts/load.ts";
import { resolveAirport } from "../src/resolve.ts";
import { dateNumber, interval, overlaps } from "../src/time.ts";
import { assertDataset, validateDataset } from "../src/validate.ts";
import type { Dataset } from "../src/types.ts";

const base = await loadDataset();
const proposal: Dataset = JSON.parse(readFileSync(new URL(
  "../research/evidence/direct/generated/proposed-data.json", import.meta.url), "utf8"));
const added = proposal.assignments.filter(a => !base.assignments.some(b => b.assignmentId === a.assignmentId));

describe("PR13 pending historical proposals", () => {
  it("passes the unchanged formal schema and preserves every frozen record", () => {
    assertDataset(proposal);
    for (const collection of ["airports", "assignments", "names", "sources"] as const)
      expect(proposal[collection].slice(0, base[collection].length)).toEqual(base[collection]);
    expect(base.dataVersion).toBe("0.7.0");
    expect(added).toHaveLength(6);
    expect(added.every(a => a.scheme === "ICAO" && a.verificationStatus === "pending" && a.verifiedOn === null)).toBe(true);
  });

  it("never resolves a pending proposal even inside its proposed certain interval", () => {
    for (const a of added) {
      const result = resolveAirport(proposal, a.code, a.validFrom.latest!, "ICAO");
      expect(result.airport).toBeNull();
      expect(result.status).toBe("uncertain");
    }
  });

  it("keeps St George's old/new sites and January/December service changes separate", () => {
    const old = added.find(a => a.assignmentId === "proposal-icao-sgu-old")!;
    const replacement = added.find(a => a.assignmentId === "proposal-icao-sgu-new")!;
    expect(old.airportId).not.toBe(replacement.airportId);
    expect(old.validTo.earliest).toBe("2011-01-12");
    expect(replacement.validFrom.latest).toBe("2011-12-16");
    expect(overlaps(interval(old).certain, interval(replacement).certain)).toBe(false);
    expect(replacement.validFrom.earliest).toBeNull();
    expect(added.some(a => a.code === "KDXZ")).toBe(false);
  });

  it("preserves half-open local-date boundaries without claiming exact withdrawals", () => {
    for (const a of added) {
      const span = interval(a);
      const start = dateNumber(a.validFrom.latest!), end = dateNumber(a.validTo.earliest!);
      expect(overlaps([start - 1, start], span.certain)).toBe(false);
      expect(overlaps([start, start + 1], span.certain)).toBe(true);
      expect(overlaps([end - 1, end], span.certain)).toBe(true);
      expect(overlaps([end, end + 1], span.certain)).toBe(false);
      expect(a.validTo.latest).toBeNull();
      expect(a.evidenceType).toBe("continuity_inference");
    }
  });

  it("still rejects confirmed overlapping site assignments in a synthetic review-state scenario", () => {
    // Test-only state, never saved as evidence or as a human acceptance record.
    const synthetic = structuredClone(proposal);
    for (const s of synthetic.sources) s.verificationStatus = "verified";
    for (const a of synthetic.assignments) {
      a.verificationStatus = "verified";
      a.verifiedOn = "2026-10-28";
    }
    const replacement = synthetic.assignments.find(a => a.assignmentId === "proposal-icao-sgu-new")!;
    replacement.validFrom.latest = "2010-01-01";
    expect(validateDataset(synthetic).errors.some(e => e.includes("Conflicting assignments"))).toBe(true);
  });

  it("exposes St George's remaining bounds gap even in a hypothetical reviewed state", () => {
    const hypothetical = structuredClone(proposal);
    for (const s of hypothetical.sources) s.verificationStatus = "verified";
    for (const a of hypothetical.assignments) {
      a.verificationStatus = "verified";
      a.verifiedOn = "2026-10-28";
    }
    // No acceptance is persisted. This measures the unresolved boundary problem.
    expect(resolveAirport(hypothetical, "KSGU", "2010-01-01", "ICAO").status).toBe("uncertain");
    expect(resolveAirport(hypothetical, "KSGU", "2013-01-01", "ICAO").status).toBe("uncertain");
    for (const [code, date] of [["KPFN", "2010-01-01"], ["KECP", "2013-01-01"],
      ["KISN", "2013-01-01"], ["KXWA", "2020-01-01"]])
      expect(resolveAirport(hypothetical, code!, date!, "ICAO").status).toBe("resolved");
  });

  it("preserves existing results at every old boundary and around newly investigated dates", () => {
    for (const a of base.assignments) {
      const dates = new Set(["2009-05-07", "2010-05-23", "2011-01-13", "2011-12-15", "2019-10-10", "2026-10-25"]);
      for (const b of [a.validFrom, a.validTo])
        for (const date of [b.earliest, b.latest]) if (date)
          for (const delta of [-1, 0, 1]) dates.add(new Date((dateNumber(date) + delta) * 86400000).toISOString().slice(0, 10));
      for (const date of dates) {
        const before = resolveAirport(base, a.code, date, a.scheme);
        const after = resolveAirport(proposal, a.code, date, a.scheme);
        expect({ ...after, dataVersion: base.dataVersion }).toEqual(before);
      }
    }
  });
});
