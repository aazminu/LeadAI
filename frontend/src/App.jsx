import { LayoutDashboard, Settings } from "lucide-react";
import { Link, Route, Routes, useLocation } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import AgentOutputsPage from "./pages/AgentOutputsPage";
import SettingsPage from "./pages/SettingsPage";
import ScoringMethodologyPage from "./pages/ScoringMethodologyPage";
import eliseLogo from "./assets/elise-ai-logo.png";

const NAV = [
  { to: "/",         label: "Dashboard", icon: LayoutDashboard },
  { to: "/settings", label: "Settings",  icon: Settings },
];

function NavLink({ to, label, icon: Icon }) {
  const { pathname } = useLocation();
  const active = pathname === to;
  return (
    <Link
      to={to}
      className={`focus-ring flex h-9 items-center gap-2 rounded px-3 text-sm transition ${
        active
          ? "bg-spruce text-white"
          : "text-ink/70 hover:bg-spruce/8 hover:text-graphite"
      }`}
    >
      <Icon size={16} aria-hidden="true" />
      {label}
    </Link>
  );
}

export default function App() {
  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="border-b border-steel/15 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-2 py-3 sm:px-3 lg:px-3">
          <div className="flex min-w-0 items-center">
            <Link to="/">
              <img
                className="h-9 w-auto shrink-0 object-contain object-left"
                src={eliseLogo}
                alt="EliseAI"
              />
            </Link>
            <div className="ml-8">
              <p className="text-sm font-semibold leading-4 text-graphite">LeadAI</p>
              <p className="text-xs text-ink/60">Internal property-management workspace</p>
            </div>
          </div>

          <nav className="hidden items-center gap-1 md:flex" aria-label="Primary">
            {NAV.map((item) => (
              <NavLink key={item.to} {...item} />
            ))}
          </nav>
        </div>
      </header>

      <Routes>
        <Route path="/"         element={<Dashboard />} />
        <Route path="/leads/:leadId/outputs" element={<AgentOutputsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/scoring"  element={<ScoringMethodologyPage />} />
      </Routes>
    </div>
  );
}
