import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import * as schema from "./schema";

const connectionString = process.env.DATABASE_URL ?? "postgresql://localhost:5432/clawwork";

const client = postgres(connectionString, { max: 10, prepare: false });

export function getDb() {
  return drizzle(client, { schema });
}

export * from "./schema";
