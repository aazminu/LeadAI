import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, BarChart3, Clock3, Database } from "lucide-react";
import BulkUpload from "../components/BulkUpload";
import LeadCard from "../components/LeadCard";
import LeadForm from "../components/LeadForm";
import EmailDraft from "../components/EmailDraft";
import PipelineCodex from "../components/PipelineCodex";
import SalesInsightsPanel from "../components/SalesInsightsPanel";
import SalesOutcomePanel from "../components/SalesOutcomePanel";
import ScoreBreakdownPanel from "../components/ScoreBreakdownPanel";
import { useLeadPolling } from "../hooks/useLeadPolling";
import { useLeadStream } from "../hooks/useLeadStream";
import { useScheduler } from "../hooks/useScheduler";
import { regenerateEmail } from "../lib/api";

function MetricTile({ icon: Icon, label, value, detail }) {
  return (
    <div className="panel p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="label">{label}</p>
          <p className="mt-2 text-2xl font-semibold tracking-normal">{value}</p>
        </div>
        <div className="flex h-9 w-9 items-center justify-center rounded bg-moss/12 text-moss">
          <Icon size={18} aria-hidden="true" />
        </div>
      </div>
      <p className="mt-3 text-sm text-ink/60">{detail}</p>
    </div>
  );
}

function QueueSummary({ leads }) {
  const counts = leads.reduce(
    (acc, lead) => {
      const status = lead.status === "pending" ? "queued" : lead.status;
      if (status in acc) acc[status] += 1;
      return acc;
    },
    { processing: 0, queued: 0, complete: 0, disqualified: 0, failed: 0 },
  );

  return (
    <div className="mb-3 grid grid-cols-2 gap-2">
      {[
        ["Running",   counts.processing],
        ["Queued",    counts.queued],
        ["Complete",  counts.complete],
        ["Not valid", counts.disqualified],
      ].map(([label, value]) => (
        <div key={label} className="rounded border border-steel/15 bg-white px-3 py-2">
          <p className="text-[11px] font-semibold uppercase tracking-normal text-ink/45">
            {label}
          </p>
          <p className="mt-1 text-lg font-semibold text-graphite">{value}</p>
        </div>
      ))}
    </div>
  );
}

// processing → queued/pending → complete/disqualified/failed (most recent first within each group)
const STATUS_ORDER = { processing: 0, queued: 1, pending: 1, complete: 2, disqualified: 2, failed: 2 };

function sortLeads(leads) {
  return [...leads].sort((a, b) => {
    const diff = (STATUS_ORDER[a.status] ?? 3) - (STATUS_ORDER[b.status] ?? 3);
    if (diff !== 0) return diff;
    return new Date(b.created_at) - new Date(a.created_at);
  });
}

