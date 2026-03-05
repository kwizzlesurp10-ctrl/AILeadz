export default function DashboardPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Dashboard</h1>
      <p className="text-gray-600">
        Your agents and balance will appear here. The LiveBench API can be proxied at{" "}
        <code className="rounded bg-gray-200 px-1">/api/livebench/*</code>.
      </p>
    </div>
  );
}
