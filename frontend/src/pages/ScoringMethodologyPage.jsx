const DIMENSIONS = [
  {
    key: "pain",
    label: "Pain",
    max: 30,
    color: "bg-red-500",
    description: "How severe is the operational pain the prospect faces today?",
    signals: [
      { name: "Active leasing hiring", detail: "2+ open leasing or maintenance roles indicates the team is stretched thin and responding manually to every inquiry." },
      { name: "Maintenance hiring pressure", detail: "Multiple maintenance roles suggest high ticket volume with no automation routing requests to the right person." },
      { name: "No automation tooling", detail: "If no PropTech is detected, the team is handling prospect communication entirely through email and phone." },
      { name: "High portfolio size", detail: "Large unit counts without proportional headcount means after-hours inquiries go unanswered, costing leases." },
    ],
    scoring: [
      { range: "25–30", label: "Critical pain", detail: "3+ leasing roles open, no automation, large portfolio" },
      { range: "15–24", label: "Moderate pain", detail: "1–2 hiring signals or clear manual ops" },
      { range: "5–14",  label: "Low pain",      detail: "Some tools in place, limited hiring" },
      { range: "0–4",   label: "No signal",     detail: "Fully automated or no evidence of pain" },
    ],
  },
  {
    key: "fit",
    label: "Fit",
    max: 25,
    color: "bg-emerald-500",
    description: "How closely does the prospect match EliseAI's ideal customer profile?",
    signals: [
      { name: "Residential focus", detail: "EliseAI is purpose-built for residential property management. Mixed-use or commercial operators score lower." },
      { name: "Unit count", detail: "50–5,000 units is the sweet spot. Too small = budget risk. Too large = enterprise complexity." },
      { name: "Native integrations", detail: "Yardi, Entrata, OneSite, or RealPage in the stack means a 30-day deployment with no rip-and-replace." },
      { name: "Company size", detail: "10–500 employee operators have budget authority and a clear decision-making structure." },
    ],
    scoring: [
      { range: "20–25", label: "Perfect ICP",    detail: "Residential, 200–2000 units, native integration detected" },
      { range: "12–19", label: "Strong fit",     detail: "Residential with partial integration match" },
      { range: "5–11",  label: "Partial fit",    detail: "Some ICP signals, gaps in size or stack" },
      { range: "0–4",   label: "Poor fit",       detail: "Commercial, micro-operator, or no stack signal" },
    ],
  },
  {
    key: "timing",
    label: "Timing",
    max: 25,
    color: "bg-blue-500",
    description: "How ready is the prospect to evaluate and buy right now?",
    signals: [
      { name: "Active expansion", detail: "Acquiring properties or entering new markets means new leasing capacity is needed immediately." },
      { name: "Tech gap with existing PropTech", detail: "Using Yardi or Entrata but missing leasing automation means they already believe in PropTech — just haven't found EliseAI yet." },
      { name: "Recent funding or growth event", detail: "Fundraises and major portfolio announcements signal budget availability and a window for new tooling decisions." },
      { name: "Lease-up phase", detail: "New construction in lease-up needs to fill units fast — automation directly drives revenue velocity." },
    ],
    scoring: [
      { range: "20–25", label: "Buy now",        detail: "Active expansion + tech gap + recent growth event" },
      { range: "12–19", label: "Near-term",      detail: "1–2 strong timing signals" },
      { range: "5–11",  label: "Possible",       detail: "Stable operator, moderate signals" },
      { range: "0–4",   label: "Not ready",      detail: "No timing indicators detected" },
    ],
  },
  {
    key: "market",
    label: "Market",
    max: 10,
    color: "bg-yellow-500",
    description: "How much does the local leasing market intensify the need for automation?",
    signals: [
      { name: "High leasing intensity city", detail: "Markets like Dallas, Austin, Phoenix, and Charlotte have prospects shopping 3–4 properties simultaneously. Response speed wins the lease." },
      { name: "Competitive vacancy", detail: "Sub-5% vacancy markets mean operators are managing high inbound volume without extra staff." },
      { name: "Seasonal surge", detail: "Spring/summer leasing seasons dramatically increase inquiry volume for unprepared teams." },
    ],
    scoring: [
      { range: "8–10", label: "High intensity",  detail: "Top-tier market, high leasing velocity" },
      { range: "5–7",  label: "Moderate",        detail: "Growing or competitive secondary market" },
      { range: "0–4",  label: "Low intensity",   detail: "Stable or low-velocity market" },
    ],
  },
  {
    key: "contact",
    label: "Contact",
    max: 10,
    color: "bg-purple-500",
    description: "How decision-ready is the specific contact identified?",
    signals: [
      { name: "Title match", detail: "VP of Operations, Director of Leasing, Regional Manager, or COO titles have direct budget authority for operational tooling." },
      { name: "Verified email", detail: "A confirmed, deliverable email address avoids bounces and signals the contact is active." },
      { name: "LinkedIn presence", detail: "An active LinkedIn profile confirms the contact is real, currently employed, and reachable for follow-up." },
      { name: "Decision-maker level", detail: "C-suite and Director+ contacts can approve deals. Manager-level contacts can champion but may need escalation." },
    ],
    scoring: [
      { range: "8–10", label: "Decision maker",  detail: "C-suite or Director+, verified email, active LinkedIn" },
      { range: "5–7",  label: "Influencer",      detail: "Manager-level with verified contact" },
      { range: "0–4",  label: "Weak contact",    detail: "Generic email, unverified title, or low seniority" },
    ],
  },
];

