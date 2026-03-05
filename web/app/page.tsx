import Link from "next/link";

export default function HomePage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50">
      <h1 className="text-4xl font-bold text-gray-900 mb-2">ClawWork</h1>
      <p className="text-gray-600 mb-8">AI Agent Economic Survival — Production SaaS</p>
      <div className="flex gap-4">
        <Link
          href="/login"
          className="px-6 py-3 rounded-lg bg-gray-900 text-white font-medium hover:bg-gray-800"
        >
          Sign in
        </Link>
        <Link
          href="/dashboard"
          className="px-6 py-3 rounded-lg border border-gray-300 text-gray-700 font-medium hover:bg-gray-100"
        >
          Dashboard
        </Link>
      </div>
    </div>
  );
}
