import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { isDeepStrictEqual, parseArgs } from "node:util";
import { queryHorizon } from "../src/index.ts";

const root = new URL("../", import.meta.url);
const datasetPath = "data/airports.json";
const manifestPath = new URL("data/production-manifest.json", root);
const versionPattern = /^\d+\.\d+\.\d+$/;

function git(...args: string[]): Buffer {
  return execFileSync("git", args, { cwd: root, maxBuffer: Infinity });
}

function sha256(bytes: Buffer): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function versionIsNewer(version: string, previous: string): boolean {
  const parts = version.split(".").map(BigInt);
  const oldParts = previous.split(".").map(BigInt);
  for (const [index, part] of parts.entries()) {
    if (part !== oldParts[index]) return part > oldParts[index]!;
  }
  return false;
}

function productionManifest(commit: string) {
  if (!/^[0-9a-f]{40}$/.test(commit) || git("cat-file", "-t", commit).toString().trim() !== "commit") {
    throw new Error("Use the full SHA of a data commit in the current history");
  }
  git("merge-base", "--is-ancestor", commit, "HEAD");
  const bytes = git("show", `${commit}:${datasetPath}`);
  const { dataVersion, schemaVersion } = JSON.parse(bytes.toString("utf8"));
  const { version } = JSON.parse(git("show", `${commit}:package.json`).toString("utf8"));
  if (!versionPattern.test(dataVersion) || !versionPattern.test(schemaVersion) || dataVersion !== version) {
    throw new Error("The committed schema, package and data versions must be valid and the package must match the data");
  }
  return {
    dataVersion,
    schemaVersion,
    commit,
    queryHorizon: JSON.parse(git("show", `${commit}:src/query-horizon.json`).toString("utf8")),
    files: { [datasetPath]: { sha256: sha256(bytes) } },
  };
}

const { values } = parseArgs({
  options: {
    check: { type: "boolean" },
    commit: { type: "string" },
    release: { type: "boolean" },
  },
});
if (Boolean(values.check) === Boolean(values.commit) || (values.release && !values.check)) {
  throw new Error("Use --commit <full SHA> or --check [--release]");
}

const previous = existsSync(manifestPath)
  ? JSON.parse(readFileSync(manifestPath, "utf8"))
  : null;
if (values.check && !previous) throw new Error("Production manifest is missing");
const manifest = productionManifest(values.commit ?? previous.commit);

if (values.check) {
  if (!isDeepStrictEqual(previous, manifest)) {
    throw new Error("Production manifest differs from the immutable data commit");
  }
  const localBytes = readFileSync(new URL(datasetPath, root));
  const { dataVersion } = JSON.parse(localBytes.toString("utf8"));
  if (values.release || !versionIsNewer(dataVersion, manifest.dataVersion)) {
    if (
      manifest.files[datasetPath].sha256 !== sha256(localBytes) ||
      !isDeepStrictEqual(manifest.queryHorizon, queryHorizon)
    ) {
      throw new Error("The formal dataset or query horizon differs from the production manifest");
    }
  }
} else {
  if (previous && !isDeepStrictEqual(previous, manifest) && !versionIsNewer(manifest.dataVersion, previous.dataVersion)) {
    throw new Error("Advance dataVersion before publishing a different production dataset");
  }
  writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
}
console.log(`Production manifest v${manifest.dataVersion} at ${manifest.commit}`);
