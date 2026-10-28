import { expect, it } from "vitest";
import { loadDataset } from "../scripts/load.ts";
import { resolveAirport } from "../src/index.ts";
import { validateDataset } from "../src/validate.ts";

const data = await loadDataset();

it("classifies all forty curated intervals as reviewed continuity inferences", () => {
  expect(data.assignments.map((a) => a.assignmentId).sort()).toEqual([
    "iata-aap-pranoto",
    "iata-ber-schonefeld-brandenburg",
    "iata-den-denver",
    "iata-den-stapleton",
    "iata-dkr-yoff",
    "iata-dss-diass",
    "iata-hkg-chek-lap-kok",
    "iata-hkg-kai-tak",
    "iata-isb-benazir-bhutto",
    "iata-isb-islamabad",
    "iata-isl-ataturk",
    "iata-isl-istanbul",
    "iata-ist-ataturk",
    "iata-ist-istanbul",
    "iata-kiv-chisinau",
    "iata-kti-techo",
    "iata-nqz-astana",
    "iata-pnh-pochentong",
    "iata-rmo-chisinau",
    "iata-rov-platov",
    "iata-rov-rostov-on-don",
    "iata-rvi-rostov-on-don",
    "iata-sxf-schonefeld-brandenburg",
    "iata-tao-jiaodong",
    "iata-tao-liuting",
    "iata-tse-astana",
    "iata-ynt-laishan",
    "iata-ynt-penglai",
    "icao-eddb-berlin",
    "icao-gobd-diass",
    "icao-gooy-yoff",
    "icao-ltba-ataturk",
    "icao-ltfm-istanbul",
    "icao-opis-islamabad",
    "icao-oprn-chaklala",
    "icao-uacc-astana",
    "icao-vdpp-pochentong",
    "icao-vdti-techo",
    "icao-vhhh-chek-lap-kok",
    "icao-vhhh-kai-tak",
  ]);
  for (const a of data.assignments) {
    expect(a.evidenceType).toBe("continuity_inference");
    expect(a.verificationStatus).toBe("verified");
    expect(a.sourceIds.length).toBeGreaterThan(1);
  }
});

it("keeps first-party opening histories separate from code-assignment evidence", () => {
  for (const sourceId of ["hkg-transfer", "den-transfer"]) {
    expect(data.sources.find((s) => s.sourceId === sourceId)?.sourceType).toBe(
      "primary",
    );
    const assignments = data.assignments.filter((a) =>
      a.sourceIds.includes(sourceId),
    );
    expect(assignments.length).toBeGreaterThan(0);
    expect(
      assignments.every((a) => a.evidenceType === "continuity_inference"),
    ).toBe(true);
  }
  for (const sourceId of ["tao-code", "hkg-code", "den-code"])
    expect(data.sources.find((s) => s.sourceId === sourceId)?.sourceType).toBe(
      "secondary",
    );
  const result = resolveAirport(data, "HKG", "1997-06-01");
  expect(result.status).toBe("resolved");
  expect(result.candidates[0]!.assignment.evidenceType).toBe(
    "continuity_inference",
  );
  expect(result.evidence.some((s) => s.sourceType === "primary")).toBe(true);
});

it("rejects schema 1 rather than silently inventing provenance", () => {
  expect(
    validateDataset({ ...data, schemaVersion: "1.0.0" }).errors.join("\n"),
  ).toContain("constant");
});

it.each(["sourceType", "evidenceType"] as const)(
  "requires a recognized %s",
  (field) => {
    for (const value of [undefined, "official"]) {
      const d = structuredClone(data);
      if (field === "sourceType")
        Object.assign(d.sources[0]!, { sourceType: value });
      else Object.assign(d.assignments[0]!, { evidenceType: value });
      expect(validateDataset(d).errors.length).toBeGreaterThan(0);
    }
  },
);

it("requires a primary source for primary_direct, without upgrading indirect evidence", () => {
  const d = structuredClone(data);
  // A synthetic claim tests the structural gate, not any real allocation proof.
  const a = { ...d.assignments[0]!, assignmentId: "synthetic-claim", code: "ZZZ" };
  d.assignments = [a];
  a.sourceIds = ["ourairports-20261025"];
  a.evidenceType = "indirect";
  expect(validateDataset(d).errors).toEqual([]);
  a.evidenceType = "primary_direct";
  expect(validateDataset(d).errors.join("\n")).toContain(
    "primary_direct needs a primary source",
  );
  expect(resolveAirport(d, "ZZZ", "2017-06-01").status).toBe("uncertain");
  d.sources.push({
    ...d.sources[0]!,
    sourceId: "synthetic-primary",
    sourceType: "primary",
    title: "Synthetic allocation notice (test only)",
    url: "https://example.org/synthetic-allocation",
    note: "Synthetic test record, not historical evidence.",
  });
  a.sourceIds = ["synthetic-primary"];
  expect(validateDataset(d).errors).toEqual([]);
  expect(resolveAirport(d, "ZZZ", "2017-06-01").status).toBe("resolved");
});
