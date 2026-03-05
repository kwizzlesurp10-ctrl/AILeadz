import {
  pgTable,
  uuid,
  text,
  timestamp,
  real,
  integer,
  boolean,
  jsonb,
  primaryKey,
  unique,
} from "drizzle-orm/pg-core";

export const users = pgTable("users", {
  id: uuid("id").primaryKey().defaultRandom(),
  email: text("email").notNull().unique(),
  name: text("name"),
  image: text("image"),
  emailVerified: timestamp("email_verified", { withTimezone: true }),
  stripeCustomerId: text("stripe_customer_id"),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
});

export const accounts = pgTable(
  "accounts",
  {
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    type: text("type").notNull(),
    provider: text("provider").notNull(),
    providerAccountId: text("provider_account_id").notNull(),
    refresh_token: text("refresh_token"),
    access_token: text("access_token"),
    expires_at: integer("expires_at"),
    token_type: text("token_type"),
    scope: text("scope"),
    id_token: text("id_token"),
    session_state: text("session_state"),
  },
  (t) => [primaryKey({ columns: [t.provider, t.providerAccountId] })]
);

export const sessions = pgTable("sessions", {
  sessionToken: text("session_token").primaryKey(),
  userId: uuid("user_id")
    .notNull()
    .references(() => users.id, { onDelete: "cascade" }),
  expires: timestamp("expires", { withTimezone: true }).notNull(),
});

export const agents = pgTable(
  "agents",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    signature: text("signature").notNull(),
    basemodel: text("basemodel"),
    configJson: jsonb("config_json"),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => [unique().on(t.userId, t.signature)]
);

export const balanceHistory = pgTable("balance_history", {
  id: uuid("id").primaryKey().defaultRandom(),
  agentId: uuid("agent_id")
    .notNull()
    .references(() => agents.id, { onDelete: "cascade" }),
  date: text("date").notNull(),
  balance: real("balance").notNull(),
  tokenCostDelta: real("token_cost_delta").default(0),
  workIncomeDelta: real("work_income_delta").default(0),
  tradingProfitDelta: real("trading_profit_delta").default(0),
  totalTokenCost: real("total_token_cost").default(0),
  totalWorkIncome: real("total_work_income").default(0),
  totalTradingProfit: real("total_trading_profit").default(0),
  netWorth: real("net_worth"),
  survivalStatus: text("survival_status"),
  taskId: text("task_id"),
  taskCompletionTimeSeconds: real("task_completion_time_seconds"),
  apiError: boolean("api_error").default(false),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
});

export const taskCompletions = pgTable("task_completions", {
  id: uuid("id").primaryKey().defaultRandom(),
  agentId: uuid("agent_id")
    .notNull()
    .references(() => agents.id, { onDelete: "cascade" }),
  taskId: text("task_id").notNull(),
  date: text("date").notNull(),
  attempt: integer("attempt").default(1),
  workSubmitted: boolean("work_submitted").default(false),
  evaluationScore: real("evaluation_score"),
  moneyEarned: real("money_earned").default(0),
  wallClockSeconds: real("wall_clock_seconds"),
  timestamp: timestamp("timestamp", { withTimezone: true }),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
});

export const tokenCosts = pgTable("token_costs", {
  id: uuid("id").primaryKey().defaultRandom(),
  agentId: uuid("agent_id")
    .notNull()
    .references(() => agents.id, { onDelete: "cascade" }),
  date: text("date").notNull(),
  inputTokens: integer("input_tokens").default(0),
  outputTokens: integer("output_tokens").default(0),
  costUsd: real("cost_usd").default(0),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
});

export const earningsLog = pgTable("earnings_log", {
  id: uuid("id").primaryKey().defaultRandom(),
  userId: uuid("user_id")
    .notNull()
    .references(() => users.id, { onDelete: "cascade" }),
  agentId: uuid("agent_id").references(() => agents.id, { onDelete: "set null" }),
  amount: real("amount").notNull(),
  source: text("source").notNull(), // 'work' | 'referral' | 'credit'
  taskId: text("task_id"),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
});

export const subscriptions = pgTable("subscriptions", {
  id: uuid("id").primaryKey().defaultRandom(),
  userId: uuid("user_id")
    .notNull()
    .references(() => users.id, { onDelete: "cascade" })
    .unique(),
  stripeSubscriptionId: text("stripe_subscription_id"),
  stripePriceId: text("stripe_price_id"),
  status: text("status").notNull(), // active | canceled | past_due | trialing
  currentPeriodEnd: timestamp("current_period_end", { withTimezone: true }),
  creditsRemaining: integer("credits_remaining").default(0),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
});

export const invites = pgTable("invites", {
  id: uuid("id").primaryKey().defaultRandom(),
  code: text("code").notNull().unique(),
  inviterUserId: uuid("inviter_user_id")
    .notNull()
    .references(() => users.id, { onDelete: "cascade" }),
  inviteeEmail: text("invitee_email"),
  freeMonths: integer("free_months").default(1),
  usedAt: timestamp("used_at", { withTimezone: true }),
  usedByUserId: uuid("used_by_user_id").references(() => users.id),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
});

export const userSettings = pgTable("user_settings", {
  userId: uuid("user_id")
    .primaryKey()
    .references(() => users.id, { onDelete: "cascade" }),
  hiddenAgentSignatures: jsonb("hidden_agent_signatures").$type<string[]>().default([]),
  displayNames: jsonb("display_names").$type<Record<string, string>>().default({}),
  leaderboardOptIn: boolean("leaderboard_opt_in").default(false),
  leaderboardDisplayName: text("leaderboard_display_name"),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
});
