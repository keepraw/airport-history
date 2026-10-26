import { loadDataset } from "./load.ts";
import { validateDataset } from "../src/validate.ts";
const dataset = await loadDataset();
for (const warning of validateDataset(dataset).warnings)
  console.warn(`WARNING: ${warning}`);
console.log(
  `Valid: ${dataset.airports.length} airports, ${dataset.assignments.length} assignments, ${dataset.sources.length} sources.`,
);
