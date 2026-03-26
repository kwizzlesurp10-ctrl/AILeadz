import Link from "next/link";

const DASHBOARD_ITEMS = [
  {
    title: "Leaderboard",
    description: "Compare balances, earnings, and survival status across all active agents.",
    href: "/",
    cta: "Open leaderboard",
  },
  {
    title: "Agent Activity",
    description: "Review agent work logs and artifacts from the latest simulation runs.",
    href: "/",
    cta: "View activity",
  },
];

export default function DashboardPage() {
  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600">
          Track live agent performance and jump directly into the views you use most.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        {DASHBOARD_ITEMS.map((item) => (
          <article
            key={item.title}
            className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
          >
            <h2 className="text-lg font-semibold text-gray-900">{item.title}</h2>
            <p className="mt-2 text-sm text-gray-600">{item.description}</p>
            <Link
              href={item.href}
              className="mt-4 inline-flex text-sm font-medium text-blue-600 hover:text-blue-700"
            >
              {item.cta} →
            </Link>
          </article>
        ))}
      </div>
    </section>
  );
}
