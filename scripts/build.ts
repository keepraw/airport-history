import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { loadDataset } from "./load.ts";
const dataset = await loadDataset();
const pkg = JSON.parse(
  await readFile(new URL("../package.json", import.meta.url), "utf8"),
) as { version: string };
if (pkg.version !== dataset.dataVersion)
  throw new Error("package version must match dataVersion");
// Sort every object key, and stable-ID collections; no clock, network, locale or git state.
function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value !== null && typeof value === "object")
    return Object.fromEntries(
      Object.entries(value)
        .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
        .map(([k, v]) => [k, canonical(v)]),
    );
  return value;
}
const sorted = {
  ...dataset,
  airports: [...dataset.airports].sort((a, b) =>
    a.airportId < b.airportId ? -1 : 1,
  ),
  assignments: [...dataset.assignments].sort((a, b) =>
    a.assignmentId < b.assignmentId ? -1 : 1,
  ),
  sources: [...dataset.sources].sort((a, b) =>
    a.sourceId < b.sourceId ? -1 : 1,
  ),
};
const json = `${JSON.stringify(canonical(sorted), null, 2)}\n`;
const directory = new URL(`../dist/v${dataset.dataVersion}/`, import.meta.url);
await mkdir(directory, { recursive: true });
const files: Record<string, string> = {
  "airport-history.json": json,
  "dataset.schema.json": await readFile(
    new URL("../schema/dataset.schema.json", import.meta.url),
    "utf8",
  ),
  "LICENSE-DATA": await readFile(
    new URL("../LICENSE-DATA", import.meta.url),
    "utf8",
  ),
  "THIRD_PARTY_NOTICES.md": await readFile(
    new URL("../THIRD_PARTY_NOTICES.md", import.meta.url),
    "utf8",
  ),
};
const hashes: Record<string, string> = {};
for (const [name, contents] of Object.entries(files)) {
  await writeFile(new URL(name, directory), contents);
  hashes[name] = createHash("sha256").update(contents).digest("hex");
}
await writeFile(
  new URL("manifest.json", directory),
  `${JSON.stringify(
    {
      schemaVersion: dataset.schemaVersion,
      dataVersion: dataset.dataVersion,
      files: hashes,
    },
    null,
    2,
  )}\n`,
);
console.log(
  `Built dist/v${dataset.dataVersion}/ (${dataset.airports.length} airports, SHA-256 ${hashes["airport-history.json"]}).`,
);
