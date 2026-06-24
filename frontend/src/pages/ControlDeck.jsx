import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { EngineNode } from "@/components/EngineNode";
import WebhookManager from "@/components/WebhookManager";
import { ShieldCheck, Activity, FileWarning, BookOpen, Vault } from "lucide-react";

export default function ControlDeck() {
  const [engines, setEngines] = useState([]);
  const [events, setEvents] = useState([]);
  const [vault, setVault] = useState([]);
  const [docs, setDocs] = useState(null);

  async function load() {
    const [e, ev, v, d] = await Promise.all([
      api.get("/pmos/engine-status"),
      api.get("/pmos/system-events?limit=40"),
      api.get("/canon-vault?limit=200"),
      api.get("/docs/all"),
    ]);
    setEngines(e.data); setEvents(ev.data); setVault(v.data); setDocs(d.data);
  }
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, []);

  const healthy = engines.filter((e) => e.status === "success" || e.status === "idle").length;
  const errors = engines.filter((e) => e.status === "error").length;
  const totalCanon = vault.length;

  return (
    <div className="space-y-6" data-testid="control-deck-page">
      <div>
        <div className="pmos-eyebrow mb-1">Control Deck</div>
        <h1 className="pmos-h2 flex items-center gap-2"><ShieldCheck size={28} className="text-cyan-300" strokeWidth={1.5}/>Operator Console</h1>
      </div>

      <div className="grid sm:grid-cols-3 gap-3">
        <Tile icon={Activity} label="Engine health" value={`${healthy}/${engines.length || 26}`} accent="cyan" testId="tile-health" sub={`${errors} error${errors !== 1 ? "s" : ""}`}/>
        <Tile icon={Vault} label="Canon entries" value={totalCanon} accent="fuchsia" testId="tile-canon" />
        <Tile icon={FileWarning} label="Events (24h sample)" value={events.length} accent="emerald" testId="tile-events"/>
      </div>

      <section data-testid="engine-health-panel">
        <h2 className="pmos-h3 mb-3">Engine Health</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 lg:grid-cols-6 gap-3">
          {engines.map((s, i) => (
            <EngineNode key={s.engine_name} name={s.engine_name} status={s.status} index={i} version={s.engine_version} lastRun={s.last_run} />
          ))}
        </div>
      </section>

      <WebhookManager />

      <div className="grid lg:grid-cols-2 gap-5">
        <section className="pmos-card p-4" data-testid="event-timeline-panel">
          <div className="flex items-center justify-between mb-3">
            <h2 className="pmos-h3">Event Timeline</h2>
            <span className="pmos-meta">{events.length} recent</span>
          </div>
          <div className="max-h-[420px] overflow-y-auto space-y-1.5">
            {events.length === 0 && <div className="pmos-meta">No events.</div>}
            {events.map((ev) => (
              <div key={ev.event_id} className="flex items-start gap-2 py-1.5 border-b border-[#111322] last:border-b-0">
                <span className={`pmos-badge ${ev.type === "engine_error" ? "pmos-badge-error" : ev.type === "canon_approved" ? "pmos-badge-success" : "pmos-badge-magenta"}`}>{ev.type}</span>
                <div className="flex-1">
                  <div className="font-mono text-xs text-slate-300 break-words">{ev.summary}</div>
                  <div className="pmos-meta">{new Date(ev.timestamp).toLocaleString()}</div>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="pmos-card p-4" data-testid="docs-rules-panel">
          <div className="flex items-center justify-between mb-3">
            <h2 className="pmos-h3 flex items-center gap-2"><BookOpen size={18} strokeWidth={1.5} className="text-cyan-300"/>Docs & Rules</h2>
          </div>
          {!docs ? <div className="pmos-meta">Loading…</div> : (
            <div className="space-y-3 text-sm">
              <DocBlock title={docs.constitution.title} body={docs.constitution.body} testId="doc-constitution"/>
              <DocBlock title={docs.rarity_formula.title} body={docs.rarity_formula.body} testId="doc-rarity"/>
              <DocBlock title={docs.engine_order.title} body={docs.engine_order.body} testId="doc-engine-order"/>
              <DocBlock title={docs.canon_process.title} body={docs.canon_process.body} testId="doc-canon-process"/>
              <DocBlock title={docs.debug_checklist.title} body={docs.debug_checklist.body} testId="doc-debug"/>
              <DocBlock title="Amendment Log" body={docs.amendments?.length ? docs.amendments.map(a => `• v${a.version} — ${a.title}: ${a.body}`).join("\n") : "(no amendments)"} testId="doc-amendments"/>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function Tile({ icon: Icon, label, value, accent = "cyan", sub, testId }) {
  const c = accent === "fuchsia" ? "text-fuchsia-300 border-fuchsia-500/30" : accent === "emerald" ? "text-emerald-300 border-emerald-500/30" : "text-cyan-300 border-cyan-500/30";
  return (
    <div className={`pmos-card-elevated p-4 border ${c}`} data-testid={testId}>
      <div className="flex items-center justify-between">
        <span className="pmos-eyebrow">{label}</span>
        <Icon size={16} strokeWidth={1.4} />
      </div>
      <div className="font-display font-bold text-3xl text-white mt-1">{value}</div>
      {sub && <div className="pmos-meta mt-0.5">{sub}</div>}
    </div>
  );
}
function DocBlock({ title, body, testId }) {
  return (
    <details className="border border-[#111322] p-3" data-testid={testId}>
      <summary className="cursor-pointer font-display uppercase tracking-widest text-[11px] text-cyan-300">{title}</summary>
      <pre className="whitespace-pre-wrap font-mono text-[11px] text-slate-300 mt-2 leading-relaxed">{body}</pre>
    </details>
  );
}
