import { Mail, MapPin } from "lucide-react";
import ScoreBadge from "./ScoreBadge";
import StatusBadge from "./StatusBadge";

export default function LeadCard({ lead, active, onClick }) {
  return (
    <button
      className={`focus-ring w-full rounded border p-4 text-left transition hover:border-spruce/30 ${
        active ? "border-spruce bg-spruce/8 shadow-panel" : "border-ink/10 bg-white"
      }`}
      onClick={onClick}
      type="button"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">{lead.name}</p>
          <p className="mt-1 truncate text-sm text-ink/55">{lead.company}</p>
        </div>
        <ScoreBadge score={lead.enrichment?.score} tier={lead.enrichment?.tier} />
      </div>
      <div className="mt-3 flex items-center gap-2 text-xs text-ink/50">
        <MapPin size={14} aria-hidden="true" />
        <span className="truncate">
          {lead.city}, {lead.state}
        </span>
      </div>
      {lead.email && (
        <div className="mt-1.5 flex items-center gap-2 text-xs text-ink/50">
          <Mail size={14} aria-hidden="true" />
          <span className="truncate">{lead.email}</span>
        </div>
      )}
      <div className="mt-3 flex items-center justify-between">
        <StatusBadge status={lead.status} />
        <span className="text-xs text-ink/45">{lead.country || "US"}</span>
      </div>
    </button>
  );
}
