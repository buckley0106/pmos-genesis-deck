import { useEffect, useRef, useState } from "react";
import { api, API, formatApiErrorDetail } from "@/lib/api";
import { JsonViewer } from "@/components/JsonViewer";
import { EngineNode } from "@/components/EngineNode";
import { Play, Shuffle, Rocket, Sparkles, ChevronRight, Radio } from "lucide-react";
import { toast } from "sonner";
import { Link } from "react-router-dom";

const SAMPLE_SEEDS = ["WABOOT-PRIME-001", "P.BUCK-GENESIS", "PEPE-OVERLORD-9", "VOID-CHAD-XIII", "DOGE-ASCENDED-VII", "GLYPH-COIN-2026"];

export default function Dashboard() {
  const [seed, setSeed] = useState("WABOOT-PRIME-001");
  const [enrichAI, setEnrichAI] = useState(false);
  const [running, setRunning] = useState(false);
  const [statuses, setStatuses] = useState([]);
  const [result, setResult] = useState(null);
  const [progress, setProgress] = useState(0);
  const [ticks, setTicks] = useState([]); // recent SSE engine events
  const esRef = useRef(null);

  async function loadStatuses() {
    try {
      const { data } = await api.get("/pmos/engine-status");
      setStatuses(data);
    } catch { /* ignore */ }
  }
  useEffect(() => { loadStatuses(); }, []);

  function closeStream() { try { esRef.current?.close(); } catch { /* */ } esRef.current = null; }

  function runPMOS() {
    if (!seed.trim()) { toast.error("Please enter a seed"); return; }
    setRunning(true); setResult(null); setProgress(0); setTicks([]);
    closeStream();
    const url = `${API}/pmos/run/stream?seed=${encodeURIComponent(seed)}&enrich_ai=${enrichAI}`;
    const es = new EventSource(url);
    esRef.current = es;
    let total = 26;

    es.addEventListener("start", (e) => {
      const data = JSON.parse(e.data); total = data.total;
    });
    es.addEventListener("engine_start", (e) => {
      const d = JSON.parse(e.data);
      setStatuses((prev) => prev.map((s) => s.engine_name === d.engine ? { ...s, status: "running" } : s));
      setTicks((t) => [{ engine: d.engine, kind: "start", ts: Date.now() }, ...t].slice(0, 60));
    });
    es.addEventListener("engine_done", (e) => {
      const d = JSON.parse(e.data);
      setStatuses((prev) => prev.map((s) => s.engine_name === d.engine ? { ...s, status: "success" } : s));
      setProgress(Math.round(((d.index + 1) / total) * 100));
      setTicks((t) => [{ engine: d.engine, kind: "done", ts: Date.now() }, ...t].slice(0, 60));
    });
    es.addEventListener("engine_error", (e) => {
      const d = JSON.parse(e.data);
      setStatuses((prev) => prev.map((s) => s.engine_name === d.engine ? { ...s, status: "error" } : s));
      setTicks((t) => [{ engine: d.engine, kind: "error", error: d.error, ts: Date.now() }, ...t].slice(0, 60));
    });
    es.addEventListener("complete", (e) => {
      const asset = JSON.parse(e.data);
      setResult(asset);
      setProgress(100);
      setRunning(false);
      closeStream();
      loadStatuses();
      toast.success(`PMOS run complete — rarity ${asset.rarity?.tier?.toUpperCase()} (${asset.rarity?.score})`);
    });
    es.onerror = () => {
      // SSE error or stream closed by server
      if (esRef.current) {
        setRunning(false); closeStream();
        loadStatuses();
      }
    };
  }

  useEffect(() => () => closeStream(), []);

  async function fallbackRun() {
    // legacy non-SSE
    setRunning(true); setResult(null); setProgress(0);
    try {
      const { data } = await api.post("/pmos/run", { seed, enrich_ai: enrichAI });
      setResult(data); setProgress(100);
      toast.success(`PMOS run complete — rarity ${data.rarity?.tier?.toUpperCase()}`);
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail) || e.message); }
    finally { setRunning(false); loadStatuses(); }
  }

  const completed = statuses.filter((s) => s.status === "success").length;

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      <section className="relative overflow-hidden pmos-card-elevated p-6 sm:p-10 pmos-corner">
        <div className="absolute inset-0 pmos-grid-bg opacity-25 pointer-events-none" />
        <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent" />
        <div className="relative">
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            <span className="pmos-badge pmos-badge-running">live</span>
            <span className="pmos-eyebrow">mission control · 26-engine pipeline · v2.0 universe-class</span>
          </div>
          <h1 className="pmos-h1 mb-2">
            Meme Civilization <span className="text-cyan-300">Engine</span>
          </h1>
          <p className="text-slate-400 text-sm max-w-2xl mb-6 leading-relaxed">
            Feed a seed. Drive 26 engines. Bind blueprints, biology, energy, identity, lore, coin, marketplace,
            and chart data into a single canonical Meme Asset — minted, vaulted, publicly canonized, and governance-ready.
          </p>

          <div className="grid sm:grid-cols-[1fr_auto] gap-3 mb-3">
            <div>
              <label className="pmos-label" htmlFor="seed-input">Seed</label>
              <div className="flex gap-2">
                <input
                  id="seed-input"
                  data-testid="dashboard-seed-input"
                  className="pmos-input"
                  value={seed}
                  onChange={(e) => setSeed(e.target.value)}
                  placeholder="e.g. WABOOT-PRIME-001"
                />
                <button type="button" className="pmos-btn-secondary flex items-center gap-1.5" data-testid="dashboard-random-seed"
                  onClick={() => setSeed(SAMPLE_SEEDS[Math.floor(Math.random() * SAMPLE_SEEDS.length)] + "-" + Math.floor(Math.random()*999))}>
                  <Shuffle size={12} /> Random
                </button>
              </div>
            </div>
            <div className="flex flex-col justify-end gap-2">
              <label className="pmos-label">AI Enrich (text only)</label>
              <button type="button" onClick={() => setEnrichAI(!enrichAI)} data-testid="dashboard-enrich-toggle"
                className={`pmos-btn-secondary flex items-center gap-2 ${enrichAI ? "!border-fuchsia-400 !text-fuchsia-300" : ""}`}>
                <Sparkles size={12} /> {enrichAI ? "ON" : "OFF"}
              </button>
            </div>
          </div>

          <div className="flex gap-2 flex-wrap">
            <button onClick={runPMOS} disabled={running} className="pmos-btn-primary text-sm flex items-center gap-2" data-testid="run-pmos-button">
              {running ? <Play size={14} className="animate-pulse" /> : <Rocket size={14} />}
              {running ? "Streaming PMOS..." : "Run PMOS (SSE live)"}
            </button>
            <button onClick={fallbackRun} disabled={running} className="pmos-btn-secondary flex items-center gap-1.5" data-testid="run-pmos-classic">
              <Radio size={12}/> Classic run (no stream)
            </button>
          </div>

          <div className="mt-6">
            <div className="flex justify-between items-center mb-2 pmos-meta">
              <span>Pipeline progress · {completed}/{statuses.length || 26} engines</span>
              <span>{progress}%</span>
            </div>
            <div className="h-1 bg-[#111322] overflow-hidden">
              <div className="h-full bg-gradient-to-r from-cyan-400 to-fuchsia-500 transition-all" style={{ width: `${progress}%` }} />
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="pmos-h3">26-Engine Pipeline</h2>
          <Link to="/control-deck" className="pmos-meta hover:text-cyan-300 flex items-center gap-1" data-testid="link-control-deck">
            view control deck <ChevronRight size={12} />
          </Link>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6 gap-3" data-testid="engine-grid">
          {statuses.map((s, i) => (
            <EngineNode key={s.engine_name} name={s.engine_name} status={s.status} index={i} version={s.engine_version} lastRun={s.last_run} />
          ))}
        </div>
      </section>

      {ticks.length > 0 && (
        <section className="pmos-card p-3" data-testid="live-tick-feed">
          <div className="pmos-eyebrow mb-2 flex items-center gap-2"><Radio size={12} className="text-cyan-300 animate-pulse"/> Live tick feed</div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-1 max-h-48 overflow-y-auto">
            {ticks.map((t, i) => (
              <div key={i} className={`font-mono text-[11px] flex justify-between gap-2 px-2 py-1 border-l-2 ${t.kind === "error" ? "border-rose-500 text-rose-300" : t.kind === "done" ? "border-emerald-400 text-emerald-300" : "border-cyan-400 text-cyan-300"}`}>
                <span>{t.kind === "start" ? "▶" : t.kind === "done" ? "✓" : "✕"} {t.engine}</span>
                <span className="text-slate-500">{new Date(t.ts).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {result && (
        <section className="animate-fade-in space-y-3" data-testid="dashboard-result-section">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="pmos-h3">Generated Meme Asset</h2>
            <div className="flex gap-2 flex-wrap">
              <span className="pmos-badge pmos-badge-magenta">{result.rarity?.tier}</span>
              <span className="pmos-badge pmos-badge-success">score {result.rarity?.score}</span>
              <Link to={`/assets/${result.id}`} className="pmos-btn-secondary" data-testid="open-asset-viewer">Open in Viewer →</Link>
              {result.canon_approved && <Link to={`/public/${result.id}`} className="pmos-btn-primary" data-testid="open-public-canon">View public canon page →</Link>}
            </div>
          </div>
          <JsonViewer data={result} label={`Meme Asset · ${result.id?.slice(0, 8)}`} testId="dashboard-result-json" maxHeight={520} />
        </section>
      )}
    </div>
  );
}
