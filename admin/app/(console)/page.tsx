import type { Metadata } from "next";
import { Suspense } from "react";
import { Activity, AlertTriangle, Bot, CheckCircle2, ClipboardList, Database, Lock, MessageSquare, Users, XCircle } from "lucide-react";
import { ColumnChart, HorizontalBars } from "@/components/admin/charts";
import { formatDateTime } from "@/lib/format";
import { backendGet } from "@/lib/server-api";

export const metadata: Metadata = { title: "Overview" };

type Dashboard = {
  totals: { users: number; newUsers7d: number; conversations: number; assessments: number; activeSessions: number };
  assessmentsByUrgency: Record<"self_monitoring" | "consultation" | "urgent" | "emergency", number>;
  conversationsByStatus: Record<"in_progress" | "completed" | "emergency_flagged", number>;
  recentActivity: { type: string; urgency: string | null; createdAt: string }[];
  system: { database: string; aiConfigured: boolean; model: string; environment: string };
  aiUsage: {
    requests7d: number;
    errors7d: number;
    inputTokens7d: number;
    outputTokens7d: number;
    avgLatencyMs: number;
    byDay: { date: string; requests: number; errors: number; tokens: number }[];
  };
};

const EVENT_LABELS: Record<string, string> = {
  "user.registered": "New user registered",
  "conversation.started": "Conversation started",
  "assessment.created": "Assessment generated",
  "emergency.flagged": "Emergency guidance given",
  "account.deleted": "Account deleted",
};

const URGENCY_LABELS: Record<string, string> = {
  self_monitoring: "Self-monitoring",
  consultation: "See a doctor",
  urgent: "Urgent",
  emergency: "Emergency",
};

const nf = new Intl.NumberFormat("en-IN");

export default function OverviewPage() {
  return (
    <Suspense fallback={<div className="h-96 animate-pulse rounded-3xl bg-white" aria-busy="true" />}>
      <Overview />
    </Suspense>
  );
}

