import type { Boundary, CodeAssignment } from "./types.ts";
const DAY = 86_400_000;
/** Gregorian civil-date arithmetic only; UTC is an arithmetic device, not input timezone. */
export function dateNumber(value: string): number {
  if (!/^(?!0000)\d{4}-\d{2}-\d{2}$/.test(value)) return NaN;
  const n = Date.parse(`${value}T00:00:00Z`);
  return Number.isFinite(n) && new Date(n).toISOString().slice(0, 10) === value
    ? n / DAY
    : NaN;
}
export function bounds(boundary: Boundary): [number, number] {
  return [
    boundary.earliest === null ? -Infinity : dateNumber(boundary.earliest),
    boundary.latest === null ? Infinity : dateNumber(boundary.latest),
  ];
}
export function interval(
  assignment: Pick<CodeAssignment, "validFrom" | "validTo">,
): {
  possible: [number, number];
  certain: [number, number];
} {
  const [startMin, startMax] = bounds(assignment.validFrom);
  const [endMin, endMax] = bounds(assignment.validTo);
  return { possible: [startMin, endMax], certain: [startMax, endMin] };
}
export function overlaps(a: [number, number], b: [number, number]): boolean {
  return Math.max(a[0], b[0]) < Math.min(a[1], b[1]);
}
