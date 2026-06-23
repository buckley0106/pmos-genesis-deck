import { useEffect, useState } from "react";
import { api, formatApiErrorDetail } from "@/lib/api";
import { JsonViewer } from "@/components/JsonViewer";
import { EngineNode } from "@/components/EngineNode";
import { Play, Shuffle, Rocket, Sparkles, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { Link } from "react-router-dom";

const SAMPLE_SEEDS = [
  "WABOOT-PRIME-001",
  "P.BUCK-GENESIS",
  "PEPE-OVERLORD-9",
  "VOID-CHAD-XIII",
  "DOGE-ASCENDED-VII",
];

export default function Dashboard() {
  const [seed, setSeed] = useState("WABOOT-PRIME-001");
  const [enrichAI, setEnrichAI] = useState(false);
  const [running, setRunning] = useState(false);
  const [statuses, setStatuses] = useState([]);
  const [result, setResult] = useState(null);
  const [progress, setProgress] = useState(0);
  const [pollingId, setPollingId] = useState(null);

  async function loadStatuses() {
    try {
      const { data } = await api.get("/pmos/engine-status");
      setStatuses(data);
    } catch (e) { /* ignore */ }
  }

  useEffect(() => { loadStatuses(); }, []);

  useEffect(() => {
    if (!pollingId) return;
    const t = setInterval(loadStatuses, 350);
    return () => clearInterval(t);
  }, [pollingId]);

  async function runPMOS() {
    if (!seed.trim()) {
      toast.error("Please enter a seed");
      return;
    }
    setRunning(true);
    setResult(null);
    setProgress(0);
    setPollingId(Date.now());
    // simulated incremental progress while server runs
    const fakeTick = setInterval(() => setProgress((p) => Math.min(p + 7, 92)), 120);
    try {
      const { data } = await api.post("/pmos/run", { seed, enrich_ai: enrichAI });
      setResult(data);
      setProgress(100);
      toast.success(`PMOS run complete — rarity ${data.rarity?.tier?.toUpperCase()} (${data.rarity?.score})`);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    } finally {
      clearInterval(fakeTick);
      setRunning(false);
      setPollingId(null);
      loadStatuses();
    }
  }

  const completed = statuses.filter((s) => s.status === "success").length;

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      {/* HERO */}
      <section className="relative overflow-hidden pmos-card-elevated p-6 sm:p-10 pmos-corner">
        <div className="absolute inset-0 pmos-grid-bg opacity-25 pointer-events-none" />
        <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent" />
        <div className="relative">
          <div className="flex items-center gap-2 mb-3">
            <span className="pmos-badge pmos-badge-running">live</span>
            <span className="pmos-eyebrow">mission control · 15-engine pipeline</span>
          </div>
          <h1 className="pmos-h1 mb-2">
            Meme Civilization <span className="text-cyan-300">Engine</span>
          </h1>
          <p className="text-slate-400 text-sm max-w-2xl mb-6 leading-relaxed">
            Feed a seed. Drive 15 engines. Bind blueprints, biology, energy, lore, coin, and chart data
            into a single canonical Meme Asset — minted, vaulted, and governance-ready.
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
                <button
                  type="button"
                  className="pmos-btn-secondary flex items-center gap-1.5"
                  data-testid="dashboard-random-seed"
                  onClick={() => setSeed(SAMPLE_SEEDS[Math.floor(Math.random() * SAMPLE_SEEDS.length)] + "-" + Math.floor(Math.random()*999))}
                >
                  <Shuffle size={12} /> Random
                </button>
              </div>
            </div>
            <div className="flex flex-col justify-end gap-2">
              <label className="pmos-label">AI Enrich (text only)</label>
              <button
                type="button"
                onClick={() => setEnrichAI(!enrichAI)}
                data-testid="dashboard-enrich-toggle"
                className={`pmos-btn-secondary flex items-center gap-2 ${enrichAI ? "!border-fuchsia-400 !text-fuchsia-300" : ""}`}
              >
                <Sparkles size={12} /> {enrichAI ? "ON" : "OFF"}
              </button>
            </div>
          </div>

          <button
            onClick={runPMOS}
            disabled={running}
            className="pmos-btn-primary text-sm flex items-center gap-2"
            data-testid="run-pmos-button"
          >
            {running ? <Play size={14} className="animate-pulse" /> : <Rocket size={14} />}
            {running ? "Running PMOS..." : "Run PMOS"}
          </button>

          <div className="mt-6">
            <div className="flex justify-between items-center mb-2 pmos-meta">
              <span>Pipeline progress · {completed}/15 engines</span>
              <span>{progress}%</span>
            </div>
            <div className="h-1 bg-[#111322] overflow-hidden">
              <div className="h-full bg-gradient-to-r from-cyan-400 to-fuchsia-500 transition-all" style={{ width: `${progress}%` }} />
            </div>
          </div>
        </div>
      </section>

      {/* ENGINE GRID */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="pmos-h3">15-Engine Pipeline</h2>
          <Link to="/control-deck" className="pmos-meta hover:text-cyan-300 flex items-center gap-1" data-testid="link-control-deck">
            view control deck <ChevronRight size={12} />
          </Link>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5 gap-3" data-testid="engine-grid">
          {statuses.map((s, i) => (
            <EngineNode key={s.engine_name} name={s.engine_name} status={s.status} index={i} version={s.engine_version} lastRun={s.last_run} />
          ))}
        </div>
      </section>

      {/* RESULT */}
      {result && (
        <section className="animate-fade-in space-y-3" data-testid="dashboard-result-section">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="pmos-h3">Generated Meme Asset</h2>
            <div className="flex gap-2">
              <span className="pmos-badge pmos-badge-magenta">{result.rarity?.tier}</span>
              <span className="pmos-badge pmos-badge-success">score {result.rarity?.score}</span>
              <Link to={`/assets/${result.id}`} className="pmos-btn-secondary" data-testid="open-asset-viewer">
                Open in Viewer →
              </Link>
            </div>
          </div>
          <JsonViewer data={result} label={`Meme Asset · ${result.id?.slice(0, 8)}`} testId="dashboard-result-json" maxHeight={520} />
        </section>
      )}
    </div>
  );
}
