// Outlined pill — represents pipeline process state
const statusStyles = {
  queued:       "bg-slate-100  text-slate-500  border border-slate-200",
  pending:      "bg-slate-100  text-slate-500  border border-slate-200",
  processing:   "bg-violet-50  text-violet-600 border border-violet-200",
  complete:     "bg-pantone text-white border border-pantone",
  disqualified: "bg-rose-50    text-rose-500   border border-rose-200",
  failed:       "bg-red-50     text-red-500    border border-red-200",
};

const statusLabel = {
  queued:       "Queued",
  pending:      "Queued",
  processing:   "Running",
  complete:     "Complete",
  disqualified: "Not valid",
  failed:       "Failed",
};

export default function StatusBadge({ status }) {
  const normalized = status || "queued";

  return (
    <span
      className={`inline-flex items-center rounded px-2 py-1 text-xs font-semibold ${
        statusStyles[normalized] || statusStyles.queued
      }`}
    >
      {statusLabel[normalized] || normalized}
    </span>
  );
}
