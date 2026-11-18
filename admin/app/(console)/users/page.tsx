import type { Metadata } from "next";
import { Suspense } from "react";
import { UsersTable, type AdminUser } from "@/components/admin/users-table";
import { backendGet, requireAdmin } from "@/lib/server-api";

export const metadata: Metadata = { title: "Users" };

export default function UsersPage({ searchParams }: PageProps<"/users">) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">Users</h1>
        <p className="mt-1.5 text-sm text-slate-600">Account details only. Conversation content is never shown here.</p>
      </div>
      <Suspense fallback={<div className="h-80 animate-pulse rounded-3xl bg-white" aria-busy="true" />}>
        <UsersContent searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function UsersContent({ searchParams }: { searchParams: PageProps<"/users">["searchParams"] }) {
  const sp = await searchParams;
  const q = typeof sp.q === "string" ? sp.q.slice(0, 100) : "";
  const page = Math.max(1, Number(typeof sp.page === "string" ? sp.page : "1") || 1);
  const params = new URLSearchParams({ page: String(page), pageSize: "20", ...(q ? { q } : {}) });
  const [admin, data] = await Promise.all([
    requireAdmin(),
    backendGet<{ users: AdminUser[]; total: number; page: number; pageSize: number }>(`/api/admin/users?${params}`),
  ]);
  return <UsersTable key={`${q}-${page}`} {...data} query={q} currentAdminId={admin.id} />;
}
