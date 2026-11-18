import type { Metadata } from "next";
import { Suspense } from "react";
import { formatDateTime } from "@/lib/format";
import { backendGet } from "@/lib/server-api";

export const metadata: Metadata = { title: "Audit log" };

type Entry = { id: string; action: string; admin: string; target: string | null; details: Record<string, string>; createdAt: string };

export default function AuditPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">Audit log</h1>
        <p className="mt-1.5 text-sm text-slate-600">Every administrative change, newest first.</p>
      </div>
      <Suspense fallback={<div className="h-80 animate-pulse rounded-3xl bg-white" aria-busy="true" />}>
        <AuditContent />
      </Suspense>
    </div>
  );
}

async function AuditContent() {
  const { entries } = await backendGet<{ entries: Entry[] }>("/api/admin/audit");
  return (
    <div className="overflow-x-auto rounded-3xl border border-slate-200 bg-white shadow-card">
      <table className="w-full min-w-[640px] text-left text-sm">
        <caption className="sr-only">Administrative actions</caption>
        <thead className="border-b border-slate-100 text-xs uppercase tracking-wider text-slate-500">
          <tr>
            <th scope="col" className="px-5 py-3 font-medium">When</th>
            <th scope="col" className="px-5 py-3 font-medium">Admin</th>
            <th scope="col" className="px-5 py-3 font-medium">Action</th>
            <th scope="col" className="px-5 py-3 font-medium">Target</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {entries.length === 0 ? (
            <tr>
              <td colSpan={4} className="px-5 py-12 text-center text-slate-500">
                No admin actions recorded yet.
              </td>
            </tr>
          ) : (
            entries.map((e) => (
              <tr key={e.id}>
                <td className="whitespace-nowrap px-5 py-3 text-slate-600">{formatDateTime(e.createdAt)}</td>
                <td className="px-5 py-3 text-slate-900">{e.admin}</td>
                <td className="px-5 py-3 text-slate-900">
                  {e.action === "user.role_changed" ? `Role changed ${e.details.from ?? ""} → ${e.details.to ?? ""}` : e.action}
                </td>
                <td className="px-5 py-3 text-slate-600">{e.target ?? "—"}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
