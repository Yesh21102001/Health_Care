import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center px-4 py-24 text-center">
      <h1 className="text-2xl font-semibold text-slate-900">Page not found</h1>
      <Link href="/" className="mt-4 text-sm font-medium text-brand-700 underline">
        Back to overview
      </Link>
    </main>
  );
}
