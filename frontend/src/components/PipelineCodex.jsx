import { memo, useEffect, useRef, useState, useMemo } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  getBezierPath,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Check, GitBranch, Layers, Loader2, Mail, Network, Search, ShieldX, Sparkles, X } from "lucide-react";

const AGENTS = [
  { id: "identity", label: "Identity", detail: "LinkedIn · email" },
  { id: "company",  label: "Company",  detail: "SEC · Exa · jobs" },
  { id: "market",   label: "Market",   detail: "Census · FRED · HUD" },
  { id: "property", label: "Property", detail: "WalkScore · v2" },
  { id: "values",   label: "Values",   detail: "ESG · tech · v2" },
];

// Spaced for the current 308px cards plus label rows, so the fan-out column never overlaps.
const agentY = { identity: -420, company: 0, market: 420, property: 840, values: 1260 };

function currentAgentFromSteps(steps = []) {
  return [...steps].reverse().find((s) => s.agent)?.agent;
}

function nodeStatus(id, enrichment, activeAgent, leadStatus, signalData = {}) {
  if (id === "orchestrator") return leadStatus && leadStatus !== "new" ? "complete" : "idle";
  if (id === "collector") return AGENTS.every((a) => enrichment?.[`${a.id}_complete`]) ? "complete" : "idle";
  if (id === "routing") {
    if (leadStatus === "disqualified") return "disqualified";
    const allAgentsComplete = AGENTS.every((a) => enrichment?.[`${a.id}_complete`]);
    if (
      allAgentsComplete &&
      signalData?.company_data?.is_residential === true &&
      signalData?.company_data?.is_real_estate === true
    ) return "qualified";
    if (allAgentsComplete) return "active";
    return "idle";
  }
  if (id === "scoring") {
    if (enrichment?.scoring_complete) return "complete";
    return activeAgent === "scoring" ? "active" : "idle";
  }
  if (id === "outreach") {
    if (enrichment?.outreach_complete) return "complete";
    return activeAgent === "outreach" ? "active" : "idle";
  }
  if (id === "end") return leadStatus === "complete" ? "complete" : "idle";
  if (id === "disqualified") return leadStatus === "disqualified" ? "complete" : "idle";
  const agent = AGENTS.find((a) => a.id === id);
  if (agent) {
    if (enrichment?.[`${id}_complete`]) return "complete";
    return activeAgent === id ? "active" : "idle";
  }
  return "idle";
}

function NodeHandles() {
  return (
    <>
      <Handle type="target" position={Position.Left}   className="!h-2 !w-2 !border-0 !bg-transparent" />
      <Handle type="source" position={Position.Right}  className="!h-2 !w-2 !border-0 !bg-transparent" />
      <Handle id="bottom" type="source" position={Position.Bottom} className="!h-2 !w-2 !border-0 !bg-transparent" />
      <Handle id="top"    type="target" position={Position.Top}    className="!h-2 !w-2 !border-0 !bg-transparent" />
    </>
  );
}

