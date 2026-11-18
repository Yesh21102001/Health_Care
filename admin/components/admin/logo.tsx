import Link from "next/link";
import { HeartPulse } from "lucide-react";

export function AdminLogo() {
  return (
    <Link href="/" className="inline-flex items-center gap-2" aria-label="HealthAI Admin home">
      <span className="flex size-9 items-center justify-center rounded-xl bg-slate-900 text-white shadow-sm">
        <HeartPulse className="size-5" aria-hidden="true" />
      </span>
      <span className="text-lg font-semibold tracking-tight text-slate-900">
        Health<span className="text-brand-700">AI</span>{" "}
        <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-600">Admin</span>
      </span>
    </Link>
  );
}
