import { CalendarClock, FileUp, Loader2, Play } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { runSchedulerNow, uploadLeads } from "../lib/api";

export default function BulkUpload() {
  const [status, setStatus] = useState("");
  const [uploadResult, setUploadResult] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  async function handleFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    try {
      const result = await uploadLeads(file);
      setUploadResult(result);
      setStatus(`${result.count || 0} leads queued for enrichment.`);
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  }

  async function handleRunNow() {
    setIsRunning(true);
    try {
      await runSchedulerNow();
      setStatus(`${uploadResult?.count || 0} queued leads sent to the pipeline.`);
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    } finally {
      setIsRunning(false);
    }
  }

  function handleScheduleLater() {
    navigate("/settings#scheduler-section");
  }

  return (
    <div className="panel p-4">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded bg-steel/12 text-steel">
          {isUploading ? <Loader2 size={17} className="animate-spin" /> : <UploadIcon />}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">Bulk import</p>
          <p className="mt-1 text-sm leading-5 text-ink/55">Upload a CSV of prospects for batch enrichment.</p>
          <label className="focus-ring mt-3 inline-flex cursor-pointer items-center gap-2 rounded border border-ink/10 bg-white px-3 py-2 text-sm font-medium text-ink/70 hover:text-ink">
            <FileUp size={16} aria-hidden="true" />
            Choose CSV
            <input className="sr-only" type="file" accept=".csv,text/csv" onChange={handleFile} />
          </label>
          {status ? <p className="mt-3 text-xs leading-5 text-spruce">{status}</p> : null}
          {uploadResult?.accepted && (
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                className="focus-ring inline-flex items-center gap-2 rounded bg-spruce px-3 py-2 text-sm font-semibold text-white hover:bg-moss disabled:opacity-60"
                disabled={isRunning}
                onClick={handleRunNow}
                type="button"
              >
                {isRunning ? (
                  <Loader2 size={15} className="animate-spin" aria-hidden="true" />
                ) : (
                  <Play size={15} aria-hidden="true" />
                )}
                {isRunning ? "Starting..." : "Run now"}
              </button>
              <button
                className="focus-ring inline-flex items-center gap-2 rounded border border-spruce/30 bg-spruce/8 px-3 py-2 text-sm font-semibold text-spruce hover:bg-spruce/15"
                onClick={handleScheduleLater}
                type="button"
              >
                <CalendarClock size={15} aria-hidden="true" />
                Schedule for later
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function UploadIcon() {
  return <FileUp size={17} aria-hidden="true" />;
}
