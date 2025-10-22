import type { NextApiRequest, NextApiResponse } from "next";
import { HTTPStore, openArray, slice } from "zarr";
import { parse as parseWkt } from "@terraformer/wkt-parser";

type FeatureResponse = {
  type: "FeatureCollection";
  features: GeoJSON.Feature[];
  columns: string[];
};

const CACHE = new Map<string, { timestamp: number; payload: FeatureResponse }>();
const CACHE_TTL_MS = 60 * 1000;
const MAX_LIMIT = 2000;

function assertHttpUrl(raw: string): void {
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch (error) {
    throw new Error("URL is not valid.");
  }
  if (!/^https?:$/.test(parsed.protocol)) {
    throw new Error("Only http and https URLs are allowed.");
  }
}

async function getTableName(store: HTTPStore, explicit?: string): Promise<string> {
  if (explicit) {
    return explicit;
  }
  const entries = await store.listDir("tables");
  const child = entries.children.find((entry) => entry.kind === "dir");
  if (!child) {
    throw new Error("No AnnData tables found in bundle.");
  }
  return child.pathSegment;
}

async function resolveColumns(store: HTTPStore, tableName: string): Promise<string[]> {
  const obsPath = `tables/${tableName}/obs`;
  const attrsBuffer = await store.getItem(`${obsPath}/.zattrs`);
  if (!attrsBuffer) {
    throw new Error("Unable to read AnnData observation metadata.");
  }
  const text = new TextDecoder().decode(attrsBuffer);
  const attrs = JSON.parse(text) as { [key: string]: unknown };
  const order = Array.isArray(attrs["column-order"]) ? (attrs["column-order"] as string[]) : [];
  if (order.length > 0) {
    return order;
  }
  const listing = await store.listDir(obsPath);
  const allowable = new Set(["array", "dataset"]);
  return listing.children
    .filter((entry) => allowable.has(entry.kind))
    .map((entry) => entry.pathSegment)
    .filter((name) => !name.startsWith("."));
}

async function readColumn(store: HTTPStore, path: string, count: number): Promise<unknown[]> {
  const array = await openArray({ store, path, mode: "r" });
  const total = array.shape[0];
  const end = Math.min(count, total);
  const data = await array.get([slice(0, end)]);
  return Array.from(data as Iterable<unknown>);
}

function geometryFromRow(row: Record<string, unknown>): GeoJSON.Geometry | null {
  const wkt = row["polygon_wkt"];
  if (typeof wkt === "string" && wkt.trim()) {
    try {
      const geometry = parseWkt(wkt.trim());
      return geometry as GeoJSON.Geometry;
    } catch (error) {
      return null;
    }
  }
  const x = typeof row["x"] === "number" ? row["x"] : Number(row["x"]);
  const y = typeof row["y"] === "number" ? row["y"] : Number(row["y"]);
  if (Number.isFinite(x) && Number.isFinite(y)) {
    return {
      type: "Point",
      coordinates: [x as number, y as number]
    } satisfies GeoJSON.Point;
  }
  return null;
}

async function buildFeatureCollection(url: string, tableName?: string, limitParam?: string | string[]): Promise<FeatureResponse> {
  assertHttpUrl(url);
  const store = new HTTPStore(url, { fetch: fetch as unknown as typeof globalThis.fetch });
  const hasTables = await store.containsItem("tables/.zgroup");
  if (!hasTables) {
    throw new Error("Bundle does not contain tables.");
  }
  const name = await getTableName(store, typeof tableName === "string" ? tableName : undefined);
  const limitCandidate = Array.isArray(limitParam) ? limitParam[0] : limitParam;
  const limit = Math.min(Number(limitCandidate) || MAX_LIMIT, MAX_LIMIT);
  const columns = await resolveColumns(store, name);
  if (!columns.length) {
    throw new Error("No observation columns available.");
  }
  const obsPath = `tables/${name}/obs`;
  const data: Record<string, unknown[]> = {};
  for (const column of columns) {
    data[column] = await readColumn(store, `${obsPath}/${column}`, limit);
  }
  const firstColumn = columns[0];
  const rows = data[firstColumn]?.length ?? 0;
  const features: GeoJSON.Feature[] = [];
  for (let index = 0; index < rows; index += 1) {
    const row: Record<string, unknown> = {};
    for (const column of columns) {
      row[column] = data[column]?.[index];
    }
    const geometry = geometryFromRow(row);
    if (!geometry) {
      continue;
    }
    features.push({
      type: "Feature",
      geometry,
      properties: row
    });
  }
  return {
    type: "FeatureCollection",
    features,
    columns
  } satisfies FeatureResponse;
}

export default async function handler(request: NextApiRequest, response: NextApiResponse): Promise<void> {
  if (request.method !== "GET") {
    response.setHeader("Allow", "GET");
    response.status(405).json({ error: "Method not allowed" });
    return;
  }
  const url = typeof request.query.url === "string" ? request.query.url : undefined;
  if (!url) {
    response.status(400).json({ error: "Missing url query parameter" });
    return;
  }
  const tableName = typeof request.query.table === "string" ? request.query.table : undefined;
  const cacheKey = `${url}|${tableName ?? ""}|${request.query.limit ?? ""}`;
  const now = Date.now();
  const cached = CACHE.get(cacheKey);
  if (cached && now - cached.timestamp < CACHE_TTL_MS) {
    response.status(200).json(cached.payload);
    return;
  }
  try {
    const payload = await buildFeatureCollection(url, tableName, request.query.limit);
    CACHE.set(cacheKey, { timestamp: now, payload });
    response.status(200).json(payload);
  } catch (error) {
    response.status(500).json({ error: (error as Error).message });
  }
}
