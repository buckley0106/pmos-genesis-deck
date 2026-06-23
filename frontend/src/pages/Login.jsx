import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { LogIn, UserPlus } from "lucide-react";

export default function Login() {
  const { user, login, register } = useAuth();
  const nav = useNavigate();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ email: "", password: "", name: "" });
  const [busy, setBusy] = useState(false);

  if (user) {
    return (
      <div className="pmos-card-elevated p-8 max-w-md mx-auto text-center">
        <div className="pmos-eyebrow mb-2">Already authenticated</div>
        <div className="font-display text-xl text-white mb-3">{user.email}</div>
        <Link to="/" className="pmos-btn-primary inline-flex" data-testid="login-go-home">→ Mission Control</Link>
      </div>
    );
  }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    const res = mode === "login"
      ? await login(form.email, form.password)
      : await register(form.email, form.password, form.name);
    setBusy(false);
    if (res.ok) { toast.success(mode === "login" ? "Welcome operator" : "Registered"); nav("/"); }
    else toast.error(res.error);
  }

  return (
    <div className="max-w-md mx-auto" data-testid="login-page">
      <div className="pmos-card-elevated p-6 pmos-corner relative">
        <div className="pmos-eyebrow mb-1">Operator Console</div>
        <h1 className="pmos-h2 mb-1">{mode === "login" ? "Sign in" : "Register"}</h1>
        <p className="text-slate-400 text-xs mb-5">
          Auth required only for governance & economic write actions. Generation is open to all.
        </p>
        <form onSubmit={submit} className="space-y-3">
          {mode === "register" && (
            <div>
              <label className="pmos-label">Operator name</label>
              <input className="pmos-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="auth-name-input"/>
            </div>
          )}
          <div>
            <label className="pmos-label">Email</label>
            <input required type="email" autoComplete="email" className="pmos-input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="auth-email-input"/>
          </div>
          <div>
            <label className="pmos-label">Password</label>
            <input required type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} className="pmos-input" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} data-testid="auth-password-input"/>
          </div>
          <button type="submit" disabled={busy} className="pmos-btn-primary w-full flex items-center justify-center gap-2" data-testid="auth-submit-button">
            {mode === "login" ? <><LogIn size={14}/> Authenticate</> : <><UserPlus size={14}/> Create operator</>}
          </button>
        </form>
        <div className="pmos-divider my-4" />
        <button type="button" onClick={() => setMode(mode === "login" ? "register" : "login")} className="font-display uppercase tracking-widest text-[11px] text-cyan-300 hover:text-cyan-200" data-testid="auth-mode-toggle">
          {mode === "login" ? "Need to register? →" : "← Have an account? Sign in"}
        </button>
        <div className="mt-4 p-3 border border-[#111322] bg-[#05050A]">
          <div className="pmos-eyebrow mb-1">Admin demo</div>
          <div className="font-mono text-[11px] text-slate-400 break-all">patrick@buckleylabs.io / WMEU-2026-Admin!</div>
        </div>
      </div>
    </div>
  );
}
