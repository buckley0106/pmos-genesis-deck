import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { EngineNode } from "@/components/EngineNode";
import { JsonViewer } from "@/components/JsonViewer";
import { Bug, PlayCircle } from "lucide-react";
import { toast } from "sonner";

export default function DebugDashboard() {
  const [engines, setEngines] = useState([]);
  const [events, setEvents] = useState([]);
  const [seed, setSeed] = useState("DEBUG-SEED");
  const [target, setTarget] = useState("");
  const [report, setReport] = useState(null);
  const [running, setRunning] = useState(false);

  async function load() {
    const [e, ev] = await Promise.all([api.get("/pmos/engine-status"), api.get("/pmos/system-events?limit=20")]);
    setEngines(e.data); setEvents(ev.data);
  }
  useEffect(() => { load(); }, []);

  async function debugRun() {
    setRunning(true); setReport(null);
    try {
      const { data } = await api.post("/pmos/debug", { seed, engine: target || null });
      setReport(data);
      const fails = data.report.filter((r) => !r.ok).length;
      if (fails === 0) toast.success(`All ${data.report.length} engine(s) passed`);
      else toast.error(`${fails} engine(s) failed`);
    } finally { setRunning(false); load(); }
  }

  return (
    <div className="space-y-5" data-testid="debug-page">
      <div>
        <div className="pmos-eyebrow mb-1">Debug Dashboard</div>
        <h1 className="pmos-h2 flex items-center gap-2"><Bug size={26} className="text-cyan-300" strokeWidth={1.5}/>debugPMOS Console</h1>
        <p className="text-slate-400 text-sm mt-1">Validate single engines or the full pipeline. JSON outputs are checked structurally.</p>
      </div>

      <div className="pmos-card-elevated p-5">
        <div className="grid sm:grid-cols-[1fr_1fr_auto] gap-3 items-end">
          <div>
            <label className="pmos-label">Seed</label>
            <input className="pmos-input" value={seed} onChange={(e) => setSeed(e.target.value)} data-testid="debug-seed-input" />
          </div>
          <div>
            <label className="pmos-label">Engine (blank = all)</label>
            <select className="pmos-input" value={target} onChange={(e) => setTarget(e.target.value)} data-testid="debug-engine-select">
              <option value="">All engines</option>
              {engines.map((e) => <option key={e.engine_name} value={e.engine_name}>{e.engine_name}</option>)}
            </select>
          </div>
          <button onClick={debugRun} disabled={running} className="pmos-btn-primary flex items-center gap-1.5" data-testid="debug-run-button">
            <PlayCircle size={14} /> {running ? "Running…" : "Run debugPMOS"}
          </button>
        </div>
      </div>

      <section>
        <h2 className="pmos-h3 mb-3">Engine Health Grid</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
          {engines.map((s, i) => (
            <EngineNode key={s.engine_name} name={s.engine_name} status={s.status} index={i} version={s.engine_version} lastRun={s.last_run} />
          ))}
        </div>
      </section>

      <div className="grid lg:grid-cols-2 gap-4">
        {report && <JsonViewer data={report} label="debug report" testId="debug-report-json" maxHeight={360}/>}
        <div className="pmos-card p-4" data-testid="debug-events">
          <div className="pmos-eyebrow mb-2">Recent system events</div>
          <div className="max-h-[360px] overflow-y-auto space-y-1">
            {events.map((ev) => (
              <div key={ev.event_id} className="flex items-start gap-2 py-1 border-b border-[#111322] last:border-b-0">
                <span className={`pmos-badge ${ev.type === "engine_error" ? "pmos-badge-error" : "pmos-badge-magenta"}`}>{ev.type}</span>
                <div className="flex-1 font-mono text-xs text-slate-300 break-words">{ev.summary}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
