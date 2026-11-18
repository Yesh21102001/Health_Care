"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { LayoutDashboard, LogOut, ScrollText, Users } from "lucide-react";
import { AdminLogo } from "@/components/admin/logo";
import { Button } from "@/components/ui/button";
import { apiRequest } from "@/lib/api-client";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/users", label: "Users", icon: Users },
  { href: "/audit", label: "Audit log", icon: ScrollText },
];

export function AdminSidebar({ admin }: { admin: { name: string; email: string } }) {
  const pathname = usePathname();
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function logout() {
    setPending(true);
    await apiRequest("POST", "/api/auth/logout", {});
    router.replace("/login");
    router.refresh();
  }

  return (
    <aside className="flex shrink-0 flex-col border-b border-slate-200 bg-white px-4 py-4 lg:min-h-screen lg:w-64 lg:border-b-0 lg:border-r lg:py-5">
      <div className="px-1">
        <AdminLogo />
      </div>
      <nav aria-label="Admin" className="mt-4 lg:mt-8 lg:flex-1">
        <ul className="flex gap-1 overflow-x-auto lg:flex-col">
          {nav.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-3 whitespace-nowrap rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                    active ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                  )}
                >
                  <item.icon className="size-4" aria-hidden="true" />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="mt-4 hidden border-t border-slate-100 pt-4 lg:block">
        <p className="truncate text-sm font-medium text-slate-900">{admin.name}</p>
        <p className="truncate text-xs text-slate-500">{admin.email}</p>
        <Button variant="secondary" onClick={logout} disabled={pending} className="mt-3 w-full">
          <LogOut className="size-4" aria-hidden="true" />
          Sign out
        </Button>
      </div>
    </aside>
  );
}
