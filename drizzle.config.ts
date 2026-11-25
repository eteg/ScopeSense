import { defineConfig } from "drizzle-kit";

// Apenas gera SQL em db/migrations; quem aplica é o wrangler
// (npm run db:migrate:local | db:migrate:dev | db:migrate:prod).
export default defineConfig({
  dialect: "sqlite",
  schema: "./db/schema.ts",
  out: "./db/migrations",
});
