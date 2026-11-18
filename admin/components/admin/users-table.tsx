"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { ChevronLeft, ChevronRight, Search, ShieldCheck } from "lucide-react";
import { FormAlert } from "@/components/admin/form-controls";
import { Button } from "@/components/ui/button";
import { apiRequest } from "@/lib/api-client";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

export type AdminUser = {
  id: string;
  name: string;
  email: string;
  role: "user" | "admin";
  createdAt: string;
  conversationCount: number;
};

type Props = { users: AdminUser[]; total: number; page: number; pageSize: number; query: string; currentAdminId: string };

export function UsersTable({ users: initial, total, page, pageSize, query, currentAdminId }: Props) {
  const router = useRouter();
  const [users, setUsers] = useState(initial);
  const [q, setQ] = useState(query);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const pages = Math.max(1, Math.ceil(total / pageSize));

  function go(nextPage: number, nextQ = q) {
    const params = new URLSearchParams();
    if (nextQ.trim()) params.set("q", nextQ.trim());
    if (nextPage > 1) params.set("page", String(nextPage));
    router.push(`/users${params.size ? `?${params}` : ""}`);
  }

  function onSearch(e: FormEvent) {
    e.preventDefault();
    go(1);
  }

  async function toggleRole(u: AdminUser) {
    const role = u.role === "admin" ? "user" : "admin";
    const verb = role === "admin" ? "Grant admin access to" : "Remove admin access from";
    if (!window.confirm(`${verb} ${u.email}? This action is recorded in the audit log.`)) return;
    setBusyId(u.id);
    setMessage(null);
    const res = await apiRequest<{ user: AdminUser }>("PATCH", `/api/admin/users/${u.id}`, { role });
    setBusyId(null);
    if (!res.ok) return setMessage({ tone: "error", text: res.error });
    setUsers((all) => all.map((x) => (x.id === u.id ? { ...x, role } : x)));
    setMessage({ tone: "success", text: `${u.email} is now ${role === "admin" ? "an admin" : "a regular user"}.` });
  }

  return (
    <div className="space-y-4">
      <form onSubmit={onSearch} role="search" className="flex gap-2 sm:max-w-md">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
          <label htmlFor="user-search" className="sr-only">
            Search by name or email
          </label>
          <input
            id="user-search"
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by name or email"
            className="h-10 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-3 text-sm focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-100"
          />
        </div>
        <Button type="submit" variant="secondary">
          Search
        </Button>
      </form>

      {message && <FormAlert tone={message.tone}>{message.text}</FormAlert>}

      <div className="overflow-x-auto rounded-3xl border border-slate-200 bg-white shadow-card">
        <table className="w-full min-w-[640px] text-left text-sm">
          <caption className="sr-only">Registered users</caption>
          <thead className="border-b border-slate-100 text-xs uppercase tracking-wider text-slate-500">
            <tr>
              <th scope="col" className="px-5 py-3 font-medium">User</th>
              <th scope="col" className="px-5 py-3 font-medium">Role</th>
              <th scope="col" className="px-5 py-3 font-medium">Joined</th>
              <th scope="col" className="px-5 py-3 text-right font-medium">Conversations</th>
              <th scope="col" className="px-5 py-3 text-right font-medium">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {users.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-5 py-12 text-center text-slate-500">
                  {query ? `No users match “${query}”.` : "No users yet."}
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id}>
                  <td className="px-5 py-3">
                    <p className="font-medium text-slate-900">{u.name}</p>
                    <p className="text-slate-500">{u.email}</p>
                  </td>
                  <td className="px-5 py-3">
                    <span
                      className={cn(
                        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium",
                        u.role === "admin" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700",
                      )}
                    >
                      {u.role === "admin" && <ShieldCheck className="size-3.5" aria-hidden="true" />}
                      {u.role === "admin" ? "Admin" : "User"}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-slate-600">{formatDate(u.createdAt)}</td>
                  <td className="px-5 py-3 text-right tabular-nums text-slate-900">{u.conversationCount}</td>
                  <td className="px-5 py-3 text-right">
                    {u.id !== currentAdminId && (
                      <Button variant="ghost" onClick={() => toggleRole(u)} disabled={busyId === u.id}>
                        {u.role === "admin" ? "Remove admin" : "Make admin"}
                      </Button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-slate-600">
        <span>
          {total} user{total === 1 ? "" : "s"} · page {page} of {pages}
        </span>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => go(page - 1)} disabled={page <= 1} aria-label="Previous page">
            <ChevronLeft className="size-4" aria-hidden="true" />
          </Button>
          <Button variant="secondary" onClick={() => go(page + 1)} disabled={page >= pages} aria-label="Next page">
            <ChevronRight className="size-4" aria-hidden="true" />
          </Button>
        </div>
      </div>
    </div>
  );
}
