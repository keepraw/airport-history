import { readFileSync, createReadStream } from "node:fs";
import { createGunzip } from "node:zlib";
import { createInterface } from "node:readline";
import { Ajv } from "ajv";

const root = new URL("../../", import.meta.url);
const schema: unknown = JSON.parse(readFileSync(new URL("schema/reference-record.schema.json", root), "utf8"));
const validate = new Ajv({ allErrors: true, strict: true }).compile(schema as object);
let count = 0;
for (const shard of "0123456789abcdef") {
  const lines = createInterface({ input: createReadStream(new URL(`reference/generated/records.${shard}.jsonl.gz`, root)).pipe(createGunzip()), crlfDelay: Infinity });
  for await (const line of lines) {
    const row: unknown = JSON.parse(line);
    if (!validate(row)) throw new Error(JSON.stringify(validate.errors));
    count++;
  }
}
console.log(`Validated reference schema 1.0.0 for ${count.toLocaleString("en-US")} source records.`);
