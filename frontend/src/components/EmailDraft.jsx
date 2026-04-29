import { useState } from "react";
import { Copy, HelpCircle, Loader2, Mail, RefreshCw, Send } from "lucide-react";
import { loadProfile } from "../pages/SettingsPage";

function buildSignature(profile) {
  const name  = profile.name  || "Your Name";
  const title = profile.title || "Sales Development Representative";
  const email = profile.email || "you@eliseai.com";
  return `\n\n--\nBest,\n${name}\n\n${title}, EliseAI\n${email}`;
}

// Strip any sign-off the LLM may have included before we append the real signature
function stripSignoff(draft) {
  if (!draft) return draft;
  return draft
    .replace(/\n+(?:best|regards|thanks|cheers|sincerely)[,.]?\s*\n?\[?your name\]?\s*$/i, "")
    .trimEnd();
}

function buildMailto(to, subject, draft, profile) {
  const body = (stripSignoff(draft) || "") + buildSignature(profile);
  return `mailto:${encodeURIComponent(to || "")}?subject=${encodeURIComponent(subject || "")}&body=${encodeURIComponent(body)}`;
}

function CallPromptsTooltip() {
  const [hovered, setHovered] = useState(false);
  return (
    <div className="relative inline-flex">
      <button
        className="flex items-center justify-center text-graphite hover:text-ink transition-colors"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        type="button"
        aria-label="What are call prompts?"
      >
        <HelpCircle size={13} />
      </button>
      {hovered && (
        <div className="absolute bottom-full left-1/2 mb-2 -translate-x-1/2 whitespace-nowrap rounded bg-graphite/90 px-2.5 py-1.5 text-xs text-white shadow-lg">
          <div className="absolute left-1/2 top-full -translate-x-1/2 border-4 border-transparent border-t-graphite/90" />
          Talking points for a follow-up phone call
        </div>
      )}
    </div>
  );
}

export default function EmailDraft({ to, subject, draft, points = [], onRegenerate, isRegenerating = false }) {
  const cleanDraft = stripSignoff(draft);

  function copyDraft() {
    if (!cleanDraft) return;
    const profile = loadProfile();
    navigator.clipboard.writeText(cleanDraft + buildSignature(profile));
  }

  function sendEmail() {
    const profile = loadProfile();
    window.location.href = buildMailto(to, subject, cleanDraft, profile);
  }

  function regenerateDraft() {
    if (!onRegenerate || !cleanDraft) return;
    const feedback = window.prompt(
      "What should change in the regenerated email?",
      "Make it shorter, sharper, and more specific to the strongest signal.",
    );
    if (feedback === null) return;
    onRegenerate(feedback.trim() || "Make it shorter, sharper, and more specific to the strongest signal.");
  }

  return (
    <section className="panel p-5">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <p className="label text-spruce">Draft outreach</p>
          <h2 className="mt-2 text-xl font-semibold tracking-normal text-graphite">
            Email and call prep
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="focus-ring flex h-9 items-center gap-2 rounded border border-spruce/30 bg-spruce/8 px-3 text-sm font-semibold text-spruce hover:bg-spruce/15 disabled:opacity-40"
            disabled={!cleanDraft || !onRegenerate || isRegenerating}
            onClick={regenerateDraft}
            title="Regenerate email"
            type="button"
          >
            {isRegenerating ? (
              <Loader2 size={15} className="animate-spin" aria-hidden="true" />
            ) : (
              <RefreshCw size={15} aria-hidden="true" />
            )}
            {isRegenerating ? "Regenerating" : "Regenerate"}
          </button>
          <button
            className="focus-ring flex h-9 w-9 items-center justify-center rounded border border-ink/10 bg-white text-ink/65 hover:text-ink disabled:opacity-40"
            disabled={!cleanDraft}
            onClick={copyDraft}
            title="Copy email with signature"
            type="button"
          >
            <Copy size={16} aria-hidden="true" />
          </button>
          <button
            className="focus-ring flex h-9 items-center gap-2 rounded bg-spruce px-3 text-sm font-semibold text-white hover:bg-moss disabled:opacity-40"
            disabled={!cleanDraft}
            onClick={sendEmail}
            title="Open in mail app"
            type="button"
          >
            <Send size={15} aria-hidden="true" />
            Send
          </button>
        </div>
      </div>

      <div className="grid items-start gap-5 lg:grid-cols-[2fr_1fr]">
        {/* Email preview */}
        <div className="rounded border border-ink/10 bg-paper/65 p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-graphite">
            <Mail size={16} className="shrink-0 text-spruce" aria-hidden="true" />
            {subject || "Email draft"}
          </div>
          <div className="max-h-[460px] overflow-y-auto pr-1">
            <p className="whitespace-pre-line text-sm leading-7 text-ink/68">
              {cleanDraft || "The outreach email will appear after scoring approves the lead."}
            </p>
            {cleanDraft && (
              <pre className="mt-4 whitespace-pre-wrap border-t border-ink/8 pt-4 font-sans text-xs leading-5 text-ink/40">
                {buildSignature(loadProfile()).trimStart()}
              </pre>
            )}
          </div>
        </div>

        {/* Call prompts */}
        <div>
          <div className="mb-3 flex items-center gap-1.5">
            <p className="label text-graphite">Call prompts</p>
            <CallPromptsTooltip />
          </div>
          <div className="space-y-2">
            {points.length ? (
              points.map((point, i) => (
                <div key={i} className="flex gap-3 rounded bg-paper/70 p-3">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-spruce" />
                  <p className="text-sm leading-6 text-ink/68">{point}</p>
                </div>
              ))
            ) : (
              <div className="rounded border border-dashed border-ink/15 p-4 text-sm text-ink/50">
                Talking points will appear after the outreach agent completes.
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
