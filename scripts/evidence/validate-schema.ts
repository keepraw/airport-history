import { readFileSync, createReadStream } from "node:fs";
import { createGunzip } from "node:zlib";
import { createInterface } from "node:readline";
import { Ajv } from "ajv";

const root = new URL("../../", import.meta.url);
const schema = JSON.parse(readFileSync(new URL("schema/evidence-observation.schema.json", root), "utf8")) as object;
const validate = new Ajv({ allErrors: true, strict: true }).compile(schema);
const lines = createInterface({ input: createReadStream(new URL("research/evidence/generated/observations.jsonl.gz", root)).pipe(createGunzip()), crlfDelay: Infinity });
let count = 0;
for await (const line of lines) {
  if (!validate(JSON.parse(line))) throw new Error(JSON.stringify(validate.errors));
  count++;
}
console.log(`Validated strict evidence schema for ${count} observations.`);
