import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";
import { authOptions } from "@/lib/auth";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getServerSession(authOptions);
  if (!session) redirect("/login");

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-gray-900">ClawWork Dashboard</span>
          <span className="text-sm text-gray-500">{session.user?.email}</span>
        </div>
      </header>
      <main className="p-6">{children}</main>
    </div>
  );
}
