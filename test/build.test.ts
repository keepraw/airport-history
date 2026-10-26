import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFile, readdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";
import { assertDataset } from "../src/validate.ts";
import { resolveAirport } from "../src/resolve.ts";
it("builds identical bytes twice and ships a parseable, independently checked artifact", async () => {
  const root = fileURLToPath(new URL("../", import.meta.url));
  const build = fileURLToPath(new URL("../scripts/build.ts", import.meta.url));
  const dist = new URL("../dist/v0.2.0/", import.meta.url);
  const run = (tz: string) =>
    execFileSync(process.execPath, [build], {
      cwd: root,
      env: { ...process.env, TZ: tz },
    });
  const snapshot = async () =>
    Object.fromEntries(
      await Promise.all(
        (await readdir(dist))
          .sort()
          .map(async (name) => [
            name,
            await readFile(new URL(name, dist), "utf8"),
          ]),
      ),
    );
  run("Pacific/Honolulu");
  const first = await snapshot();
  run("Asia/Shanghai");
  expect(await snapshot()).toEqual(first);
  const manifest = JSON.parse(first["manifest.json"]!) as {
    schemaVersion: string;
    dataVersion: string;
    files: Record<string, string>;
  };
  expect(manifest.schemaVersion).toBe("2.0.0");
  expect(manifest.dataVersion).toBe("0.2.0");
  const license = await readFile(new URL("../LICENSE", import.meta.url), "utf8");
  expect(first).toHaveProperty("LICENSE");
  expect(first["LICENSE"]).toBe(license);
  expect(manifest.files).toHaveProperty("LICENSE");
  expect(manifest.files["LICENSE"]).toBe(
    createHash("sha256").update(license).digest("hex"),
  );
  for (const [name, digest] of Object.entries(manifest.files))
    expect(createHash("sha256").update(first[name]!).digest("hex")).toBe(
      digest,
    );
  const dataset: unknown = JSON.parse(first["airport-history.json"]!);
  assertDataset(dataset);
  expect(dataset.schemaVersion).toBe(manifest.schemaVersion);
  expect(dataset.dataVersion).toBe(manifest.dataVersion);
  expect(
    dataset.assignments.every((a) => a.evidenceType === "continuity_inference"),
  ).toBe(true);
  expect(resolveAirport(dataset, "HKG", "1997-06-01").status).toBe("resolved");
});