export default function Dashboard() {
  const queryClient = useQueryClient();
  const { leads, isLoading, createLead, isCreating } = useLeadPolling();
  const { scheduler } = useScheduler();
  const [streamLeadId, setStreamLeadId] = useState(null);
  const { steps, streamEnrichment, isStreaming } = useLeadStream(streamLeadId);

  const leadList = leads || [];
  const sortedLeads = sortLeads(leadList);
  const activeLead = leadList.find((l) => l.id === streamLeadId) || sortedLeads[0];
  const regenerateEmailMutation = useMutation({
    mutationFn: ({ leadId, feedback }) => regenerateEmail(leadId, feedback),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });

  async function handleSubmitLead(form) {
    const result = await createLead(form);
    const id = result?.lead_id || result?.id;
    if (id) setStreamLeadId(id);
  }

  const completed = leadList.filter((l) => l.status === "complete").length;
  const avgScore = Math.round(
    leadList.reduce((sum, l) => sum + (l.enrichment?.score || 0), 0) /
      Math.max(leadList.filter((l) => l.enrichment?.score).length, 1),
  );

  return (
    <main>
      {/* Hero + form */}
      <section className="border-b border-steel/15 bg-gradient-to-br from-white via-paper to-frost">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-8 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:px-8 lg:py-10">
          <div className="flex min-h-[520px] flex-col justify-between">
            <div>
              <p className="label text-spruce">EliseAI internal property intelligence</p>
              <h1 className="mt-4 max-w-3xl text-4xl font-semibold tracking-normal text-graphite sm:text-5xl lg:text-6xl">
                Turn inbound property leads into sales-ready outreach.
              </h1>
              <p className="mt-5 max-w-2xl text-lg leading-8 text-ink/68">
                Enrich each lead with public signals, score the opportunity,
                explain the reasoning, and draft the first SDR touch.
              </p>
            </div>
            <div className="mt-8 grid gap-3 sm:grid-cols-3">
              <MetricTile
                icon={Database}
                label="Leads tracked"
                value={isLoading ? "..." : leadList.length}
                detail="Live queue for enrichment"
              />
              <MetricTile
                icon={BarChart3}
                label="Avg score"
                value={avgScore || 0}
                detail={`${completed} completed profiles`}
              />
              <MetricTile
                icon={Clock3}
                label="Scheduler"
                value={scheduler?.enabled ? "On" : "Off"}
                detail={`Next run ${scheduler?.next_run || "pending"}`}
              />
            </div>
          </div>
          <LeadForm onSubmit={handleSubmitLead} isSubmitting={isCreating} />
        </div>
      </section>

      {/* Sidebar + top panels */}
      <section className="mx-auto grid max-w-7xl gap-5 px-2 py-6 sm:px-3 lg:grid-cols-[360px_1fr] lg:px-3">
        <aside className="space-y-5">
          <BulkUpload />
          <div>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-base font-semibold">Recent leads</h2>
              <button
                className="focus-ring flex items-center gap-1 rounded px-2 py-1 text-sm text-spruce"
                type="button"
              >
                View all <ArrowRight size={14} aria-hidden="true" />
              </button>
            </div>
            <QueueSummary leads={leadList} />
            <div className="max-h-[712px] overflow-y-auto space-y-3 pr-0.5">
              {sortedLeads.length === 0 && !isLoading && (
                <p className="rounded border border-dashed border-steel/25 p-4 text-sm text-ink/45">
                  No leads yet. Submit one above to get started.
                </p>
              )}
              {sortedLeads.map((lead) => (
                <LeadCard
                  key={lead.id}
                  lead={lead}
                  active={lead.id === activeLead?.id}
                  onClick={() => setStreamLeadId(lead.id)}
                />
              ))}
            </div>
          </div>
        </aside>

        <div className="space-y-5">
          <SalesOutcomePanel lead={activeLead} isStreaming={isStreaming} steps={steps} />
          <div id="email-draft-section" className="self-start">
            <EmailDraft
              to={activeLead?.email}
              subject={activeLead?.enrichment?.email_subject}
              draft={activeLead?.enrichment?.email_draft}
              points={activeLead?.enrichment?.talking_points || []}
              isRegenerating={regenerateEmailMutation.isPending}
              onRegenerate={
                activeLead?.id
                  ? (feedback) => regenerateEmailMutation.mutateAsync({ leadId: activeLead.id, feedback })
                  : null
              }
            />
          </div>
        </div>
      </section>

      {/* Full-width panels */}
      <div className="mx-auto max-w-7xl space-y-5 px-2 pb-10 sm:px-3 lg:px-3">
        <div id="score-breakdown-section">
          <ScoreBreakdownPanel lead={activeLead} />
        </div>
        <div id="sales-insights-section">
          <SalesInsightsPanel lead={activeLead} />
        </div>
        <div id="pipeline-codex-section">
          <PipelineCodex lead={activeLead} steps={steps} streamEnrichment={streamEnrichment} isStreaming={isStreaming} />
        </div>
      </div>
    </main>
  );
}
