/**
 * Migration: file-based agent_data/* → PostgreSQL
 *
 * Prereqs: DATABASE_URL set, migrations applied (packages/db).
 * Usage: npx tsx scripts/migrate_file_data_to_postgres.ts [--default-user-id=<uuid>]
 *
 * Reads livebench/data/agent_data/{signature}/economic/*.jsonl and
 * activity_logs, work, memory; creates agents and balance_history,
 * task_completions, token_costs for the given user.
 */

import { readFileSync, readdirSync, existsSync } from "fs";
import { join } from "path";
import { and, eq } from "drizzle-orm";
import { getDb, agents, balanceHistory, taskCompletions, tokenCosts } from "../packages/db";

const AGENT_DATA_ROOT = join(process.cwd(), "livebench", "data", "agent_data");

type JsonlLine = Record<string, unknown>;

function readJsonl<T = JsonlLine>(filePath: string): T[] {
  if (!existsSync(filePath)) return [];
  const content = readFileSync(filePath, "utf-8");
  return content
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line) as T);
}

async function main() {
  const defaultUserId = process.argv.find((a) => a.startsWith("--default-user-id="))?.split("=")[1];
  if (!defaultUserId) {
    console.error("Usage: npx tsx scripts/migrate_file_data_to_postgres.ts --default-user-id=<uuid>");
    process.exit(1);
  }

  const db = getDb();

  if (!existsSync(AGENT_DATA_ROOT)) {
    console.error("Agent data root not found:", AGENT_DATA_ROOT);
    process.exit(1);
  }

  const signatures = readdirSync(AGENT_DATA_ROOT, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name);

  for (const signature of signatures) {
    const agentDir = join(AGENT_DATA_ROOT, signature);
    const economicDir = join(agentDir, "economic");

    let agentId: string | undefined = (
      await db.query.agents.findFirst({
        where: and(eq(agents.userId, defaultUserId), eq(agents.signature, signature)),
        columns: { id: true },
      })
    )?.id;
    if (!agentId) {
      const [inserted] = await db
        .insert(agents)
        .values({
          userId: defaultUserId,
          signature,
          basemodel: signature.split("-")[0] ?? null,
        })
        .onConflictDoNothing()
        .returning({ id: agents.id });
      agentId = inserted?.id;
    }
    if (!agentId) continue;

    const balancePath = join(economicDir, "balance.jsonl");
    const balanceRows = readJsonl<{ date: string; balance: number; token_cost_delta?: number; work_income_delta?: number; total_token_cost?: number; total_work_income?: number; net_worth?: number; survival_status?: string; task_id?: string; task_completion_time_seconds?: number; api_error?: boolean }>(balancePath);
    for (const row of balanceRows) {
      await db.insert(balanceHistory).values({
        agentId,
        date: row.date,
        balance: row.balance,
        tokenCostDelta: row.token_cost_delta ?? 0,
        workIncomeDelta: row.work_income_delta ?? 0,
        totalTokenCost: row.total_token_cost ?? 0,
        totalWorkIncome: row.total_work_income ?? 0,
        netWorth: row.net_worth ?? row.balance,
        survivalStatus: row.survival_status ?? null,
        taskId: row.task_id ?? null,
        taskCompletionTimeSeconds: row.task_completion_time_seconds ?? null,
        apiError: row.api_error ?? false,
      });
    }

    const completionsPath = join(economicDir, "task_completions.jsonl");
    const completionRows = readJsonl<{ task_id: string; date: string; attempt?: number; work_submitted?: boolean; evaluation_score?: number; money_earned?: number; wall_clock_seconds?: number; timestamp?: string }>(completionsPath);
    for (const row of completionRows) {
      await db.insert(taskCompletions).values({
        agentId,
        taskId: row.task_id,
        date: row.date,
        attempt: row.attempt ?? 1,
        workSubmitted: row.work_submitted ?? true,
        evaluationScore: row.evaluation_score ?? null,
        moneyEarned: row.money_earned ?? 0,
        wallClockSeconds: row.wall_clock_seconds ?? null,
        timestamp: row.timestamp ? new Date(row.timestamp) : null,
      });
    }

    const tokenCostsPath = join(economicDir, "token_costs.jsonl");
    if (existsSync(tokenCostsPath)) {
      const costRows = readJsonl<{ date: string; input_tokens?: number; output_tokens?: number; cost_usd?: number }>(tokenCostsPath);
      for (const row of costRows) {
        await db.insert(tokenCosts).values({
          agentId,
          date: row.date,
          inputTokens: row.input_tokens ?? 0,
          outputTokens: row.output_tokens ?? 0,
          costUsd: row.cost_usd ?? 0,
        });
      }
    }

    console.log("Migrated agent:", signature);
  }

  console.log("Migration complete.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
