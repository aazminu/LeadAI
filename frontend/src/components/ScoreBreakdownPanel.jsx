import { ArrowUpRight, CheckCircle2, Zap } from "lucide-react";
import InfoTooltip from "./InfoTooltip";

function getEvidenceBullets(breakdown) {
  if (!breakdown) return [];
  const bullets = [];
  for (const key of [
    "pain_evidence",
    "fit_evidence",
    "timing_evidence",
    "market_evidence",
    "contact_evidence",
  ]) {
    const arr = breakdown[key];
    if (Array.isArray(arr)) bullets.push(...arr);
  }
  return bullets.filter(Boolean).slice(0, 8);
}

export default function ScoreBreakdownPanel({ lead }) {
  const enrichment = lead?.enrichment || {};
  const breakdown = enrichment.score_breakdown || null;
  const evidenceBullets = getEvidenceBullets(breakdown);

  if (!enrichment.score && !enrichment.pitch_angle && !evidenceBullets.length) {
    return null;
  }

  return (
    <section className="panel p-5">
      <p className="label mb-4">Score breakdown</p>

      <div className="grid gap-4 lg:grid-cols-[1fr_3fr]">
        {/* Left: Pitch angle + Fit summary stacked */}
        <div className="flex flex-col gap-3">
          <div className="rounded border border-ink/35 bg-white p-4">
            <Zap size={18} className="text-spruce" aria-hidden="true" />
            <div className="mt-3 flex items-center gap-1.5">
            <p className="label">Pitch angle</p>
            <InfoTooltip text="The framing angle used to position EliseAI" />
          </div>
            <p className="mt-2 text-sm leading-6 text-ink/68">
              {enrichment.pitch_angle || "Pending outreach signal"}
            </p>
          </div>
          <div className="rounded border border-ink/35 bg-white p-4">
            <ArrowUpRight size={18} className="text-marigold" aria-hidden="true" />
            <div className="mt-3 flex items-center gap-1.5">
            <p className="label">Fit summary</p>
            <InfoTooltip text="Overall assessment of how well this lead matches our ICP" />
          </div>
            <p className="mt-2 text-sm leading-6 text-ink/68">
              {enrichment.tier
                ? `${enrichment.tier} lead based on enriched market and company signals.`
                : "Score and tier pending."}
            </p>
          </div>
        </div>

        {/* Right: Why this score scrollable */}
        <div>
          <p className="label mb-3">Why this score</p>
          {evidenceBullets.length > 0 ? (
            <div className="max-h-[300px] overflow-y-auto space-y-2 pr-1">
              {evidenceBullets.map((bullet, i) => (
                <div key={i} className="flex gap-3 rounded bg-paper/70 p-3">
                  <CheckCircle2
                    size={17}
                    className="mt-0.5 shrink-0 text-spruce"
                    aria-hidden="true"
                  />
                  <p className="text-sm leading-6 text-ink/70">{bullet}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-ink/45">Evidence will appear after scoring completes.</p>
          )}
        </div>
      </div>
    </section>
  );
}
