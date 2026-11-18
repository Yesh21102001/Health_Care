import type { Metadata } from "next";
import { Suspense } from "react";
import { ShieldCheck } from "lucide-react";
import { AdminLogo } from "@/components/admin/logo";
import { AdminLoginForm } from "@/components/admin/login-form";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <main className="flex flex-1 items-center justify-center px-4 py-16">
      <div className="w-full max-w-md">
        <AdminLogo />
        <div className="mt-8 rounded-3xl border border-slate-200 bg-white p-8 shadow-card">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Admin sign in</h1>
          <p className="mt-2 flex items-center gap-2 text-sm text-slate-600">
            <ShieldCheck className="size-4 text-brand-700" aria-hidden="true" />
            Restricted to HealthAI administrators.
          </p>
          <div className="mt-6">
            <Suspense fallback={null}>
              <AdminLoginForm />
            </Suspense>
          </div>
        </div>
      </div>
    </main>
  );
}
