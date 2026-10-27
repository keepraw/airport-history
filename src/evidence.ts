import type { CodeAssignment, Source } from "./types.ts";

/** Shared review gate for resolution and confirmed-conflict detection.
 * Evidence type describes provenance; it does not replace review or rank winners.
 * Source content must still be reviewed for the actual historical claim.
 */
export function hasReviewedEvidence(
  assignment: Pick<
    CodeAssignment,
    "verificationStatus" | "verifiedOn" | "sourceIds" | "evidenceType"
  >,
  sources: ReadonlyMap<string, Source>,
): boolean {
  const verifiedOn = assignment.verifiedOn;
  return (
    assignment.verificationStatus === "verified" &&
    verifiedOn !== null &&
    assignment.sourceIds.length > 0 &&
    ["primary_direct", "indirect", "continuity_inference"].includes(
      assignment.evidenceType,
    ) &&
    assignment.sourceIds.every((id) => {
      const source = sources.get(id);
      return (
        source?.verificationStatus === "verified" &&
        source.accessedOn <= verifiedOn
      );
    }) &&
    (assignment.evidenceType !== "primary_direct" ||
      assignment.sourceIds.some(
        (id) => sources.get(id)?.sourceType === "primary",
      ))
  );
}
