import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { buildArtifacts, DIRECTORY, hypothesis, loadInputs, ROOT, validateInputs } from "../scripts/evidence/first_admission.ts";
import { resolveAirport } from "../src/resolve.ts";

describe("first historical admission preparation", () => {
  it("reproduces scoped artifacts offline using singleton and combined real resolver calls", () => {
    const outputs = buildArtifacts();
    for (const [name, bytes] of Object.entries(outputs))
      expect(readFileSync(`${ROOT}/${DIRECTORY}/generated/${name}`, "utf8")).toBe(bytes);
    const diff = JSON.parse(outputs["resolver-diff.json"]!);
    expect(diff.formalNewResolvedQueries).toBe(0);
    expect(diff.combined.netNewResolved).toBe(9820);
    expect(diff.combined.byScheme).toEqual({ IATA: 2645, ICAO: 7175 });
    expect(diff.byRecord.map((r: { netNewResolved: number }) => r.netNewResolved)).toEqual([867, 867, 867, 867, 867, 2645, 195, 2645]);
    expect(diff.combined.formalToAccepted).toEqual({ "not_found->uncertain": 24740, "not_found->resolved": 9820 });
    expect(diff.combined.pendingToAccepted["uncertain->resolved"]).toBe(9820);
    expect(diff.combined.protectedQueries).toBe(146938);
    for (const field of ["changedPublishedResolved", "changedExistingAnswers", "newConflicts", "removedConflicts"])
      expect(diff.combined[field]).toBe(0);
  }, 120000);

  it("keeps all serialized additions pending and leaves existing records byte-identical", () => {
    const input = loadInputs(), scopes = input.selection.assignments.filter(r => r.class === "A");
    const pending = hypothesis(input, scopes, false);
    for (const collection of ["airports", "assignments", "sources", "names"] as const)
      expect(pending[collection].slice(0, input.base[collection].length)).toEqual(input.base[collection]);
    expect(pending.airports.slice(input.base.airports.length).every(p => p.name.status === "reference" &&
      p.coordinates.status === "reference" && p.timezone.status === "unknown")).toBe(true);
    expect(pending.assignments.slice(input.base.assignments.length).every(a => a.verificationStatus === "pending" && a.verifiedOn === null)).toBe(true);
    expect(pending.sources.slice(input.base.sources.length).every(s => s.verificationStatus === "pending")).toBe(true);
    expect(input.selection.physicalAirports).toHaveLength(7);
    expect(input.selection.assignments.filter(r => r.class === "B").map(r => r.code)).toEqual(["MJV"]);
    const approved = hypothesis(input, scopes);
    expect(resolveAirport(pending, "VOSR", "2025-01-01", "ICAO").status).toBe("uncertain");
    expect(resolveAirport(approved, "VOSR", "2025-01-01", "ICAO").status).toBe("resolved");
    expect(resolveAirport(approved, "VOSR", "2024-02-22", "ICAO").status).toBe("uncertain");
    expect(resolveAirport(approved, "VOSR", "2026-07-09", "ICAO").status).toBe("uncertain");
    expect(resolveAirport(approved, "LELC", "2019-08-02", "ICAO").status).toBe("uncertain");
    expect(resolveAirport(approved, "MJV", "2026-10-28", "IATA").status).toBe("not_found");
  });

  it("does not let classification, dates or physical review silently authorize more", () => {
    let input = loadInputs();
    input.selection.assignments[0]!.reviewer = "invented" as never;
    expect(() => validateInputs(input)).toThrow(/cannot record a human approval/);
    input = loadInputs();
    input.selection.assignments[0]!.exactAuthorization!.validTo.earliest = "2027-01-01";
    expect(() => validateInputs(input)).toThrow(/authorization window/);
    input = loadInputs();
    input.selection.assignments[0]!.recommendedWindow![0] = "2024-02-22";
    input.selection.assignments[0]!.exactAuthorization!.validFrom.latest = "2024-02-22";
    expect(() => validateInputs(input)).toThrow(/dated endpoint/);
    input = loadInputs();
    input.selection.physicalAirports.shift();
    expect(() => validateInputs(input)).toThrow(/physical review missing/);
    input = loadInputs();
    input.selection.physicalAirports[0]!.coordinates.longitude += 0.01;
    expect(() => validateInputs(input)).toThrow(/reference attributes changed/);
  });

  it("rejects duplicate scopes, blocked records and competing pending sites", () => {
    const input = loadInputs(), first = input.selection.assignments[0]!;
    expect(() => hypothesis(input, [first, first])).toThrow(/unique A scopes/);
    expect(() => hypothesis(input, [input.selection.assignments.at(-1)!])).toThrow(/unique A scopes/);
    input.stages.transfers!.assignments.push({ ...input.stages.global!.assignments.find(a => a.assignmentId === first.recordId)!,
      assignmentId: "competing-record", airportId: "different-site" });
    expect(() => validateInputs(input)).toThrow(/Competing pending/);
  });

  it("fails the unchanged actual admission gate without explicit claim review", () => {
    const result = execFileSync("python3", ["-c", `import sys,json
from pathlib import Path
sys.path.insert(0,'scripts/reference')
from admissions import validate_admission
base=json.loads(Path('test/curated-0.8.0.json').read_text())
proposed=json.loads(Path('${DIRECTORY}/generated/scoped-proposed-data.json').read_text())
dossier=json.loads(Path('${DIRECTORY}/generated/dossier.json').read_text())
batches=[json.loads(p.read_text()) for p in sorted(Path('research/evidence/global/generated/batches').glob('*.json'))]
try: validate_admission(base,proposed,batches,dossier)
except ValueError as error:
 assert 'explicit claim review' in str(error),str(error)
 print('pending scoped candidate rejected by unchanged admission gate')
else: raise AssertionError('Unauthorized admission succeeded')`], { cwd: ROOT, encoding: "utf8" });
    expect(result).toContain("rejected by unchanged admission gate");
  });
});