const TIERS = [
  { range: "85–100", tier: "Hot",          color: "bg-emerald-600 text-white",          action: "Contact within 24 hours. All signals aligned." },
  { range: "70–84",  tier: "Warm",         color: "bg-green-100 text-green-700 border border-green-300",         action: "Prioritize outreach this week. Strong ICP, minor gaps." },
  { range: "55–69",  tier: "Nurture",      color: "bg-yellow-100 text-yellow-700 border border-yellow-300",      action: "Add to nurture sequence. Re-score in 30 days." },
  { range: "40–54",  tier: "Low",          color: "bg-orange-100 text-orange-600 border border-orange-300",          action: "Low effort only. Check back on expansion signals." },
  { range: "0–39",   tier: "Pass / Cold",  color: "bg-red-50 text-red-500 border border-red-300",   action: "Disqualify or hold. No compelling signal today." },
];

import { useNavigate } from "react-router-dom";

export default function ScoringMethodologyPage() {
  const navigate = useNavigate();
  return (
    <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-8">
        <button
          className="mb-6 flex items-center gap-1.5 text-sm text-ink/55 hover:text-ink transition-colors"
          onClick={() => navigate(-1)}
          type="button"
        >
          ← Back
        </button>
        <h1 className="text-2xl font-semibold tracking-normal text-graphite">Lead Scoring Methodology</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-ink/60">
          Every lead is scored 0–100 across five weighted dimensions. The score reflects how urgently EliseAI
          should be in front of this operator — not just whether they're a fit, but whether now is the right moment.
        </p>
      </div>

      {/* Tier guide */}
      <div className="panel mb-8 p-6">
        <h2 className="mb-4 text-base font-semibold text-graphite">Score tiers</h2>
        <div className="divide-y divide-steel/10">
          {TIERS.map((t) => (
            <div key={t.tier} className="flex items-start gap-4 py-3 first:pt-0 last:pb-0">
              <div className="w-16 shrink-0 text-sm font-semibold tabular-nums text-ink/50">{t.range}</div>
              <span className={`inline-flex shrink-0 items-center rounded-full px-2.5 py-1 text-xs font-semibold ${t.color}`}>
                {t.tier}
              </span>
              <p className="text-sm text-ink/65">{t.action}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Dimension breakdowns */}
      <div className="space-y-6">
        {DIMENSIONS.map((dim) => (
          <div key={dim.key} className="panel overflow-hidden">
            <div className="flex items-center justify-between border-b border-steel/10 px-6 py-4">
              <div className="flex items-center gap-3">
                <div className={`h-2.5 w-2.5 rounded-full ${dim.color}`} />
                <h2 className="text-base font-semibold text-graphite">{dim.label}</h2>
              </div>
              <span className="text-sm font-semibold text-spruce">{dim.max} pts</span>
            </div>

            <div className="p-6">
              <p className="mb-5 text-sm leading-6 text-ink/65">{dim.description}</p>

              <div className="grid gap-6 sm:grid-cols-2">
                {/* Signals */}
                <div>
                  <p className="label mb-3">Signals evaluated</p>
                  <div className="space-y-3">
                    {dim.signals.map((s) => (
                      <div key={s.name} className="flex gap-3">
                        <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-spruce" />
                        <div>
                          <p className="text-sm font-semibold text-graphite">{s.name}</p>
                          <p className="mt-0.5 text-sm leading-5 text-ink/55">{s.detail}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Scoring bands */}
                <div>
                  <p className="label mb-3">Scoring bands</p>
                  <div className="space-y-2">
                    {dim.scoring.map((s) => (
                      <div key={s.range} className="rounded border border-steel/10 bg-paper/60 p-3">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-semibold text-graphite">{s.label}</span>
                          <span className="text-xs font-semibold tabular-nums text-spruce">{s.range} pts</span>
                        </div>
                        <p className="mt-1 text-xs text-ink/50">{s.detail}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
