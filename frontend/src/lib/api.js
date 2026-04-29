import { demoLeads, makeDemoLead } from "./demoData";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const useMocks = import.meta.env.VITE_USE_MOCKS === "true";

let mockLeads = [...demoLeads];

async function request(path, options = {}) {
  if (useMocks) {
    throw new Error("Mock mode enabled");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

function fallbackLeads() {
  return new Promise((resolve) => {
    window.setTimeout(() => resolve([...mockLeads]), 180);
  });
}

export async function getLeads() {
  try {
    const data = await request("/api/leads");
    return Array.isArray(data) ? data : data.leads || [];
  } catch {
    return fallbackLeads();
  }
}

export async function getLead(id) {
  try {
    return await request(`/api/leads/${id}`);
  } catch {
    return mockLeads.find((lead) => lead.id === id) || mockLeads[0];
  }
}

export async function regenerateEmail(leadId, feedback) {
  return request(`/api/leads/${leadId}/regenerate-email`, {
    method: "POST",
    body: JSON.stringify({ feedback }),
  });
}

export async function createLead(payload) {
  try {
    return await request("/api/leads", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  } catch {
    const lead = makeDemoLead(payload);
    mockLeads = [lead, ...mockLeads];
    return lead;
  }
}

export async function uploadLeads(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_BASE_URL}/api/leads/batch`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  } catch {
    return {
      accepted: true,
      count: 0,
      batch_id: `demo-batch-${Date.now()}`,
      message: "Upload accepted locally. Backend route is not available yet.",
    };
  }
}

export async function getSchedulerStatus() {
  try {
    return await request("/api/scheduler");
  } catch {
    return {
      enabled: true,
      next_run: "09:00 local",
      queue_depth: mockLeads.filter((lead) => lead.status !== "complete").length,
    };
  }
}

export async function toggleScheduler(enabled) {
  return request("/api/scheduler/toggle", {
    method: "POST",
    body: JSON.stringify({ enabled }),
  });
}

export async function updateSchedulerSchedule(payload) {
  return request("/api/scheduler/schedule", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function runSchedulerNow() {
  return request("/api/scheduler/run-now", { method: "POST" });
}

// Backend emits named SSE events — onmessage only catches unnamed events,
// so we register a listener for every known event type.
const SSE_EVENT_TYPES = [
  "queued",
  "pipeline_started",
  "step",
  "agent_complete",
  "pipeline_complete",
  "pipeline_failed",
  "pipeline_requeued",
  "pipeline_retry_scheduled",
  "done",
];

export function streamLead(leadId, onEvent, onDone, onError) {
  if (typeof EventSource === "undefined") {
    onError(new Error("EventSource not supported in this environment"));
    return () => {};
  }

  const url = `${API_BASE_URL}/api/leads/${leadId}/stream`;
  const eventSource = new EventSource(url);
  let finished = false;

  function handleRawEvent(e) {
    if (finished) return;
    try {
      const parsed = JSON.parse(e.data);
      onEvent(parsed);
      if (parsed.event === "done") {
        finished = true;
        eventSource.close();
        onDone();
      }
    } catch (err) {
      finished = true;
      eventSource.close();
      onError(err);
    }
  }

  for (const type of SSE_EVENT_TYPES) {
    eventSource.addEventListener(type, handleRawEvent);
  }

  eventSource.onerror = () => {
    if (!finished) {
      finished = true;
      eventSource.close();
      onError(new Error("SSE connection error"));
    }
  };

  return () => {
    finished = true;
    eventSource.close();
  };
}
