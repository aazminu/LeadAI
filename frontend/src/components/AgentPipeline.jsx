import {
  BrainCircuit,
  Check,
  CircleDashed,
  CircleDot,
  FileText,
  Loader2,
  Mail,
  MapPinned,
  SearchCheck,
  Sparkles,
  X,
} from "lucide-react";

const AGENTS = [
  {
    name: "identity",
    key: "identity_complete",
    outputKey: "identity_data",
    label: "Identity",
    description: "Role and decision-maker probability",
    icon: SearchCheck,
  },
  {
    name: "company",
    key: "company_complete",
    outputKey: "company_data",
    label: "Company",
    description: "Residential fit and firmographics",
    icon: BrainCircuit,
  },
  {
    name: "market",
    key: "market_complete",
    outputKey: "market_data",
    label: "Market",
    description: "Economic and local demand signals",
    icon: MapPinned,
  },
  {
    name: "property",
    key: "property_complete",
    outputKey: "property_data",
    label: "Property",
    description: "Address and neighborhood context",
    icon: FileText,
  },
  {
    name: "values",
    key: "values_complete",
    outputKey: "values_data",
    label: "Values",
    description: "Mission, hiring, news, and tech signals",
    icon: Sparkles,
  },
  {
    name: "scoring",
    key: "scoring_complete",
    outputKey: "score_breakdown",
    label: "Scoring",
    description: "Fit tier and recommended action",
    icon: BrainCircuit,
  },
  {
    name: "outreach",
    key: "outreach_complete",
    outputKey: "email_draft",
    label: "Outreach",
    description: "Email draft and call talking points",
    icon: Mail,
  },
];

function AgentIcon({ complete, failed, active }) {
  if (failed) return <X size={16} className="text-coral" aria-hidden="true" />;
  if (complete) return <Check size={16} className="text-spruce" aria-hidden="true" />;
  if (active) return <CircleDot size={16} className="text-marigold" aria-hidden="true" />;
  return <CircleDashed size={16} className="text-ink/35" aria-hidden="true" />;
}

export default function AgentPipeline({
  lead,
  steps = [],
  streamEnrichment = {},
  isStreaming = false,
}) {
  const dbEnrichment = lead?.enrichment || {};
  const enrichment = { ...dbEnrichment, ...streamEnrichment };

  const completeCount = AGENTS.filter((a) => enrichment[a.key]).length;
  const progress = Math.round((completeCount / AGENTS.length) * 100);

  // Group SSE step events by agent name
  const stepsByAgent = {};
  for (const step of steps) {
    if (!stepsByAgent[step.agent]) stepsByAgent[step.agent] = [];
    stepsByAgent[step.agent].push(step);
  }

  return (
    <section className="panel p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="label">Agent pipeline</p>
          <h2 className="mt-2 text-xl font-semibold tracking-normal">
            {lead ? `${lead.company} research run` : "No lead selected"}
          </h2>
        </div>
        <div className="min-w-[140px]">
          <div className="flex justify-between text-xs font-medium text-ink/55">
            <span>{completeCount} of {AGENTS.length}</span>
            <span>{progress}%</span>
          </div>
          <div className="mt-2 h-2 rounded bg-spruce/10">
            <div
              className="h-2 rounded bg-spruce transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(220px,3fr)_minmax(0,7fr)]">
        {/* Agent status list */}
        <div className="space-y-2">
          {AGENTS.map((agent, index) => {
            const complete = Boolean(enrichment[agent.key]);
            const active = !complete && index === completeCount;
            return (
              <div
                key={agent.key}
                className="rounded border border-steel/15 bg-paper/55 p-3"
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-white">
                    <AgentIcon complete={complete} active={active} />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-graphite">{agent.label}</p>
                    <p className="mt-1 text-xs leading-5 text-ink/58">{agent.description}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Output cards with live step feed */}
        <div className="grid gap-4 sm:grid-cols-2">
          {AGENTS.map((agent) => {
            const Icon = agent.icon;
            const complete = Boolean(enrichment[agent.key]);
            const hasOutput = Boolean(enrichment[agent.outputKey]);
            const agentSteps = stepsByAgent[agent.name] || [];
            const running = isStreaming && !complete && agentSteps.length > 0;

            let badge = "Blank";
            let badgeClass = "text-ink/40";
            if (complete && hasOutput) {
              badge = "Ready";
              badgeClass = "text-spruce font-semibold";
            } else if (running) {
              badge = "Running";
              badgeClass = "text-marigold";
            } else if (complete) {
              badge = "Done";
              badgeClass = "text-ink/50";
            }

            return (
              <div
                key={agent.key + "-output"}
                className="min-h-[132px] rounded border border-dashed border-spruce/25 bg-gradient-to-br from-white to-frost/70 p-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 text-sm font-semibold text-ink/70">
                    <Icon size={17} className="text-spruce" aria-hidden="true" />
                    {agent.label} output
                  </div>
                  <span
                    className={`flex items-center gap-1 rounded bg-white px-2 py-1 text-xs ${badgeClass}`}
                  >
                    {running && (
                      <Loader2 size={11} className="animate-spin" aria-hidden="true" />
                    )}
                    {badge}
                  </span>
                </div>

                {agentSteps.length > 0 && (
                  <div className="mt-3 max-h-[80px] space-y-1.5 overflow-y-auto">
                    {agentSteps.map((step, i) => (
                      <div key={i} className="flex items-start gap-1.5">
                        <span className="shrink-0 text-xs leading-4" aria-hidden="true">
                          {step.icon}
                        </span>
                        <div className="min-w-0 text-xs leading-4">
                          <span className="text-graphite">{step.message}</span>
                          {step.detail && (
                            <span className="ml-1 text-ink/45">{step.detail}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
