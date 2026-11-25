import { sql } from "drizzle-orm";
import { getDb } from "@/lib/db";

export async function GET() {
  try {
    const db = await getDb();
    await db.run(sql`select 1`);
    return Response.json({ status: "ok", db: "ok" });
  } catch (error) {
    return Response.json({ status: "error", db: String(error) }, { status: 503 });
  }
}
