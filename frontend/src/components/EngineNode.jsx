import { CheckCircle2, CircleDot, AlertOctagon, Loader2 } from "lucide-react";

const ICONS = {
  idle: CircleDot,
  running: Loader2,
  success: CheckCircle2,
  error: AlertOctagon,
};

const COLORS = {
  idle: "border-[#1A1D2E] text-slate-500",
  running: "border-cyan-400/70 text-cyan-300 animate-pulse-cyan",
  success: "border-emerald-400/70 text-emerald-300",
  error: "border-rose-500/70 text-rose-400",
};

export function EngineNode({ name, status = "idle", index, version, lastRun }) {
  const Icon = ICONS[status] || CircleDot;
  return (
    <div
      data-testid={`engine-node-${name}`}
      className={`pmos-card relative p-3 transition-all hover:border-cyan-400/40 ${COLORS[status]}`}
    >
      <div className="flex items-start gap-2">
        <div className="font-display font-bold text-[10px] tracking-widest text-slate-600">
          {String(index + 1).padStart(2, "0")}
        </div>
        <div className="flex-1">
          <div className="font-display font-semibold text-sm text-white leading-tight">{name}</div>
          <div className="pmos-meta mt-0.5">v{version || "1.0.0"}</div>
        </div>
        <Icon size={14} strokeWidth={1.8} className={status === "running" ? "animate-spin" : ""} />
      </div>
      <div className="mt-2 flex items-center justify-between">
        <span className={`pmos-badge pmos-badge-${status}`}>{status}</span>
        {lastRun && <span className="font-mono text-[10px] text-slate-600">{new Date(lastRun).toLocaleTimeString()}</span>}
      </div>
    </div>
  );
}
