// Solid filled pill — represents quality judgment
const tierStyles = {
  hot:          "bg-emerald-600 text-white        border border-emerald-700",
  warm:         "bg-green-50    text-green-600   border border-green-300",
  nurture:      "bg-yellow-50   text-yellow-700  border border-yellow-300",
  low:          "bg-orange-50   text-orange-600  border border-orange-300",
  cold:         "bg-orange-50   text-orange-600  border border-orange-300",
  pass:         "bg-red-50      text-red-500     border border-red-300",
  disqualified: "bg-gray-50     text-gray-400    border border-gray-200",
};

export default function ScoreBadge({ score, tier }) {
  if (!score && !tier) {
    return (
      <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-1 text-xs font-semibold text-gray-400">
        Pending
      </span>
    );
  }

  const normalizedTier = tier || "pending";
  const styles = tierStyles[normalizedTier] || "bg-gray-200 text-gray-500";

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${styles}`}>
      {normalizedTier}
    </span>
  );
}
