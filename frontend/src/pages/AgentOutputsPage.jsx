import { ArrowLeft, CheckCircle2, CircleDashed } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { getLead } from "../lib/api";

const OUTPUTS = [
  { key: "identity_data", label: "Identity agent", completeKey: "identity_complete" },
  { key: "company_data", label: "Company agent", completeKey: "company_complete" },
  { key: "market_data", label: "Market agent", completeKey: "market_complete" },
  { key: "property_data", label: "Property agent", completeKey: "property_complete" },
  { key: "values_data", label: "Values agent", completeKey: "values_complete" },
  { key: "score_breakdown", label: "Scoring breakdown", completeKey: "scoring_complete" },
  { key: "insights", label: "Sales insights", completeKey: "scoring_complete" },
  { key: "email_draft", label: "Outreach email", completeKey: "outreach_complete" },
  { key: "talking_points", label: "Outreach talking points", completeKey: "outreach_complete" },
];

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "No output saved yet.";
  }
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

function OutputCard({ item, enrichment }) {
  const complete = Boolean(enrichment?.[item.completeKey]);
  const value = enrichment?.[item.key];

  return (
    <section className="rounded border border-steel/15 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-graphite">{item.label}</p>
          <p className="mt-0.5 font-mono text-xs text-ink/42">{item.key}</p>
        </div>
        <span
          className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-semibold ${
            complete
              ? "bg-spruce/8 text-spruce"
              : "bg-steel/10 text-ink/45"
          }`}
        >
          {complete ? <CheckCircle2 size={13} /> : <CircleDashed size={13} />}
          {complete ? "Complete" : "Pending"}
        </span>
      </div>
      <pre className="max-h-[360px] overflow-auto rounded bg-paper/70 p-4 font-mono text-xs leading-5 text-ink/72">
        {formatValue(value)}
      </pre>
    </section>
  );
}

export default function AgentOutputsPage() {
  const { leadId } = useParams();
  const { data: lead, isLoading, error } = useQuery({
    queryKey: ["lead", leadId],
    queryFn: () => getLead(leadId),
    enabled: Boolean(leadId),
  });

  const enrichment = lead?.enrichment || {};

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link
            className="mb-4 inline-flex items-center gap-1.5 text-sm font-semibold text-spruce hover:text-moss"
            to="/"
          >
            <ArrowLeft size={15} aria-hidden="true" />
            Back to dashboard
          </Link>
          <p className="label text-spruce">Agent outputs</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-normal text-graphite">
            {lead?.company || "Lead"} research output
          </h1>
          <p className="mt-1 text-sm leading-6 text-ink/55">
            Stored principal output from each enrichment, scoring, and outreach stage.
          </p>
        </div>
        {lead?.status && (
          <div className="rounded border border-steel/15 bg-white px-3 py-2 font-mono text-sm text-ink/55">
            {lead.status}
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="panel p-6 text-sm text-ink/55">Loading agent outputs...</div>
      ) : error ? (
        <div className="panel p-6 text-sm text-coral">Unable to load this lead.</div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {OUTPUTS.map((item) => (
            <OutputCard key={item.key} item={item} enrichment={enrichment} />
          ))}
        </div>
      )}
    </main>
  );
}