function StreamFeed({ steps, status, activeText, completeText, idleText }) {
  return (
    <div className="nodrag nowheel nopan relative -mx-0.5 mt-4 overflow-hidden rounded-lg border border-spruce/12 bg-white/45 p-3">
      <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-6 bg-gradient-to-b from-white/95 to-transparent" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 h-6 bg-gradient-to-t from-white/95 to-transparent" />
      <div
        className="nodrag nowheel nopan h-[188px] space-y-2 overflow-y-auto overscroll-contain py-1 pr-2"
        onPointerDownCapture={(event) => event.stopPropagation()}
        onWheelCapture={(event) => event.stopPropagation()}
        onTouchMoveCapture={(event) => event.stopPropagation()}
      >
        {steps?.length > 0 ? steps.map((step, i) => (
          <div key={i} className="flex items-start gap-2.5 rounded bg-paper/65 px-3 py-2">
            {step.icon && <span className="shrink-0 text-[22px] leading-7" aria-hidden="true">{step.icon}</span>}
            <div className="min-w-0 text-[22px] leading-7">
              <span className="text-ink/82">{step.message}</span>
              {step.detail && <span className="ml-1 text-ink/42">{step.detail}</span>}
            </div>
          </div>
        )) : (
          <p className="px-3 py-2 text-[22px] leading-7 text-ink/30">
            {status === "active" ? activeText : status === "complete" ? completeText : idleText}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Enrichment agent — AgentPipeline gradient theme ──────────────────
const AgentNode = memo(function AgentNode({ data }) {
  const Icon = data.icon;
  const s = data.status;
  return (
    <div className="flex w-[610px] flex-col">
      {/* Label row above box */}
      <div className="mb-2 flex items-center gap-2 px-1">
        <Icon size={18} className="text-spruce" aria-hidden="true" />
        <p className="text-4xl font-bold leading-none text-ink/70">{data.label}</p>
      </div>

      {/* Bordered box — matches AgentPipeline output cards */}
      <div
        className={`relative flex h-[328px] flex-col rounded-xl border-2 border-dashed bg-gradient-to-br from-white to-frost/70 px-7 py-6 transition-all ${
          s === "active"
            ? "border-spruce/60 shadow-[0_0_0_4px_rgba(116,55,245,0.06)]"
            : s === "complete"
            ? "border-spruce/45"
            : "border-spruce/38"
        }`}
      >
        <NodeHandles />
        {/* Status badge */}
        <div className="absolute right-3 top-3">
          <span className={`flex items-center gap-2 rounded bg-white px-5 py-2 text-2xl font-semibold ${
            s === "active" ? "text-marigold" : "text-spruce"
          }`}>
            {s === "active" && <Loader2 size={24} className="animate-spin shrink-0" aria-hidden="true" />}
            {s === "complete" && <Check size={24} className="shrink-0" aria-hidden="true" />}
            {s === "active" ? "Running" : s === "complete" ? "Done" : "Ready"}
          </span>
        </div>

        <p className="font-mono text-[22px] font-medium leading-6 text-spruce/60">{data.detail}</p>
        <StreamFeed
          steps={data.steps}
          status={s}
          activeText="Fetching signals..."
          completeText="Enrichment complete."
          idleText="Awaiting orchestrator."
        />
      </div>
    </div>
  );
});

// ── Orchestrator/control — gray, draw.io: 260×190 ────────────────────
const ControlNode = memo(function ControlNode({ data }) {
  const Icon = data.icon;
  const isComplete = data.status === "complete";
  return (
    <div
      className={`relative flex min-h-[220px] w-[270px] flex-col justify-center rounded-xl border-2 px-6 py-5 transition-all ${
        isComplete
          ? "border-pink-300 bg-gradient-to-br from-pink-50 via-white to-frost text-pink-700 shadow-[0_0_0_6px_rgba(244,114,182,0.10)]"
          : "border-pink-200 bg-gradient-to-br from-pink-50/70 via-white to-frost/40 text-pink-600"
      }`}
    >
      <NodeHandles />
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-ink/8">
          <Icon size={20} aria-hidden="true" />
        </div>
        <div>
          <p className="text-3xl font-semibold leading-5">{data.label}</p>
          <p className="mt-7  text-2xl leading-4 text-ink/55">{data.detail}</p>
        </div>
      </div>
    </div>
  );
});

// ── Collector — oval/circle with sweep animation on completion ────────
const CollectorNode = memo(function CollectorNode({ data }) {
  const Icon = data.icon;
  const [sweeping, setSweeping] = useState(false);
  const [hasSettled, setHasSettled] = useState(false);
  // always start from "idle" so the transition fires even if status is complete on mount
  const prevStatus = useRef("idle");

  useEffect(() => {
    if (data.status === "complete" && data.isRunning && prevStatus.current !== "complete") {
      prevStatus.current = "complete";
      setSweeping(true);
      const t = setTimeout(() => {
        setSweeping(false);
        setHasSettled(true);
      }, 1450);
      return () => clearTimeout(t);
    }
    if (data.status !== "complete") {
      prevStatus.current = data.status;
      setSweeping(false);
      setHasSettled(false);
    }
  }, [data.isRunning, data.status]);

  const settled = data.status === "complete" && hasSettled && !sweeping;

  return (
    <div
      className={`relative flex h-[210px] w-[210px] flex-col items-center justify-center border-[3px] transition-all duration-700 ${
        settled  ? "border-[#f59e0b] bg-[#fff7ed] text-[#b45309] shadow-[0_0_0_6px_rgba(245,158,11,0.16)]"
        : sweeping ? "border-gray-300 bg-gray-100 text-gray-500"
        : "border-gray-200 bg-gray-100 text-gray-400"
      }`}
      style={{ borderRadius: "50%" }}
    >
      <Handle type="target" position={Position.Left}  className="!h-2 !w-2 !border-0 !bg-transparent" />
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-0 !bg-transparent" />

      {/* Sweeping glow arc — 2 rotations then removed from DOM */}
      {sweeping && (
        <svg
          className="pointer-events-none absolute inset-0 animate-spin"
          style={{ animationDuration: "1.35s", animationTimingFunction: "linear", animationIterationCount: 1 }}
          viewBox="0 0 210 210"
          aria-hidden="true"
        >
          {/* Wide soft glow */}
          <circle cx="105" cy="105" r="101" fill="none"
            stroke="#f59e0b" strokeWidth="12"
            strokeDasharray="130 525" strokeLinecap="round"
            strokeOpacity="0.25"
          />
          {/* Sharp leading arc */}
          <circle cx="105" cy="105" r="101" fill="none"
            stroke="#f59e0b" strokeWidth="4"
            strokeDasharray="130 525" strokeLinecap="round"
          />
          <circle cx="105" cy="4" r="8" fill="#f59e0b" />
        </svg>
      )}

      <Icon size={24} aria-hidden="true" />
      <p className="mt-2 text-2xl font-semibold">{data.label}</p>
      <p className="mt-1 font-mono text-xl opacity-60">{data.detail}</p>
    </div>
  );
});

// ── Decision / routing — idle placeholder, then qualified (green) or disqualified (red) ──
const DecisionNode = memo(function DecisionNode({ data }) {
  const s   = data.status; // "idle" | "active" | "qualified" | "disqualified"
  const res = data.residential;
  const re  = data.realEstate;

  const isQualified    = s === "qualified" && data.isLiveSession && res === true && re === true;
  const isDisqualified = s === "disqualified";

  const iconColor   = isDisqualified ? "text-coral"     : isQualified ? "text-teal-500" : "text-ink/25";
  const labelColor  = isDisqualified ? "text-coral"     : isQualified ? "text-teal-600" : "text-ink/30";
  const detailColor = isDisqualified ? "text-coral/60"  : isQualified ? "text-teal-400" : "text-ink/25";
  const diamondClass = isDisqualified
    ? "border-coral/50 bg-coral/10"
    : isQualified
    ? "border-teal-400/60 bg-teal-50/70"
    : "border-steel/20 bg-gradient-to-br from-white to-frost/40";

  return (
    <div className="flex flex-col items-center">
      {/* Label above */}
      <div className="mb-3 flex items-center gap-2 px-1">
        <GitBranch size={18} className={iconColor} aria-hidden="true" />
        <div>
          <p className={`text-4xl font-bold ${labelColor}`}>{data.label}</p>
          <p className={`font-mono text-xl ${detailColor}`}>{data.detail}</p>
        </div>
      </div>

      {/* 280×280 transparent wrapper — handles sit at diamond points */}
      <div className="relative flex h-[280px] w-[280px] items-center justify-center">
        <NodeHandles />
        <div
          className={`flex h-[198px] w-[198px] items-center justify-center rounded-2xl border-[3px] transition-all ${diamondClass}`}
          style={{ transform: "rotate(45deg)" }}
        >
          <div style={{ transform: "rotate(-45deg)" }} className="flex flex-col items-center justify-center gap-3 px-2">
            {isQualified ? (
              <>
                <div className="flex items-center gap-2 font-mono text-2xl leading-6 text-teal-700">
                  <Check size={22} className="text-teal-500 shrink-0" aria-hidden="true" />
                  <span>residential</span>
                </div>
                <div className="flex items-center gap-2 font-mono text-2xl leading-6 text-teal-700">
                  <Check size={22} className="text-teal-500 shrink-0" aria-hidden="true" />
                  <span>real estate</span>
                </div>
              </>
            ) : isDisqualified ? (
              <>
                {res === false && (
                  <div className="flex items-center gap-2 font-mono text-xl leading-6 text-coral">
                    <X size={22} className="shrink-0" aria-hidden="true" />
                    <span>not residential</span>
                  </div>
                )}
                {re === false && (
                  <div className="flex items-center gap-2 font-mono text-xl leading-6 text-coral">
                    <X size={22} className="shrink-0" aria-hidden="true" />
                    <span>not real estate</span>
                  </div>
                )}
                {res !== false && re !== false && (
                  <div className="flex items-center gap-2 font-mono text-xl leading-6 text-coral">
                    <X size={22} className="shrink-0" aria-hidden="true" />
                    <span>disqualified</span>
                  </div>
                )}
              </>
            ) : (
              <div className="flex flex-col items-center gap-1 text-ink/25">
                <p className="font-mono text-xl">qualified /</p>
                <p className="font-mono text-xl">disqualified</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Label below — only shown once routing resolves */}
      {(isQualified || isDisqualified) && (
        <div className="mt-2 px-1">
          <p className={`text-2xl font-semibold ${isQualified ? "text-teal-600" : "text-coral"}`}>
            {isQualified ? "Qualified" : "Disqualified"}
          </p>
        </div>
      )}
    </div>
  );
});

// ── Sequential — scoring/outreach, AgentPipeline gradient theme ───────
const SequentialNode = memo(function SequentialNode({ data }) {
  const Icon = data.icon;
  const s = data.status;
  return (
    <div className="flex w-[450px] flex-col">
      {/* Label row above box */}
      <div className="mb-2 flex items-center gap-2 px-1">
        <Icon size={18} className="text-spruce" aria-hidden="true" />
        <p className="text-4xl font-bold leading-none text-ink/70">{data.label}</p>
      </div>
      {/* Bordered box — gradient theme, thicker/more intense border */}
      <div
        className={`relative flex h-[348px] flex-col rounded-xl border-[3px] bg-gradient-to-br from-white to-frost/70 px-8 py-6 transition-all ${
          s === "complete"
            ? "border-spruce/35"
            : s === "active"
            ? "border-spruce/55 shadow-[0_0_0_4px_rgba(116,55,245,0.05)]"
            : "border-spruce/42"
        }`}
      >
        <NodeHandles />
        {/* Status badge */}
        <div className="absolute right-4 top-4">
          <span className={`flex items-center gap-2 rounded bg-white px-5 py-2 text-2xl font-semibold ${
            s === "active" ? "text-marigold" : "text-spruce"
          }`}>
            {s === "active"   && <Loader2 size={24} className="animate-spin shrink-0" aria-hidden="true" />}
            {s === "complete" && <Check   size={24} className="shrink-0"             aria-hidden="true" />}
            {s === "active" ? "Running" : s === "complete" ? "Done" : "Ready"}
          </span>
        </div>
        <p className="font-mono text-[22px] leading-6 text-ink/50">{data.detail}</p>
        <StreamFeed
          steps={data.steps}
          status={s}
          activeText="Processing..."
          completeText="Complete."
          idleText="Waiting..."
        />
      </div>
    </div>
  );
});

// ── Danger — disqualified ─────────────────────────────────────────────
const DangerNode = memo(function DangerNode({ data }) {
  const isComplete = data.status === "complete";
  return (
    <div className="flex w-[280px] flex-col">
      {/* Bordered box */}
      <div
        className={`relative flex min-h-[160px] flex-col justify-center rounded-xl border-2 px-6 py-5 transition-all ${
          isComplete
            ? "border-coral/80 bg-gradient-to-br from-coral/15 to-coral/5 text-coral shadow-[0_0_0_6px_rgba(251,113,133,0.12)]"
            : "border-steel/18 bg-gradient-to-br from-white to-frost/45 text-ink/30 opacity-45"
        }`}
      >
        <NodeHandles />
        <div className="flex items-center gap-3">
          <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${isComplete ? "bg-coral/10" : "bg-steel/10"}`}>
            <ShieldX size={20} className={isComplete ? "text-coral" : "text-ink/30"} aria-hidden="true" />
          </div>
          <p className={`font-mono text-xl leading-6 ${isComplete ? "text-coral/75" : "text-ink/35"}`}>{data.detail}</p>
        </div>
      </div>
      {/* Label below box */}
      <div className="mt-2 flex items-center gap-2 px-1">
        <p className={`text-2xl font-semibold ${isComplete ? "text-coral" : "text-ink/25"}`}>
          {data.label}
        </p>
      </div>
    </div>
  );
});

// ── End — oval terminal, draw.io: 210×170 ─────────────────────────────
const EndNode = memo(function EndNode({ data }) {
  const isComplete = data.status === "complete" && data.isLiveSession;
  return (
    <div
      className={`relative flex h-[170px] w-[210px] flex-col items-center justify-center border-2 transition-all ${
        isComplete
          ? "border-teal-400 bg-teal-50 text-teal-600 shadow-[0_0_0_8px_rgba(45,212,191,0.1)]"
          : "border-steel/30 bg-white text-ink/40"
      }`}
      style={{ borderRadius: "50%" }}
    >
      <Handle type="target" position={Position.Left}  className="!h-2 !w-2 !border-0 !bg-transparent" />
      <Handle id="top" type="target" position={Position.Top} className="!h-2 !w-2 !border-0 !bg-transparent" />
      <Check size={isComplete ? 28 : 22} aria-hidden="true" />
      <p className="mt-2 font-mono text-xl font-semibold">{data.label}</p>
    </div>
  );
});

// ── Animated edge ─────────────────────────────────────────────────────
function AnimatedEdge(props) {
  const [edgePath, labelX, labelY] = getBezierPath({ ...props, curvature: 0.15 });
  const tone = props.data?.tone;
  const stroke   = tone === "danger" ? "#fda4af" : tone === "success" ? "#5eead4" : tone === "orange" ? "#f59e0b" : "#cfd5e8";
  const dotColor = tone === "success" ? "#2dd4bf" : tone === "danger" ? "#fb7185" : tone === "orange" ? "#f59e0b" : "#a78bfa";

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={props.markerEnd}
        style={{ stroke, strokeWidth: props.animated && tone === "success" ? 5 : props.animated ? 3.5 : 3 }}
      />
      {props.animated && (
        <circle r="4" fill={dotColor}>
          <animateMotion dur="1.35s" repeatCount="indefinite" path={edgePath} />
        </circle>
      )}
      {props.label && (
        <EdgeLabelRenderer>
          <div
            className="pointer-events-none absolute rounded bg-white/90 px-1.5 py-0.5 font-mono text-[11px] text-ink/55"
            style={{ transform: `translate(-50%,-50%) translate(${labelX}px,${labelY}px)` }}
          >
            {props.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const nodeTypes = {
  agentNode:      AgentNode,
  controlNode:    ControlNode,
  collectorNode:  CollectorNode,
  decisionNode:   DecisionNode,
  sequentialNode: SequentialNode,
  dangerNode:     DangerNode,
  endNode:        EndNode,
};
const edgeTypes = { animatedCodex: AnimatedEdge };

function nodeSteps(agentId, steps) {
  return steps.filter((s) => s.agent === agentId && s.message).slice(-5);
}

export default function PipelineCodex({ lead, steps = [], streamEnrichment = {}, isStreaming }) {
  const dbEnrichment = lead?.enrichment || {};
  const liveSession  = isStreaming || steps.length > 0 || Object.keys(streamEnrichment).length > 0;
  const enrichment   = liveSession ? streamEnrichment : {};
  const signalData   = { ...dbEnrichment, ...streamEnrichment };
  const activeAgent  = currentAgentFromSteps(steps);
  const leadStatus   = lead?.status;
  const running      = isStreaming || leadStatus === "processing";
  const company      = lead?.company || signalData?.identity_data?.company || "Lead";

  const nodes = useMemo(() => {
    const res = signalData?.company_data?.is_residential;
    const re  = signalData?.company_data?.is_real_estate;

    const mk = (id, type, position, extra) => ({
      id,
      type,
      position,
      data: { ...extra, status: nodeStatus(id, enrichment, activeAgent, leadStatus, signalData) },
      draggable: false,
    });

    return [
      mk("orchestrator", "controlNode",   { x: -70,   y: 517 }, { label: "Orchestrator", detail: "lead submitted",    icon: Network }),
      ...AGENTS.map((a) =>
        mk(a.id, "agentNode", { x: 360, y: agentY[a.id] }, {
          label: a.label,
          detail: a.detail,
          icon: Search,
          steps: nodeSteps(a.id, steps),
        })
      ),
      mk("collector",    "collectorNode", { x: 1180,  y: 524 }, { label: "Collector",    detail: "fan-in",            icon: Layers, isRunning: running }),
      mk("routing",      "decisionNode",  { x: 1500, y: 409 }, { label: "Routing", detail: "fit gate", residential: res, realEstate: re, isLiveSession: liveSession }),
      mk("scoring",  "sequentialNode", { x: 1870, y: 411 }, { label: "Scoring",  detail: "0–100 · evidence", icon: Sparkles, steps: nodeSteps("scoring",  steps) }),
      mk("outreach", "sequentialNode", { x: 2400, y: 411 }, { label: "Outreach", detail: "signal → email",   icon: Mail,     steps: nodeSteps("outreach", steps) }),
      mk("end",          "endNode",       { x: 2520, y: 850 }, { label: "End", isLiveSession: liveSession }),
      mk("disqualified", "dangerNode",    { x: 1500, y: 850 }, { label: "Disqualified", detail: "not residential" }),
    ];
  }, [activeAgent, enrichment, leadStatus, liveSession, running, signalData, steps]);

  const edges = useMemo(() => {
    const allAgentsComplete = AGENTS.every((a) => enrichment?.[`${a.id}_complete`]);
    const isDisqualified = leadStatus === "disqualified";
    const fitPassed = allAgentsComplete && signalData?.company_data?.is_residential === true && signalData?.company_data?.is_real_estate === true && !isDisqualified;
    const arrowColor = (tone) =>
      tone === "success" ? "#5eead4" : tone === "danger" ? "#fda4af" : tone === "orange" ? "#f59e0b" : "#c0c7de";

    const edge = (id, source, target, opts = {}) => ({
      id,
      source,
      target,
      type: "animatedCodex",
      animated: Boolean(opts.active),
      markerEnd: { type: MarkerType.ArrowClosed, color: arrowColor(opts.data?.tone) },
      ...opts,
      data: opts.data || {},
    });

    return [
      ...AGENTS.map((a) => edge(`o-${a.id}`, "orchestrator", a.id, { active: running && !allAgentsComplete })),
      ...AGENTS.map((a) => edge(`${a.id}-c`,  a.id, "collector", { active: running && !allAgentsComplete })),
      edge("collector-routing",    "collector",    "routing",      {
        active: running && allAgentsComplete,
        data: { tone: allAgentsComplete ? "orange" : undefined },
      }),
      edge("routing-scoring",      "routing",      "scoring",      {
        label: fitPassed ? "yes" : "",
        active: running && fitPassed && !enrichment?.scoring_complete,
        data: { tone: fitPassed ? "success" : undefined },
      }),
      edge("routing-disqualified", "routing",      "disqualified", {
        label: isDisqualified ? "no" : "",
        sourceHandle: "bottom",
        targetHandle: "top",
        active: running && isDisqualified,
        data: { tone: isDisqualified ? "danger" : undefined },
      }),
      edge("scoring-outreach",     "scoring",      "outreach",     {
        active: running && enrichment?.scoring_complete,
        data: { tone: enrichment?.scoring_complete ? "success" : undefined },
      }),
      edge("outreach-end",         "outreach",     "end",          {
        sourceHandle: "bottom",
        targetHandle: "top",
        active: running && enrichment?.outreach_complete,
        data: { tone: enrichment?.outreach_complete ? "success" : undefined },
      }),
    ];
  }, [enrichment, leadStatus, running, signalData]);

  const completeCount = AGENTS.filter((a) => enrichment[`${a.id}_complete`]).length;

  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-4 p-5">
        <div>
          <h2 className="text-xl font-semibold tracking-normal text-graphite">
            {company} research pipeline run
          </h2>

          <p className="mt-1 text-sm leading-6 text-ink/55">
            Live map of how a lead fans out through enrichment, gates through scoring, and exits with outreach or disqualification.
          </p>
        </div>
        <div className="flex items-center gap-3">
          
        </div>
      </div>

      <div className="h-[800px]">
        <ReactFlow
          key={lead?.id ?? "empty"}
          style={{ background: "white" }}
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          fitViewOptions={{ padding: 0.03 }}
          minZoom={0.2}
          maxZoom={1.2}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag={false}
          panOnScroll={false}
          zoomOnScroll={false}
          zoomOnPinch={false}
          zoomOnDoubleClick={false}
          preventScrolling={false}
          proOptions={{ hideAttribution: true }}
        />
      </div>

      <div className="flex flex-wrap justify-center gap-6 px-5 py-3.5">
        <LegendItem color="bg-pink-300" label="Orchestrator" />
        <LegendItem color="bg-spruce/55" label="Parallel research agents" />
        <LegendItem color="bg-[#f59e0b]" label="Outputs collected" />
        <LegendItem color="bg-teal-400" label="Qualified path" />
        <LegendItem color="bg-coral/60" label="Disqualified path" />
        <LegendItem color="bg-ink/25" label="Idle / waiting" />
      </div>
    </section>
  );
}

function LegendItem({ color, label }) {
  return (
    <div className="flex items-center gap-2 font-mono text-xs text-ink/55">
      <span className={`h-4 w-4 rounded-full ${color}`} />
      {label}
    </div>
  );
}
