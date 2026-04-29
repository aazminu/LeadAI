import { useState } from "react";
import { HelpCircle } from "lucide-react";

export default function InfoTooltip({ text }) {
  const [hovered, setHovered] = useState(false);
  return (
    <div className="relative inline-flex">
      <button
        className="flex items-center justify-center text-ink/60 hover:text-graphite transition-colors"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        type="button"
        aria-label={text}
      >
        <HelpCircle size={13} />
      </button>
      {hovered && (
        <div className="absolute bottom-full left-1/2 mb-2 -translate-x-1/2 z-50 w-48 rounded bg-graphite px-2.5 py-1.5 text-xs text-white shadow-lg text-center line-clamp-2">
          <div className="absolute left-1/2 top-full -translate-x-1/2 border-4 border-transparent border-t-graphite/90" />
          {text}
        </div>
      )}
    </div>
  );
}
