import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
  LayoutDashboard, Boxes, Vault, Scale, Sigma, LineChart, Activity, Bug, ScrollText, LogIn, LogOut, ShieldCheck,
} from "lucide-react";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, id: "dashboard" },
  { to: "/assets", label: "Meme Assets", icon: Boxes, id: "assets" },
  { to: "/canon", label: "Canon Vault", icon: Vault, id: "canon" },
  { to: "/governance", label: "Governance", icon: Scale, id: "governance" },
  { to: "/rarity", label: "Rarity Calc", icon: Sigma, id: "rarity" },
  { to: "/economic", label: "Economic Sim", icon: Activity, id: "economic" },
  { to: "/charts", label: "Chart Viewer", icon: LineChart, id: "charts" },
  { to: "/control-deck", label: "Control Deck", icon: ShieldCheck, id: "control-deck" },
  { to: "/debug", label: "Debug", icon: Bug, id: "debug" },
  { to: "/legal", label: "Legal & Docs", icon: ScrollText, id: "legal" },
];

export function Layout({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  return (
    <div className="min-h-screen flex flex-col text-slate-200">
      <header className="sticky top-0 z-50 pmos-glass border-b border-cyan-500/15">
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6 py-3 flex items-center gap-6">
          <NavLink to="/" className="flex items-center gap-3" data-testid="nav-brand">
            <div className="w-8 h-8 border border-cyan-400 grid place-items-center text-cyan-300 font-display font-bold text-lg" style={{ boxShadow: "0 0 12px rgba(0,240,255,0.35)" }}>
              P
            </div>
            <div className="leading-tight">
              <div className="font-display font-bold tracking-widest text-white text-sm">PMOS • WMEU</div>
              <div className="pmos-meta">Meme Civilization Engine</div>
            </div>
          </NavLink>
          <div className="hidden lg:flex items-center gap-1 flex-1 overflow-x-auto">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/"}
                data-testid={`nav-link-${n.id}`}
                className={({ isActive }) =>
                  `font-display uppercase tracking-widest text-[11px] px-3 py-2 border border-transparent transition-all flex items-center gap-1.5 ${
                    isActive ? "text-cyan-300 border-cyan-500/40 bg-cyan-500/5" : "text-slate-400 hover:text-cyan-200 hover:border-cyan-500/20"
                  }`
                }
              >
                <n.icon size={14} strokeWidth={1.5} /> {n.label}
              </NavLink>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-2">
            {user ? (
              <>
                <span className="hidden sm:inline-flex pmos-badge pmos-badge-success" data-testid="user-role-badge">
                  {user.role}
                </span>
                <span className="hidden md:inline font-mono text-xs text-slate-400">{user.email}</span>
                <button onClick={() => { logout(); nav("/"); }} className="pmos-btn-secondary flex items-center gap-1.5" data-testid="logout-button">
                  <LogOut size={12} /> Logout
                </button>
              </>
            ) : (
              <NavLink to="/login" className="pmos-btn-primary flex items-center gap-1.5" data-testid="login-button">
                <LogIn size={12} /> Operator Login
              </NavLink>
            )}
          </div>
        </div>
        {/* mobile nav */}
        <div className="lg:hidden flex items-center gap-1 px-3 pb-2 overflow-x-auto">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              data-testid={`nav-mobile-${n.id}`}
              className={({ isActive }) =>
                `font-display uppercase tracking-widest text-[10px] px-2.5 py-1.5 border whitespace-nowrap ${
                  isActive ? "text-cyan-300 border-cyan-500/40" : "text-slate-400 border-[#1A1D2E]"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </div>
      </header>
      <main className="flex-1 max-w-[1600px] w-full mx-auto px-4 sm:px-6 py-6 sm:py-8">{children}</main>
      <footer className="border-t border-[#111322] bg-[#05050A] py-6 mt-12">
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6 flex flex-col md:flex-row md:items-center gap-3 text-[11px] text-slate-500 font-mono">
          <span data-testid="footer-copyright">© 2026 Patrick Buckley — All rights reserved.</span>
          <span className="text-slate-700">·</span>
          <span>P.BUCK™ · PMOS™ · WMEU™ · Waboot Meme Engine Universe™</span>
          <span className="text-slate-700 hidden md:inline">·</span>
          <span className="md:ml-auto">Buckley Labs LLC <span className="text-slate-700">(pending)</span></span>
        </div>
      </footer>
    </div>
  );
}
