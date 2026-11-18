"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { FormAlert, SubmitButton, TextField } from "@/components/admin/form-controls";
import { apiRequest } from "@/lib/api-client";

type Me = { user: { role: "user" | "admin" } };

export function AdminLoginForm() {
  const router = useRouter();
  const denied = useSearchParams().get("denied") === "1";
  const [error, setError] = useState<string | null>(denied ? "That account doesn't have admin access." : null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const fd = new FormData(e.currentTarget);
    const email = String(fd.get("email") ?? "").trim();
    const password = String(fd.get("password") ?? "");
    if (!email || !password) {
      setError("Enter your email and password.");
      return;
    }
    setPending(true);
    const login = await apiRequest<Me>("POST", "/api/auth/login", { email, password });
    if (!login.ok) {
      setPending(false);
      setError(login.error);
      return;
    }
    if (login.data.user.role !== "admin") {
      // Don't leave a non-admin signed in to the console.
      await apiRequest("POST", "/api/auth/logout", {});
      setPending(false);
      setError("That account doesn't have admin access.");
      return;
    }
    router.replace("/");
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-5">
      {error && <FormAlert>{error}</FormAlert>}
      <TextField label="Email" name="email" type="email" autoComplete="email" required />
      <TextField label="Password" name="password" type="password" autoComplete="current-password" required />
      <SubmitButton pending={pending}>{pending ? "Signing in…" : "Sign in"}</SubmitButton>
    </form>
  );
}
