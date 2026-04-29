import { useEffect, useState } from "react";
import { Loader2, Play, Save, User } from "lucide-react";
import { getSchedulerStatus, runSchedulerNow, toggleScheduler, updateSchedulerSchedule } from "../lib/api";

const PROFILE_KEY = "leados_profile";

export function loadProfile() {
  try {
    return JSON.parse(localStorage.getItem(PROFILE_KEY)) || {};
  } catch {
    return {};
  }
}

function saveProfile(profile) {
  localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
}

function ProfileSection() {
  const [form, setForm] = useState({ name: "", title: "", email: "" });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const stored = loadProfile();
    if (stored.name || stored.title || stored.email) setForm(stored);
  }, []);

  function update(e) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
    setSaved(false);
  }

  function handleSave(e) {
    e.preventDefault();
    saveProfile(form);
    setSaved(true);
  }

  return (
    <div className="panel p-6">
      <div className="mb-5 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-spruce/10 text-spruce">
          <User size={20} aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-graphite">Your profile</h2>
          <p className="text-sm text-ink/55">Used in the email signature when sending outreach.</p>
        </div>
      </div>

      <form onSubmit={handleSave} className="grid gap-4 sm:grid-cols-2">
        <label className="block sm:col-span-2">
          <span className="label">Full name</span>
          <input
            className="mt-2 w-full rounded border border-ink/10 bg-white px-3 py-2.5 text-sm outline-none focus:border-spruce/60 focus:ring-2 focus:ring-spruce/15"
            name="name"
            onChange={update}
            placeholder="Maria Morin"
            value={form.name}
          />
        </label>

        <label className="block">
          <span className="label">Title</span>
          <input
            className="mt-2 w-full rounded border border-ink/10 bg-white px-3 py-2.5 text-sm outline-none focus:border-spruce/60 focus:ring-2 focus:ring-spruce/15"
            name="title"
            onChange={update}
            placeholder="Sales Development Representative"
            value={form.title}
          />
        </label>

        <label className="block">
          <span className="label">EliseAI email</span>
          <input
            className="mt-2 w-full rounded border border-ink/10 bg-white px-3 py-2.5 text-sm outline-none focus:border-spruce/60 focus:ring-2 focus:ring-spruce/15"
            name="email"
            onChange={update}
            placeholder="you@eliseai.com"
            type="email"
            value={form.email}
          />
        </label>

        <div className="sm:col-span-2">
          {(form.name || form.title || form.email) && (
            <div className="mb-4 rounded border border-steel/15 bg-paper/70 p-4">
              <p className="label mb-2">Signature preview</p>
              <pre className="whitespace-pre-wrap font-sans text-sm leading-6 text-ink/70">
                {`Best,\n${form.name || "Your Name"}\n\n${form.title || "Your Title"}, EliseAI\n${form.email || "you@eliseai.com"}`}
              </pre>
            </div>
          )}

          <button
            className="flex items-center gap-2 rounded bg-spruce px-4 py-2.5 text-sm font-semibold text-white hover:bg-moss disabled:opacity-60"
            type="submit"
          >
            <Save size={15} aria-hidden="true" />
            {saved ? "Saved!" : "Save profile"}
          </button>
        </div>
      </form>
    </div>
  );
}

