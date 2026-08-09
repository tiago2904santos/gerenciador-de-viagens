import { readFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const floorsPath = process.argv[2] || ".github/js-coverage-floors.json";
const reportPath = process.argv[3] || "coverage-js/coverage-summary.json";
const metrics = ["lines", "functions", "branches", "statements"];

function normalize(filename) {
  return path.relative(process.cwd(), filename).replaceAll("\\", "/");
}

const floors = JSON.parse(await readFile(floorsPath, "utf8"));
const rawReport = JSON.parse(await readFile(reportPath, "utf8"));
const report = Object.fromEntries(
  Object.entries(rawReport)
    .filter(([filename]) => filename !== "total")
    .map(([filename, summary]) => [normalize(filename), summary]),
);
const failures = [];

console.log("Arquivo                                      Linhas  Funcoes  Ramos  Statements");
console.log("-------------------------------------------  ------  -------  -----  ----------");
for (const [filename, floor] of Object.entries(floors).sort()) {
  const summary = report[filename];
  if (!summary) {
    failures.push(`${filename}: arquivo nao medido`);
    continue;
  }
  console.log(
    `${filename.padEnd(43)}  ${String(summary.lines.pct).padStart(6)}  ` +
      `${String(summary.functions.pct).padStart(7)}  ${String(summary.branches.pct).padStart(5)}  ` +
      `${String(summary.statements.pct).padStart(10)}`,
  );
  for (const metric of metrics) {
    const actual = summary[metric].pct;
    const minimum = floor[metric];
    if (typeof minimum !== "number") {
      failures.push(`${filename}: piso ausente para ${metric}`);
    } else if (actual < minimum) {
      failures.push(`${filename}: ${metric} ${actual}% abaixo do piso ${minimum}%`);
    }
  }
}

if (failures.length) {
  for (const failure of failures) console.error(`::error title=Regressao de cobertura JS::${failure}`);
  process.exitCode = 1;
}
