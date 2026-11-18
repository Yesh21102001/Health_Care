import { Suspense } from "react";
import { AdminSidebar } from "@/components/admin/sidebar";
import { requireAdmin } from "@/lib/server-api";

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-1 flex-col lg:flex-row">
      <Suspense fallback={<div className="h-16 border-b border-slate-200 bg-white lg:h-auto lg:w-64 lg:border-r" aria-hidden="true" />}>
        <SidebarWithAdmin />
      </Suspense>
      <main id="main" className="min-w-0 flex-1">
        <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-10">{children}</div>
      </main>
    </div>
  );
}

async function SidebarWithAdmin() {
  const admin = await requireAdmin();
  return <AdminSidebar admin={admin} />;
}
