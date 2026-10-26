import { describe, expect, it } from "vitest";
import { loadDataset } from "../scripts/load.ts";
import { resolveAirport } from "../src/index.ts";
import { validateDataset } from "../src/validate.ts";
import type { Boundary, Dataset, VerificationStatus } from "../src/types.ts";

const data = await loadDataset();
const exact = (date: string): Boundary => ({
  earliest: date,
  latest: date,
  precision: "exact",
});
// Synthetic claims reuse existing physical identities, not historical assertions.
function competing(
  left: VerificationStatus,
  right: VerificationStatus,
  overlap: "certain" | "possible" = "certain",
): Dataset {
  const d = structuredClone(data);
  d.assignments = [left, right].map((status, i) => ({
    ...d.assignments[i]!,
    assignmentId: `claim-${i}`,
    verificationStatus: status,
    verifiedOn: status === "verified" ? "2026-10-26" : null,
    validFrom:
      i === 1 && overlap === "possible"
        ? { earliest: "2000-01-01", latest: "2001-01-01", precision: "year" }
        : exact("2000-01-01"),
    validTo: exact(
      i === 1 && overlap === "possible" ? "2001-01-01" : "2002-01-01",
    ),
  }));
  return d;
}

describe("review status and temporal overlap are independent", () => {
  const statuses = ["verified", "pending", "disputed"] as const;
  const cases = statuses.flatMap((left) =>
    statuses.flatMap((right) =>
      (["certain", "possible"] as const).map((overlap) => ({
        left, right, overlap,
      })),
    ),
  );
  it.each(cases)("$left / $right with $overlap overlap", ({
    left, right, overlap,
  }) => {
    const d = competing(left, right, overlap);
    const confirmed =
      left === "verified" && right === "verified" && overlap === "certain";
    const validation = validateDataset(d);
    expect(validation.errors).toEqual(
      confirmed
        ? ["Conflicting assignments (confirmed conflict): claim-0 / claim-1"]
        : [],
    );
    expect(validation.warnings).toHaveLength(confirmed ? 0 : 1);
    if (!confirmed) {
      expect(validation.warnings[0]).toContain(
        left === "verified" && right === "verified"
          ? "Possible boundary overlap"
          : "Unconfirmed assignment overlap (review required)",
      );
    }
    const result = resolveAirport(d, "TAO", "2000-06-01");
    expect(result.status).toBe(confirmed ? "conflict" : "uncertain");
    expect(result.airport).toBeNull();
    expect(result.candidates).toHaveLength(2);
    expect(result.candidates[1]!.temporalMatch).toBe(overlap);
    expect(result.candidates.map((c) => c.assignment.verificationStatus)).toEqual([
      left, right,
    ]);
    d.assignments.reverse();
    expect(resolveAirport(d, "TAO", "2000-06-01")).toEqual(result);
  });

  it.each(["primary_direct", "indirect", "continuity_inference"] as const)(
    "reviewed %s evidence can establish a conflict without ranking candidates",
    (evidenceType) => {
      const d = competing("verified", "verified");
      for (const a of d.assignments) a.evidenceType = evidenceType;
      expect(validateDataset(d).errors.join("\n")).toContain("confirmed conflict");
      expect(resolveAirport(d, "TAO", "2000-06-01").status).toBe("conflict");
    },
  );

  it("reports conflicts only on query dates within the confirmed overlap", () => {
    const d = competing("verified", "verified", "possible");
    d.assignments[1]!.validTo = exact("2002-01-01");
    expect(validateDataset(d).errors.join("\n")).toContain("confirmed conflict");
    expect(resolveAirport(d, "TAO", "2000-06-01").status).toBe("uncertain");
    expect(resolveAirport(d, "TAO", "2001-06-01").status).toBe("conflict");
  });

  it.each(["pending", "disputed"] as const)(
    "a confirmed conflict takes precedence over a %s third candidate",
    (status) => {
      for (const overlap of ["certain", "possible"] as const) {
        const d = competing("verified", "verified");
        const third = competing("verified", status, overlap).assignments[1]!;
        d.assignments.unshift({
          ...third,
          assignmentId: "a-review-first",
          airportId: d.airports[2]!.airportId,
        });
        const result = resolveAirport(d, "TAO", "2000-06-01");
        expect(result.status).toBe("conflict");
        expect(result.airport).toBeNull();
        expect(result.candidates).toHaveLength(3);
        const validation = validateDataset(d);
        expect(validation.errors).toHaveLength(1);
        expect(validation.errors[0]).toContain("confirmed conflict");
        expect(validation.warnings).toHaveLength(2);
      }
    },
  );

  it.each(["pending", "disputed", "missing", "empty", "undated", "predates"] as const)(
    "%s evidence behind a verified label cannot confirm a conflict",
    (problem) => {
      const d = competing("verified", "verified");
      // Keep the first claim's evidence independent of the damaged second claim.
      const a = d.assignments[1]!;
      a.sourceIds = ["ourairports-20261025"];
      if (problem === "pending" || problem === "disputed")
        d.sources.find((s) => s.sourceId === a.sourceIds[0])!.verificationStatus =
          problem;
      if (problem === "missing") a.sourceIds = ["absent"];
      if (problem === "empty") a.sourceIds = [];
      if (problem === "undated") a.verifiedOn = null;
      if (problem === "predates") a.verifiedOn = "2020-01-01";
      const result = resolveAirport(d, "TAO", "2000-06-01");
      expect(result.status).toBe("uncertain");
      expect(result.candidates).toHaveLength(2);
      expect(result.airport).toBeNull();
      const errors = validateDataset(d).errors;
      expect(errors.length).toBeGreaterThan(0);
      expect(errors.join("\n")).not.toContain("confirmed conflict");
    },
  );

  it("accepts nonoverlapping reuse at an exact half-open boundary", () => {
    const d = competing("verified", "verified");
    d.assignments[0]!.validTo = exact("2001-01-01");
    d.assignments[1]!.validFrom = exact("2001-01-01");
    expect(validateDataset(d)).toEqual({ errors: [], warnings: [] });
    expect(resolveAirport(d, "TAO", "2000-12-31").airport?.airportId).toBe(
      d.airports[0]!.airportId,
    );
    expect(resolveAirport(d, "TAO", "2001-01-01").airport?.airportId).toBe(
      d.airports[1]!.airportId,
    );
  });

  it("does not let an unreviewed claim outside the query date block resolution", () => {
    const d = competing("verified", "pending");
    d.assignments[1]!.validFrom = exact("2001-01-01");
    expect(resolveAirport(d, "TAO", "2000-06-01").status).toBe("resolved");
    expect(resolveAirport(d, "TAO", "2001-06-01").status).toBe("uncertain");
  });
});
