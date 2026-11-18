/*
 * Small, dependency-free bar charts. Single series each, so one brand hue;
 * identity is carried by text labels, values are printed, every bar has a
 * hover tooltip (title), and a visually-hidden table gives the same data to
 * screen readers.
 */

type Datum = { label: string; value: number; detail?: string };

export function HorizontalBars({ data, caption }: { data: Datum[]; caption: string }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <figure>
      <ul className="space-y-3" aria-hidden="true">
        {data.map((d) => (
          <li key={d.label} className="grid grid-cols-[8.5rem_1fr_2.5rem] items-center gap-3 text-sm">
            <span className="truncate text-slate-600">{d.label}</span>
            <span className="h-3 rounded-r bg-slate-100" title={`${d.label}: ${d.value}`}>
              <span
                className="block h-3 rounded-r-[4px] bg-brand-600 transition-[width] duration-500"
                style={{ width: `${(d.value / max) * 100}%`, minWidth: d.value > 0 ? 4 : 0 }}
              />
            </span>
            <span className="text-right font-medium tabular-nums text-slate-900">{d.value}</span>
          </li>
        ))}
      </ul>
      <DataTable caption={caption} data={data} />
    </figure>
  );
}

export function ColumnChart({ data, caption, empty }: { data: Datum[]; caption: string; empty: string }) {
  if (data.length === 0) return <p className="py-10 text-center text-sm text-slate-500">{empty}</p>;
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <figure>
      <div className="flex h-40 items-end gap-0.5 border-b border-slate-200" aria-hidden="true">
        {data.map((d) => (
          <div key={d.label} className="group relative flex h-full flex-1 items-end" title={`${d.label}: ${d.value}${d.detail ? ` (${d.detail})` : ""}`}>
            <div
              className="w-full rounded-t-[4px] bg-brand-600 transition-colors group-hover:bg-brand-700"
              style={{ height: `${(d.value / max) * 100}%`, minHeight: d.value > 0 ? 4 : 0 }}
            />
            <span className="pointer-events-none absolute -top-7 left-1/2 hidden -translate-x-1/2 whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-xs text-white group-hover:block">
              {d.value}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-2 flex gap-0.5 text-[11px] text-slate-500" aria-hidden="true">
        {data.map((d) => (
          <span key={d.label} className="flex-1 truncate text-center">
            {d.label.slice(5)}
          </span>
        ))}
      </div>
      <DataTable caption={caption} data={data} />
    </figure>
  );
}

function DataTable({ caption, data }: { caption: string; data: Datum[] }) {
  return (
    <table className="sr-only">
      <caption>{caption}</caption>
      <tbody>
        {data.map((d) => (
          <tr key={d.label}>
            <th scope="row">{d.label}</th>
            <td>{d.value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
