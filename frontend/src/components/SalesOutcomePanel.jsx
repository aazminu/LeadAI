import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowUpRight, BarChart2, Building2, HelpCircle, Loader2, Mail, MapPin, Target, Workflow } from "lucide-react";
import ScoreBadge from "./ScoreBadge";
import StatusBadge from "./StatusBadge";

const SCORE_DIMS = [
  { key: "pain",    label: "Pain",    max: 30 },
  { key: "fit",     label: "Fit",     max: 25 },
  { key: "timing",  label: "Timing",  max: 25 },
  { key: "market",  label: "Market",  max: 10 },
  { key: "contact", label: "Contact", max: 10 },
];

function ScoreBar({ label, score, max }) {
  const pct = Math.min(Math.round(((score || 0) / max) * 100), 100);
  return (
    <div className="flex items-center gap-3">
      <span className="w-14 shrink-0 text-xs text-white/60">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-white/20">
        <div
          className="h-1.5 rounded-full bg-white transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-10 shrink-0 text-right text-xs font-medium tabular-nums text-white/80">
        {score ?? "—"}/{max}
      </span>
    </div>
  );
}


function scrollToScoreBreakdown() {
  document.getElementById("score-breakdown-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function scrollToInsights() {
  document.getElementById("sales-insights-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function scrollToPipeline() {
  document.getElementById("pipeline-codex-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

const AGENT_LABELS = {
  research:   "Research agent",
  market:     "Market agent",
  scoring:    "Scoring agent",
  outreach:   "Outreach agent",
  identity:   "Identity agent",
  properties: "Properties agent",
};

function ScoreFormulaTooltip() {
  const navigate = useNavigate();
  const [hovered, setHovered] = useState(false);
  return (
    <div className="relative inline-flex">
      <button
        className="flex items-center justify-center text-white/80 hover:text-white transition-colors"
        onClick={() => navigate("/scoring")}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        type="button"
        aria-label="Learn more about scoring methodology"
      >
        <HelpCircle size={14} />
      </button>
      {hovered && (
        <div className="absolute left-1/2 top-full mt-2 -translate-x-1/2 whitespace-nowrap rounded bg-graphite/90 px-2.5 py-1.5 text-xs text-white shadow-lg">
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 border-4 border-transparent border-b-graphite/90" />
          Click to learn more about scoring
        </div>
      )}
    </div>
  );
}

export default function SalesOutcomePanel({ lead, isStreaming = false, steps = [] }) {
  const enrichment = lead?.enrichment || {};
  const breakdown = enrichment.score_breakdown || null;
  const score = Math.round(enrichment.score || 0);
  const isQueued = lead?.status === "queued" || lead?.status === "pending";
  const showInsightsButton = !!(enrichment.insights || enrichment.recommended_action);

  const currentAgent = steps.length
    ? AGENT_LABELS[steps[steps.length - 1]?.agent] || steps[steps.length - 1]?.agent
    : null;

  const logRef = useRef(null);
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [steps.length]);

  return (
    <section className="panel overflow-hidden">
      <div className="grid lg:grid-cols-[280px_1fr]">
        {/* Score sidebar */}
        <div className="bg-gradient-to-br from-spruce to-moss p-5 text-white">
          <div className="flex items-center gap-1.5">
            <p className="text-[11px] font-semibold uppercase tracking-normal text-white/90">
              Lead score
            </p>
            <ScoreFormulaTooltip />
          </div>
          <div className="mt-4 flex items-end gap-3">
            <span className="text-7xl font-semibold leading-none tracking-normal">
              {score || "--"}
            </span>
            <div className="pb-2">
              <ScoreBadge  tier={enrichment.tier} />
            </div>
          </div>

          {breakdown ? (
            <div className="mt-5 space-y-2.5">
              {SCORE_DIMS.map((dim) => (
                <ScoreBar
                  key={dim.key}
                  label={dim.label}
                  score={breakdown[`${dim.key}_score`]}
                  max={dim.max}
                />
              ))}
            </div>
          ) : (
            <p className="mt-4 text-sm leading-6 text-white/70">
              {lead?.company
                ? `${lead.company} scored on fit, market pressure, and outreach readiness.`
                : "Select a lead to see score and tier."}
            </p>
          )}
        </div>

        {/* Recommended action */}
        <div className="p-5">
          <div className="grid items-start gap-4 sm:grid-cols-[minmax(0,1fr)_auto]">
            <div className="min-w-0 pr-2">
              <p className="label text-spruce">
                {isStreaming ? "Enriching lead" : "Recommended next action"}
              </p>
              <h2 className="mt-2 text-2xl font-semibold tracking-normal text-graphite">
                {lead?.name || "Lead"}{!isStreaming && lead?.company ? ` at ${lead.company}` : ""}
              </h2>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                {lead?.company && (
                  <span className="flex items-center gap-1.5 text-sm text-ink/55">
                    <Building2 size={13} className="shrink-0" />
                    {lead.company}
                  </span>
                )}
                {lead?.email && (
                  <span className="flex items-center gap-1.5 text-sm text-ink/55">
                    <Mail size={13} className="shrink-0" />
                    {lead.email}
                  </span>
                )}
                {(lead?.city || lead?.state) && (
                  <span className="flex items-center gap-1.5 text-sm text-ink/55">
                    <MapPin size={13} className="shrink-0" />
                    {[lead.city, lead.state].filter(Boolean).join(", ")}
                  </span>
                )}
              </div>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1.5">
              {lead?.id && (
                <Link
                  className="focus-ring inline-flex items-center gap-2 rounded border border-spruce/30 bg-spruce/8 px-3 py-2 text-sm font-semibold text-spruce hover:bg-spruce/15"
                  to={`/leads/${lead.id}/outputs`}
                >
                  Full output
                  <ArrowUpRight size={16} aria-hidden="true" />
                </Link>
              )}
              <StatusBadge status={lead?.status} />
              {isStreaming && currentAgent && (
                <span className="flex items-center gap-1.5 text-xs text-spruce">
                  <Loader2 size={11} className="animate-spin" />
                  {currentAgent}
                </span>
              )}
            </div>
          </div>

          {isQueued && (
            <div className="mt-5 rounded border border-spruce/20 bg-spruce/8 p-4 text-sm leading-6 text-spruce">
              This lead is queued. It will run after the current pipeline finishes.
            </div>
          )}

          {isStreaming && steps.length > 0 ? (
            <div className="mt-5 rounded border border-spruce/20 bg-spruce/5 p-4">
              <p className="label mb-3 text-spruce">Enrichment in progress</p>
              <div
                ref={logRef}
                className="h-[112px] overflow-y-hidden space-y-2"
                style={{ scrollBehavior: "smooth" }}
              >
                {steps.map((s, i) => {
                  const isLatest = i === steps.length - 1;
                  return (
                    <div
                      key={i}
                      className={`flex items-start gap-2 text-sm transition-opacity duration-500 ${isLatest ? "opacity-100" : "opacity-35"}`}
                    >
                      <span className="mt-0.5 shrink-0 text-base leading-none">{s.icon || "·"}</span>
                      <div className="min-w-0">
                        <span className="text-ink/80">{s.message}</span>
                        {s.detail && <span className="ml-1.5 text-ink/40">{s.detail}</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="mt-5 rounded border border-steel/15 bg-frost/70 p-4">
              <div className="flex gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded bg-white text-spruce">
                  <Target size={18} aria-hidden="true" />
                </div>
                <p className="text-sm leading-6 text-ink/75">
                  {enrichment.recommended_action ||
                    "Run enrichment to generate the SDR next step."}
                </p>
              </div>
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            {isStreaming && (
              <button
                className="flex items-center gap-2 rounded bg-spruce px-4 py-2.5 text-sm font-semibold text-white hover:bg-moss"
                onClick={scrollToPipeline}
                type="button"
              >
                <Workflow size={15} aria-hidden="true" />
                View enrichment pipeline
              </button>
            )}
            {showInsightsButton && (
              <>
                <button
                  className="flex items-center gap-2 rounded border border-spruce/30 bg-spruce/8 px-4 py-2.5 text-sm font-semibold text-spruce hover:bg-spruce/15"
                  onClick={scrollToScoreBreakdown}
                  type="button"
                >
                  <BarChart2 size={15} aria-hidden="true" />
                  Score breakdown
                </button>
                <button
                  className="flex items-center gap-2 rounded border border-spruce/30 bg-spruce/8 px-4 py-2.5 text-sm font-semibold text-spruce hover:bg-spruce/15"
                  onClick={scrollToInsights}
                  type="button"
                >
                  <BarChart2 size={15} aria-hidden="true" />
                  Sales insights
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
