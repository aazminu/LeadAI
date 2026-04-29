import { useRef, useEffect, useState } from "react";
import { Building2, MapPinned, Newspaper, ShieldQuestion } from "lucide-react";
import InfoTooltip from "./InfoTooltip";

const TOP_CARDS = [
  {
    label: "Company fit",
    icon: Building2,
    tooltip: "Size, portfolio, and ICP alignment for this company",
    resolve: (insights) => {
      const snap = insights?.company_snapshot;
      if (Array.isArray(snap) && snap.length) return snap[0];
      if (typeof snap === "string") return snap;
      return null;
    },
  },
  {
    label: "Market context",
    icon: MapPinned,
    tooltip: "Local leasing market conditions affecting urgency",
    resolve: (insights) => {
      const ctx = insights?.market_context;
      return typeof ctx === "string" ? ctx : null;
    },
  },
  {
    label: "Timing signals",
    icon: Newspaper,
    tooltip: "Events that indicate they're ready to buy now",
    resolve: (insights) => {
      const sig = insights?.timing_signals;
      if (Array.isArray(sig) && sig.length) return sig[0];
      if (typeof sig === "string") return sig;
      return null;
    },
  },
  {
    label: "Objection prep",
    icon: ShieldQuestion,
    tooltip: "Top objection to expect on first contact",
    resolve: (insights) => {
      const prep = insights?.objection_prep;
      if (Array.isArray(prep) && prep.length) {
        const first = prep[0];
        return typeof first === "string" ? first : first?.objection ?? null;
      }
      return null;
    },
  },
];

export default function SalesInsightsPanel({ lead }) {
  const insights = lead?.enrichment?.insights || null;
  const painPoints = Array.isArray(insights?.pain_points) ? insights.pain_points : [];
  const integrationHook = typeof insights?.integration_hook === "string" ? insights.integration_hook : null;
  const objectionPrep = Array.isArray(insights?.objection_prep) ? insights.objection_prep : [];

  const hookColRef = useRef(null);
  const [hookHeight, setHookHeight] = useState(null);

  useEffect(() => {
    const measure = () => {
      if (hookColRef.current) setHookHeight(hookColRef.current.offsetHeight);
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [integrationHook]);

  return (
    <section className="panel p-5">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="label text-spruce">Sales insights</p>
          <h2 className="mt-2 text-xl font-semibold tracking-normal text-graphite">
            What the rep should know
          </h2>
        </div>
      </div>

      {/* 4-column top cards */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {TOP_CARDS.map(({ label, icon: Icon, tooltip, resolve }) => {
          const value = insights ? resolve(insights) : null;
          return (
            <div key={label} className="rounded border border-ink/35 bg-white p-4">
              <Icon size={18} className="text-spruce" aria-hidden="true" />
              <div className="mt-3 flex items-center gap-1.5">
                <p className="label">{label}</p>
                <InfoTooltip text={tooltip} />
              </div>
              <p className="mt-2 text-sm leading-6 text-ink/68">
                {value ?? "Pending enriched signal."}
              </p>
            </div>
          );
        })}
      </div>

      {/* Grouped insight sections */}
      {insights ? (
        <div className="mt-5 space-y-5">
          {/* Pain points + Integration hook side by side */}
          {(painPoints.length > 0 || integrationHook) && (
            <div className="grid items-start gap-5 lg:grid-cols-2">
              {painPoints.length > 0 && (
                <div
                  className="flex flex-col overflow-hidden"
                  style={hookHeight ? { height: hookHeight } : {}}
                >
                  <div className="mb-3 flex items-center gap-1.5">
                    <p className="label">Pain points</p>
                    <InfoTooltip text="Operational challenges this prospect faces today" />
                  </div>
                  <div className="flex-1 overflow-y-auto space-y-2 pr-2">
                    {painPoints.map((point, i) => (
                      <div key={i} className="flex gap-3 rounded bg-paper/70 p-3">
                        <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-spruce" />
                        <p className="text-sm leading-6 text-ink/70">{point}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {integrationHook && (
                <div ref={hookColRef}>
                  <div className="mb-3 flex items-center gap-1.5">
                    <p className="label">Integration hook</p>
                    <InfoTooltip text="How EliseAI fits into their existing tech stack" />
                  </div>
                  <div className="rounded border border-spruce/60 bg-spruce/5 p-4">
                    <p className="text-sm leading-6 text-ink/70">{integrationHook}</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Objections below, horizontal grid */}
          {objectionPrep.length > 0 && (
            <div>
              <div className="mb-3 flex items-center gap-1.5">
                <p className="label">Objections</p>
                <InfoTooltip text="Likely pushbacks and how to handle them" />
              </div>
              <div className={`grid gap-3 ${objectionPrep.length > 3 ? "auto-cols-[280px] grid-flow-col overflow-x-auto pb-1" : "grid-cols-3"}`}>
                {objectionPrep.map((item, i) => (
                  <div key={i} className="rounded border border-ink/35 bg-white p-4">
                    <p className="text-sm font-semibold text-graphite">
                      {typeof item === "string" ? item : item.objection}
                    </p>
                    {item?.response && (
                      <p className="mt-2 text-sm leading-6 text-slate-500">{item.response}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="mt-5 rounded border border-dashed border-steel/25 bg-paper/70 p-4 text-sm text-ink/55">
          Sales insights will populate as scoring and enrichment complete.
        </div>
      )}
    </section>
  );
}
