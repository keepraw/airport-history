import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFile, readdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";
import { assertDataset } from "../src/validate.ts";
import { loadDataset } from "../scripts/load.ts";
import { resolveAirport, resolveAirportName } from "../src/index.ts";
it("builds identical bytes twice and ships a parseable, independently checked artifact", async () => {
  const root = fileURLToPath(new URL("../", import.meta.url));
  const build = fileURLToPath(new URL("../scripts/build.ts", import.meta.url));
  const formal = await loadDataset();
  const dist = new URL(`../dist/v${formal.dataVersion}/`, import.meta.url);
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
  expect(manifest.schemaVersion).toBe("4.0.0");
  expect(manifest.dataVersion).toBe(formal.dataVersion);
  for (const license of ["LICENSE", "LICENSE-DATA", "THIRD_PARTY_NOTICES.md"]) {
    expect(first[license]).toBe(
      await readFile(new URL(`../${license}`, import.meta.url), "utf8"),
    );
    expect(manifest.files).toHaveProperty(license);
  }
  for (const [name, digest] of Object.entries(manifest.files))
    expect(createHash("sha256").update(first[name]!).digest("hex")).toBe(
      digest,
    );
  const dataset: unknown = JSON.parse(first["airport-history.json"]!);
  assertDataset(dataset);
  expect(dataset.schemaVersion).toBe(manifest.schemaVersion);
  expect(dataset.dataVersion).toBe(manifest.dataVersion);
  expect(dataset.airports).toHaveLength(formal.airports.length);
  expect(dataset.assignments).toHaveLength(formal.assignments.length);
  expect(dataset.names).toHaveLength(formal.names.length);
  expect(dataset.names.map((n) => n.nameId)).toEqual(
    dataset.names.map((n) => n.nameId).sort(),
  );
  const astanaId = "apt_99f19660-7609-49c5-b221-ed4a37046566";
  expect(resolveAirportName(dataset, astanaId, "2015-01-01").name).toBe(
    "Международный аэропорт Астана",
  );
  expect(resolveAirportName(dataset, astanaId, "2017-06-21").status).toBe(
    "uncertain",
  );
  expect(resolveAirportName(dataset, astanaId, "2024-01-01").name).toBe(
    "Международный аэропорт Нурсултан Назарбаев",
  );
  expect(resolveAirport(dataset, "HKG", "2000-01-01").status).toBe("resolved");
  expect(resolveAirport(dataset, "ISB", "2018-05-03").status).toBe("uncertain");
  expect(resolveAirport(dataset, "BER", "2020-10-26").status).toBe("resolved");
  expect(resolveAirport(dataset, "KIV", "2024-01-19").status).toBe("not_found");
}, 30_000);
