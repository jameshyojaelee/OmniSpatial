import { performance } from "node:perf_hooks";
import { writeFileSync } from "node:fs";
import { featureCollectionFromColumns, FeatureResponse } from "../pages/api/geojson";

const DEFAULT_FEATURES = 1_000_000;

type StressResult = {
  features: number;
  durationMs: number;
  rssPeakMb: number;
};

function parseArgs(argv: string[]): { count: number; report?: string } {
  let count = DEFAULT_FEATURES;
  let report: string | undefined;
  for (const arg of argv) {
    if (arg.startsWith("--features=")) {
      count = Number.parseInt(arg.split("=")[1] ?? "", 10);
    } else if (arg.startsWith("--report=")) {
      report = arg.split("=")[1];
    }
  }
  const envCount = process.env.GEOJSON_STRESS_FEATURES;
  if (envCount) {
    count = Number.parseInt(envCount, 10);
  }
  return { count, report };
}

function memoryUsageMb(): number {
  const rss = process.memoryUsage().rss;
  return rss / (1024 * 1024);
}

function runStress(count: number): { result: FeatureResponse; metrics: StressResult } {
  const columns = ["cell_id", "x", "y"];
  const data: Record<string, unknown[]> = {
    cell_id: new Array<string>(count),
    x: new Array<number>(count),
    y: new Array<number>(count)
  };

  for (let index = 0; index < count; index += 1) {
    data.cell_id[index] = `cell_${index}`;
    data.x[index] = index % 1000;
    data.y[index] = Math.floor(index / 1000);
  }

  const baseline = memoryUsageMb();
  const start = performance.now();
  const featureCollection = featureCollectionFromColumns(columns, data);
  const durationMs = performance.now() - start;
  const rssPeakMb = Math.max(baseline, memoryUsageMb());

  return {
    result: featureCollection,
    metrics: {
      features: featureCollection.features.length,
      durationMs,
      rssPeakMb
    }
  };
}

function main(): void {
  const { count, report } = parseArgs(process.argv.slice(2));
  console.log(`Generating synthetic feature collection with ${count.toLocaleString()} entries.`);
  const { metrics } = runStress(count);
  console.log(JSON.stringify(metrics, null, 2));
  if (report) {
    writeFileSync(report, JSON.stringify(metrics, null, 2), { encoding: "utf-8" });
    console.log(`Metrics written to ${report}`);
  }
}

main();
