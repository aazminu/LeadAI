import AgentPipeline from "../components/AgentPipeline";
import ValuesPanel from "../components/ValuesPanel";

export default function LeadDetail({ lead }) {
  return (
    <div className="space-y-5">
      <AgentPipeline lead={lead} />
      <ValuesPanel lead={lead} />
    </div>
  );
}
