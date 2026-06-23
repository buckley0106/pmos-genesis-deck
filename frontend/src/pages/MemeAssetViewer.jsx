import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, formatApiErrorDetail } from "@/lib/api";
import { JsonViewer } from "@/components/JsonViewer";
import { useAuth } from "@/context/AuthContext";
import { ShieldCheck, FileText } from "lucide-react";
import { toast } from "sonner";

export default function MemeAssetViewer() {
  const { id } = useParams();
  const { user } = useAuth();
  const [assets, setAssets] = useState([]);
  const [active, setActive] = useState(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const { data } = await api.get("/meme-assets");
      setAssets(data);
      if (id) {
        const found = data.find((a) => a.id === id) || (await api.get(`/meme-assets/${id}`)).data;
        setActive(found);
      } else if (data.length > 0 && !active) {
        setActive(data[0]);
      }
    } finally { setLoading(false); }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [id]);

  async function approve() {
    try {
      await api.post(`/meme-assets/${active.id}/approve`);
      toast.success("Asset entered Canon Vault");
      load();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    }
  }

  return (
    <div className="space-y-5" data-testid="asset-viewer-page">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <div className="pmos-eyebrow mb-1">Meme Asset Viewer</div>
          <h1 className="pmos-h2">Bound Civilizations</h1>
        </div>
        <Link to="/" className="pmos-btn-secondary" data-testid="back-to-dashboard">← Generate new</Link>
      </div>

      <div className="grid lg:grid-cols-[320px_1fr] gap-5">
        {/* List */}
        <aside className="pmos-card p-3 max-h-[80vh] overflow-y-auto" data-testid="asset-list">
          <div className="pmos-eyebrow mb-3">{assets.length} asset{assets.length !== 1 && "s"}</div>
          {loading && <div className="pmos-meta">Loading…</div>}
          {!loading && assets.length === 0 && <div className="pmos-meta">No assets yet — run PMOS.</div>}
          <div className="space-y-2">
            {assets.map((a) => (
              <button
                key={a.id}
                onClick={() => setActive(a)}
                data-testid={`asset-item-${a.id.slice(0, 8)}`}
                className={`w-full text-left p-2 border transition-all ${active?.id === a.id ? "border-cyan-400 bg-cyan-500/5" : "border-[#1A1D2E] hover:border-cyan-500/40"}`}
              >
                <div className="font-display text-sm text-white truncate">{a.seed}</div>
                <div className="flex items-center justify-between mt-1">
                  <span className="pmos-meta">{a.id.slice(0, 8)}</span>
                  <div className="flex gap-1">
                    {a.canon_approved && <span className="pmos-badge pmos-badge-success">canon</span>}
                    <span className="pmos-badge pmos-badge-magenta">{a.rarity?.tier}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </aside>

        {/* Detail */}
        <section className="space-y-4">
          {!active && <div className="pmos-card p-6 pmos-meta">Select an asset</div>}
          {active && (
            <>
              <div className="pmos-card-elevated p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="pmos-eyebrow mb-1">Seed</div>
                    <h2 className="pmos-h2 break-all" data-testid="active-asset-seed">{active.seed}</h2>
                    <div className="pmos-meta mt-1">ID {active.id}</div>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <div className="flex gap-2">
                      <span className="pmos-badge pmos-badge-magenta">{active.rarity?.tier}</span>
                      <span className="pmos-badge pmos-badge-success">score {active.rarity?.score}</span>
                      {active.canon_approved ? (
                        <span className="pmos-badge pmos-badge-success flex items-center gap-1"><ShieldCheck size={10} />canon</span>
                      ) : (
                        <span className="pmos-badge pmos-badge-warning">unapproved</span>
                      )}
                    </div>
                    {user?.role === "admin" && !active.canon_approved && (
                      <button onClick={approve} className="pmos-btn-primary flex items-center gap-1.5" data-testid="approve-canon-button">
                        <ShieldCheck size={12} /> Approve to Canon
                      </button>
                    )}
                    {active.canon_approved && (
                      <Link to="/canon" className="pmos-btn-secondary flex items-center gap-1.5" data-testid="view-certificate">
                        <FileText size={12} /> View Certificate
                      </Link>
                    )}
                  </div>
                </div>
              </div>

              <div className="grid sm:grid-cols-2 gap-3">
                {active.engines && Object.entries(active.engines).map(([name, payload]) => (
                  <JsonViewer key={name} data={payload} label={name} testId={`engine-output-${name}`} maxHeight={260} />
                ))}
              </div>

              <JsonViewer data={active} label="Full Meme Asset" testId="full-asset-json" maxHeight={520} />
            </>
          )}
        </section>
      </div>
    </div>
  );
}
