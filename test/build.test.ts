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
  const dist = new URL("../dist/v0.1.0/", import.meta.url);
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
    files: Record<string, string>;
  };
  for (const [name, digest] of Object.entries(manifest.files))
    expect(createHash("sha256").update(first[name]!).digest("hex")).toBe(
      digest,
    );
  const dataset: unknown = JSON.parse(first["airport-history.json"]!);
  assertDataset(dataset);
  expect(resolveAirport(dataset, "HKG", "1997-06-01").status).toBe("resolved");
});
