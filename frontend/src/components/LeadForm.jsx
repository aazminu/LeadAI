import { Building2, Loader2, MapPin, Send, UserRound } from "lucide-react";
import { useState } from "react";

const initialForm = {
  name: "",
  email: "",
  company: "",
  property_address: "",
  city: "",
  state: "",
  country: "US",
};

function Field({ label, icon: Icon, children }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      <div className="mt-2 flex items-center gap-2 rounded border border-ink/10 bg-white px-3 py-2.5 transition focus-within:border-spruce/60 focus-within:ring-2 focus-within:ring-spruce/15">
        <Icon size={17} className="shrink-0 text-ink/38" aria-hidden="true" />
        {children}
      </div>
    </label>
  );
}

export default function LeadForm({ onSubmit, isSubmitting }) {
  const [form, setForm] = useState(initialForm);

  function updateField(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    await onSubmit(form);
    setForm(initialForm);
  }

  return (
    <form className="panel p-5 sm:p-6" onSubmit={handleSubmit}>
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <p className="label">New lead</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-normal">Start enrichment</h2>
        </div>
  
      </div>

      <div className="grid gap-4">
        <Field label="Contact name" icon={UserRound}>
          <input
            className="min-w-0 flex-1 border-0 bg-transparent text-sm outline-none placeholder:text-ink/35"
            name="name"
            onChange={updateField}
            placeholder="Maya Patel"
            required
            value={form.name}
          />
        </Field>
        <Field label="Email" icon={Send}>
          <input
            className="min-w-0 flex-1 border-0 bg-transparent text-sm outline-none placeholder:text-ink/35"
            name="email"
            onChange={updateField}
            placeholder="maya@northlinehomes.com"
            required
            type="email"
            value={form.email}
          />
        </Field>
        <Field label="Company" icon={Building2}>
          <input
            className="min-w-0 flex-1 border-0 bg-transparent text-sm outline-none placeholder:text-ink/35"
            name="company"
            onChange={updateField}
            placeholder="Northline Homes"
            required
            value={form.company}
          />
        </Field>
        <Field label="Property address" icon={MapPin}>
          <input
            className="min-w-0 flex-1 border-0 bg-transparent text-sm outline-none placeholder:text-ink/35"
            name="property_address"
            onChange={updateField}
            placeholder="1200 Commerce St"
            required
            value={form.property_address}
          />
        </Field>
        <div className="grid gap-4 sm:grid-cols-[1fr_96px_80px]">
          <input
            className="focus-ring rounded border border-ink/10 bg-white px-3 py-2.5 text-sm outline-none placeholder:text-ink/35"
            name="city"
            onChange={updateField}
            placeholder="City"
            required
            value={form.city}
          />
          <input
            className="focus-ring rounded border border-ink/10 bg-white px-3 py-2.5 text-sm uppercase outline-none placeholder:text-ink/35"
            maxLength={2}
            name="state"
            onChange={updateField}
            placeholder="TX"
            required
            value={form.state}
          />
          <input
            className="focus-ring rounded border border-ink/10 bg-white px-3 py-2.5 text-sm uppercase outline-none placeholder:text-ink/35"
            maxLength={2}
            name="country"
            onChange={updateField}
            value={form.country}
          />
        </div>
      </div>

      <button
        className="focus-ring mt-5 flex h-11 w-full items-center justify-center gap-2 rounded bg-spruce px-4 text-sm font-semibold text-white transition hover:bg-moss disabled:cursor-not-allowed disabled:opacity-70"
        disabled={isSubmitting}
        type="submit"
      >
        {isSubmitting ? <Loader2 size={17} className="animate-spin" /> : <Send size={17} />}
        Run enrichment
      </button>
    </form>
  );
}
