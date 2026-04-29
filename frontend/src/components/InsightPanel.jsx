import { CheckCircle2 } from "lucide-react";

export default function InsightPanel({ insights = [] }) {
  const items = Array.isArray(insights) ? insights : Object.values(insights || {});

  return (
    <div className="mt-5">
      <p className="label">Agent insights</p>
      <div className="mt-3 grid gap-2">
        {items.length ? (
          items.map((insight, index) => (
            <div key={`${insight}-${index}`} className="flex gap-3 rounded bg-paper/70 p-3">
              <CheckCircle2 size={17} className="mt-0.5 shrink-0 text-spruce" aria-hidden="true" />
              <p className="text-sm leading-6 text-ink/70">{insight}</p>
            </div>
          ))
        ) : (
          <div className="rounded border border-dashed border-ink/15 bg-paper/70 p-4 text-sm text-ink/55">
            Insights will appear as the enrichment agents finish.
          </div>
        )}
      </div>
    </div>
  );
}
