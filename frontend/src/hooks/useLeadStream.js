import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { streamLead } from "../lib/api";

export function useLeadStream(leadId) {
  const [steps, setSteps] = useState([]);
  const [streamEnrichment, setStreamEnrichment] = useState({});
  const [isStreaming, setIsStreaming] = useState(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!leadId) return;

    setSteps([]);
    setStreamEnrichment({});
    setIsStreaming(true);

    const cleanup = streamLead(
      leadId,
      (event) => {
        if (event.event === "step") {
          setSteps((prev) => [...prev, event]);
        } else if (event.event === "agent_complete") {
          setStreamEnrichment((prev) => ({
            ...prev,
            [`${event.agent}_complete`]: true,
          }));
        } else if (event.event === "pipeline_complete") {
          const p = event.payload || {};
          setStreamEnrichment((prev) => ({
            ...prev,
            score: p.score,
            tier: p.tier,
            email_draft: p.email_draft,
            email_subject: p.email_subject,
          }));
        }
      },
      () => {
        setIsStreaming(false);
        queryClient.invalidateQueries({ queryKey: ["leads"] });
      },
      (err) => {
        console.error("SSE error:", err);
        setIsStreaming(false);
        queryClient.invalidateQueries({ queryKey: ["leads"] });
      },
    );

    return cleanup;
  }, [leadId, queryClient]);

  return { steps, streamEnrichment, isStreaming };
}