async function Overview() {
  const d = await backendGet<Dashboard>("/api/admin/dashboard");
  const stats = [
    { label: "Registered users", value: d.totals.users, icon: Users, sub: `+${d.totals.newUsers7d} in 7 days` },
    { label: "Conversations", value: d.totals.conversations, icon: MessageSquare },
    { label: "Assessments", value: d.totals.assessments, icon: ClipboardList },
    { label: "Active sessions", value: d.totals.activeSessions, icon: Activity },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">Overview</h1>
        <p className="mt-1.5 flex items-center gap-2 text-sm text-slate-600">
          <Lock className="size-4" aria-hidden="true" />
          Aggregate statistics only. Individual health conversations are not visible to administrators.
        </p>
      </div>

      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <li key={s.label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card">
            <s.icon className="size-5 text-brand-700" aria-hidden="true" />
            <p className="mt-3 text-3xl font-semibold tabular-nums text-slate-900">{nf.format(s.value)}</p>
            <p className="text-sm text-slate-500">{s.label}</p>
            {s.sub && <p className="mt-1 text-xs text-slate-400">{s.sub}</p>}
          </li>
        ))}
      </ul>

      <div className="grid gap-6 lg:grid-cols-2">
        <section aria-labelledby="urgency-title" className="rounded-3xl border border-slate-200 bg-white p-6 shadow-card">
          <h2 id="urgency-title" className="font-semibold text-slate-900">
            Assessments by suggested level of care
          </h2>
          <p className="mt-1 text-xs text-slate-500">All time. Not a validated triage measure.</p>
          <div className="mt-6">
            <HorizontalBars
              caption="Assessments by suggested level of care"
              data={Object.entries(d.assessmentsByUrgency).map(([k, v]) => ({ label: URGENCY_LABELS[k] ?? k, value: v }))}
            />
          </div>
        </section>

        <section aria-labelledby="ai-title" className="rounded-3xl border border-slate-200 bg-white p-6 shadow-card">
          <h2 id="ai-title" className="font-semibold text-slate-900">
            AI requests per day
          </h2>
          <p className="mt-1 text-xs text-slate-500">Last 7 days · token counts only, no content is logged</p>
          <div className="mt-8">
            <ColumnChart
              caption="AI requests per day, last 7 days"
              empty="No AI requests in the last 7 days."
              data={d.aiUsage.byDay.map((r) => ({ label: r.date, value: r.requests, detail: `${r.errors} errors, ${nf.format(r.tokens)} tokens` }))}
            />
          </div>
          <dl className="mt-6 grid grid-cols-2 gap-4 border-t border-slate-100 pt-5 text-sm sm:grid-cols-4">
            {[
              ["Requests", nf.format(d.aiUsage.requests7d)],
              ["Errors", nf.format(d.aiUsage.errors7d)],
              ["Tokens in / out", `${nf.format(d.aiUsage.inputTokens7d)} / ${nf.format(d.aiUsage.outputTokens7d)}`],
              ["Avg latency", `${nf.format(d.aiUsage.avgLatencyMs)} ms`],
            ].map(([k, v]) => (
              <div key={k}>
                <dt className="text-xs text-slate-500">{k}</dt>
                <dd className="mt-0.5 font-medium tabular-nums text-slate-900">{v}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <section aria-labelledby="activity-title" className="rounded-3xl border border-slate-200 bg-white shadow-card">
          <h2 id="activity-title" className="border-b border-slate-100 px-6 py-4 font-semibold text-slate-900">
            Recent platform activity
          </h2>
          {d.recentActivity.length === 0 ? (
            <p className="px-6 py-10 text-center text-sm text-slate-500">No activity yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {d.recentActivity.map((e, i) => (
                <li key={i} className="flex items-center justify-between gap-4 px-6 py-3 text-sm">
                  <span className="text-slate-800">
                    {EVENT_LABELS[e.type] ?? e.type}
                    {e.urgency && <span className="text-slate-500"> · {URGENCY_LABELS[e.urgency] ?? e.urgency}</span>}
                  </span>
                  <time className="shrink-0 text-xs text-slate-400" dateTime={e.createdAt}>
                    {formatDateTime(e.createdAt)}
                  </time>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="system-title" className="rounded-3xl border border-slate-200 bg-white p-6 shadow-card">
          <h2 id="system-title" className="font-semibold text-slate-900">
            System health
          </h2>
          <ul className="mt-4 space-y-3 text-sm">
            <HealthRow icon={Database} label="Database" ok={d.system.database === "ok"} value={d.system.database === "ok" ? "Connected" : "Unreachable"} />
            <HealthRow icon={Bot} label="AI provider" ok={d.system.aiConfigured} value={d.system.aiConfigured ? d.system.model : "Not configured"} />
            <HealthRow
              icon={AlertTriangle}
              label="AI error rate (7d)"
              ok={d.aiUsage.requests7d === 0 || d.aiUsage.errors7d / d.aiUsage.requests7d < 0.05}
              value={d.aiUsage.requests7d ? `${((d.aiUsage.errors7d / d.aiUsage.requests7d) * 100).toFixed(1)}%` : "No traffic"}
            />
          </ul>
          <p className="mt-5 text-xs text-slate-400">Environment: {d.system.environment}</p>
        </section>
      </div>
    </div>
  );
}

function HealthRow({ icon: Icon, label, ok, value }: { icon: typeof Database; label: string; ok: boolean; value: string }) {
  const Status = ok ? CheckCircle2 : XCircle;
  return (
    <li className="flex items-center justify-between gap-3">
      <span className="flex items-center gap-2 text-slate-600">
        <Icon className="size-4" aria-hidden="true" />
        {label}
      </span>
      <span className={ok ? "flex items-center gap-1.5 font-medium text-emerald-700" : "flex items-center gap-1.5 font-medium text-red-700"}>
        <Status className="size-4" aria-hidden="true" />
        {value}
        <span className="sr-only">{ok ? "(healthy)" : "(problem)"}</span>
      </span>
    </li>
  );
}
