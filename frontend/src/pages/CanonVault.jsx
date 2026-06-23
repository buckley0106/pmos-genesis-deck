import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { JsonViewer } from "@/components/JsonViewer";
import { Vault, FileBadge } from "lucide-react";

export default function CanonVault() {
  const [entries, setEntries] = useState([]);
  const [active, setActive] = useState(null);
  const [cert, setCert] = useState(null);

  useEffect(() => { (async () => {
    const { data } = await api.get("/canon-vault");
    setEntries(data);
    if (data.length > 0) setActive(data[0]);
  })(); }, []);

  useEffect(() => { (async () => {
    if (!active) return;
    try {
      const { data } = await api.get(`/canon-vault/${active.asset_id}/certificate`);
      setCert(data);
    } catch { setCert(null); }
  })(); }, [active]);

  return (
    <div className="space-y-5" data-testid="canon-vault-page">
      <div>
        <div className="pmos-eyebrow mb-1">Canon Vault</div>
        <h1 className="pmos-h2 flex items-center gap-2"><Vault size={26} strokeWidth={1.5} className="text-cyan-300"/>Approved Civilizations</h1>
        <p className="text-slate-400 text-sm mt-1">All Meme Assets admitted to the canon via governance or admin fiat.</p>
      </div>

      {entries.length === 0 && (
        <div className="pmos-card p-8 text-center pmos-meta" data-testid="canon-empty">Vault is empty. Approve a Meme Asset to add its first entry.</div>
      )}

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {entries.map((e) => (
          <button
            key={e.id}
            onClick={() => setActive(e)}
            data-testid={`canon-entry-${e.asset_id.slice(0, 8)}`}
            className={`pmos-card p-4 text-left transition-all ${active?.id === e.id ? "border-cyan-400 shadow-[0_0_18px_rgba(0,240,255,0.08)]" : "hover:border-cyan-500/40"}`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="pmos-badge pmos-badge-success">canon</span>
              <span className="pmos-badge pmos-badge-magenta">{e.rarity?.tier}</span>
            </div>
            <div className="font-display text-lg text-white truncate">{e.seed}</div>
            <div className="pmos-meta mt-1">asset {e.asset_id.slice(0, 12)}…</div>
            <div className="pmos-meta">added {new Date(e.added_at).toLocaleString()}</div>
          </button>
        ))}
      </div>

      {active && (
        <div className="grid lg:grid-cols-2 gap-4" data-testid="canon-detail">
          <JsonViewer data={active} label="Vault Entry" testId="canon-entry-json" maxHeight={360} />
          {cert ? (
            <div className="pmos-card-elevated p-5 relative">
              <div className="absolute top-0 right-0 px-3 py-1 bg-cyan-400/10 border-l border-b border-cyan-500/40 font-display text-[10px] uppercase tracking-widest text-cyan-300">
                <FileBadge size={10} className="inline mr-1" /> Certificate
              </div>
              <div className="pmos-eyebrow mb-3">Canon Certificate</div>
              <h3 className="pmos-h3">Of Authenticity</h3>
              <div className="pmos-divider my-4" />
              <div className="space-y-2 font-mono text-xs">
                <div><span className="text-slate-500">Issued at:</span> <span className="text-cyan-300">{cert.issued_at}</span></div>
                <div><span className="text-slate-500">Issuer:</span> <span className="text-cyan-300">{cert.issuer}</span></div>
                <div><span className="text-slate-500">Owner:</span> <span className="text-cyan-300">{cert.owner}</span></div>
                <div><span className="text-slate-500">Asset:</span> <span className="text-cyan-300">{cert.asset_id}</span></div>
                <div className="break-all"><span className="text-slate-500">Hash:</span> <span className="text-emerald-300">{cert.hash}</span></div>
              </div>
              <div className="pmos-divider my-4" />
              <p className="font-mono text-[10px] text-slate-500 leading-relaxed">
                This certificate attests that the associated Meme Asset has been admitted to the WMEU Canon Vault
                pursuant to the PMOS canon process. Issued under © Patrick Buckley 2026 — all rights reserved.
              </p>
            </div>
          ) : (
            <div className="pmos-card p-5 pmos-meta">No certificate found.</div>
          )}
        </div>
      )}
    </div>
  );
}
