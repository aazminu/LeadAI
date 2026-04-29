import { Lightbulb, MessageSquareText, Target } from "lucide-react";
import EmailDraft from "./EmailDraft";
import InsightPanel from "./InsightPanel";
import ScoreBadge from "./ScoreBadge";

export default function ValuesPanel({ lead }) {
  const enrichment = lead?.enrichment || {};
  const talkingPoints = enrichment.talking_points || [];

  return (
    <section className="grid gap-5 xl:grid-cols-[1fr_360px]">
      <div className="panel p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="label">Qualification brief</p>
            <h2 className="mt-2 text-xl font-semibold tracking-normal">
              {lead?.name || "Lead"} at {lead?.company || "company"}
            </h2>
          </div>
          <ScoreBadge score={enrichment.score} tier={enrichment.tier} />
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-3">
          <div className="rounded border border-ink/10 bg-white p-4">
            <Target size={18} className="text-spruce" aria-hidden="true" />
            <p className="mt-3 label">Action</p>
            <p className="mt-2 text-sm leading-6 text-ink/68">
              {enrichment.recommended_action || "Run enrichment to generate the next action."}
            </p>
          </div>
          <div className="rounded border border-ink/10 bg-white p-4">
            <Lightbulb size={18} className="text-marigold" aria-hidden="true" />
            <p className="mt-3 label">Pitch angle</p>
            <p className="mt-2 text-sm leading-6 text-ink/68">
              {enrichment.pitch_angle || "Pending agent output"}
            </p>
          </div>
          <div className="rounded border border-ink/10 bg-white p-4">
            <MessageSquareText size={18} className="text-steel" aria-hidden="true" />
            <p className="mt-3 label">Talking points</p>
            <p className="mt-2 text-sm leading-6 text-ink/68">
              {talkingPoints.length ? `${talkingPoints.length} call prompts ready` : "Waiting for outreach agent"}
            </p>
          </div>
        </div>

        <InsightPanel insights={enrichment.insights} />
      </div>

      <EmailDraft draft={enrichment.email_draft} points={talkingPoints} />
    </section>
  );
}
