import { readFile } from "node:fs/promises";
import { assertDataset } from "../src/validate.ts";
export async function loadDataset() {
  const input: unknown = JSON.parse(
    await readFile(new URL("../data/airports.json", import.meta.url), "utf8"),
  );
  assertDataset(input);
  return input;
}