function SchedulerSection() {
  const [status, setStatus] = useState(null);
  const [scheduleForm, setScheduleForm] = useState({ hour: 9, minute: 0 });
  const [isToggling, setIsToggling] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isSavingSchedule, setIsSavingSchedule] = useState(false);

  useEffect(() => {
    getSchedulerStatus().then((result) => {
      setStatus(result);
      setScheduleForm({
        hour: result.schedule?.hour ?? 9,
        minute: result.schedule?.minute ?? 0,
      });
    });
  }, []);

  async function handleToggle() {
    if (!status) return;
    setIsToggling(true);
    const result = await toggleScheduler(!status.enabled);
    setStatus((s) => ({ ...s, ...result }));
    setIsToggling(false);
  }

  async function handleRunNow() {
    setIsRunning(true);
    const result = await runSchedulerNow();
    setStatus((s) => ({ ...s, ...result }));
    setIsRunning(false);
  }

  async function handleSaveSchedule(e) {
    e.preventDefault();
    setIsSavingSchedule(true);
    const result = await updateSchedulerSchedule({
      hour: Number(scheduleForm.hour),
      minute: Number(scheduleForm.minute),
    });
    setStatus((s) => ({ ...s, ...result }));
    setIsSavingSchedule(false);
  }

  return (
    <div id="scheduler-section" className="panel p-6 scroll-mt-24">
      <div className="mb-5">
        <h2 className="text-base font-semibold text-graphite">Scheduler</h2>
        <p className="mt-1 text-sm text-ink/55">
          Automatically processes queued leads on a daily schedule.
        </p>
      </div>

      {!status ? (
        <div className="flex items-center gap-2 text-sm text-ink/50">
          <Loader2 size={15} className="animate-spin" /> Loading...
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded border border-steel/15 bg-white p-4">
            <div>
              <p className="text-sm font-semibold text-graphite">
                {status.enabled ? "Scheduler is on" : "Scheduler is off"}
              </p>
              <p className="mt-0.5 text-xs text-ink/50">
                {status.schedule?.next_run_display
                  ? `Next run: ${status.schedule.next_run_display}`
                  : "No scheduled run set"}
              </p>
            </div>
            <button
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
                status.enabled ? "bg-spruce" : "bg-steel/30"
              }`}
              disabled={isToggling}
              onClick={handleToggle}
              type="button"
              aria-label="Toggle scheduler"
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
                  status.enabled ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded border border-steel/15 bg-white p-4">
              <p className="label">Worker</p>
              <p className="mt-1 text-sm font-semibold text-graphite">
                {status.worker_running ? "Running" : "Idle"}
              </p>
            </div>
            <div className="rounded border border-steel/15 bg-white p-4">
              <p className="label">Max attempts</p>
              <p className="mt-1 text-sm font-semibold text-graphite">
                {status.max_pipeline_attempts ?? "—"}
              </p>
            </div>
            <div className="rounded border border-steel/15 bg-white p-4">
              <p className="label">Stall timeout</p>
              <p className="mt-1 text-sm font-semibold text-graphite">
                {status.stalled_after_minutes ? `${status.stalled_after_minutes} min` : "—"}
              </p>
            </div>
          </div>

          <form
            className="rounded border border-steel/15 bg-white p-4"
            onSubmit={handleSaveSchedule}
          >
            <div className="mb-3">
              <p className="text-sm font-semibold text-graphite">Scheduled run time</p>
              <p className="mt-0.5 text-xs text-ink/50">
                Uses backend scheduler timezone: America/New_York.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
              <label>
                <span className="label">Hour</span>
                <input
                  className="mt-2 w-full rounded border border-ink/10 bg-white px-3 py-2.5 text-sm outline-none focus:border-spruce/60 focus:ring-2 focus:ring-spruce/15"
                  max="23"
                  min="0"
                  onChange={(e) => setScheduleForm((f) => ({ ...f, hour: e.target.value }))}
                  type="number"
                  value={scheduleForm.hour}
                />
              </label>
              <label>
                <span className="label">Minute</span>
                <input
                  className="mt-2 w-full rounded border border-ink/10 bg-white px-3 py-2.5 text-sm outline-none focus:border-spruce/60 focus:ring-2 focus:ring-spruce/15"
                  max="59"
                  min="0"
                  onChange={(e) => setScheduleForm((f) => ({ ...f, minute: e.target.value }))}
                  type="number"
                  value={scheduleForm.minute}
                />
              </label>
              <button
                className="mt-6 flex items-center justify-center gap-2 rounded bg-spruce px-4 py-2.5 text-sm font-semibold text-white hover:bg-moss disabled:opacity-60"
                disabled={isSavingSchedule}
                type="submit"
              >
                {isSavingSchedule ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : <Save size={15} aria-hidden="true" />}
                Save time
              </button>
            </div>
          </form>

          <button
            className="flex items-center gap-2 rounded border border-spruce/30 bg-spruce/8 px-4 py-2.5 text-sm font-semibold text-spruce hover:bg-spruce/15 disabled:opacity-60"
            disabled={isRunning}
            onClick={handleRunNow}
            type="button"
          >
            {isRunning
              ? <Loader2 size={15} className="animate-spin" aria-hidden="true" />
              : <Play size={15} aria-hidden="true" />
            }
            {isRunning ? "Queuing leads…" : "Run pipeline now"}
          </button>
        </div>
      )}
    </div>
  );
}

export default function SettingsPage() {
  useEffect(() => {
    if (window.location.hash === "#scheduler-section") {
      window.setTimeout(() => {
        document.getElementById("scheduler-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 0);
    }
  }, []);

  return (
    <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-normal text-graphite">Settings</h1>
        <p className="mt-1 text-sm text-ink/55">Manage your profile and pipeline configuration.</p>
      </div>

      <div className="space-y-6">
        <ProfileSection />
        <SchedulerSection />
      </div>
    </main>
  );
}
