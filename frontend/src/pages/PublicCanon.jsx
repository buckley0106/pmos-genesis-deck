import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "@/lib/api";
import { ExternalLink, Share2, Copy } from "lucide-react";
import { toast } from "sonner";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

export default function PublicCanon() {
  const { id } = useParams();
  const [asset, setAsset] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => { (async () => {
    try {
      const { data } = await api.get(`/public/canon/${id}.json`);
      setAsset(data);
    } catch (e) { setError("Asset not in canon or not found"); }
  })(); }, [id]);

  function share() {
    const url = `${BACKEND}/canon/${id}`;
    if (navigator.share) navigator.share({ title: "PMOS•WMEU Canon", url });
    else { navigator.clipboard?.writeText(url); toast.success("Public canon URL copied"); }
  }
  function copyUrl() {
    navigator.clipboard?.writeText(`${BACKEND}/canon/${id}`); toast.success("Copied");
  }

  if (error) return <div className="pmos-card p-8 pmos-meta" data-testid="public-error">{error}</div>;
  if (!asset) return <div className="pmos-meta">Loading canon entry…</div>;

  const e = asset.engines || {};
  const identity = e.Identity || {};
  const rarity = asset.rarity || {};

  return (
    <div className="space-y-5 animate-fade-in" data-testid="public-canon-page">
      <div className="pmos-card-elevated p-5 pmos-corner relative">
        <img src={`${BACKEND}/api/public/og/${id}.png`} alt="canon OG" className="w-full border border-[#1A1D2E]" data-testid="public-og-image"/>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="pmos-eyebrow">Public Canon Page</div>
          <h1 className="pmos-h2">{identity.true_name || asset.seed}</h1>
          {identity.epithet && <div className="font-display text-fuchsia-300 text-lg">{identity.epithet}</div>}
          <div className="mt-2 flex gap-2 flex-wrap">
            <span className="pmos-badge pmos-badge-magenta">{rarity.tier}</span>
            <span className="pmos-badge pmos-badge-success">canon</span>
            <span className="pmos-badge pmos-badge-running">score {rarity.score}</span>
            {e.MemeCoinBinder?.ticker && <span className="pmos-badge pmos-badge-magenta">{e.MemeCoinBinder.ticker}</span>}
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button onClick={share} className="pmos-btn-primary flex items-center gap-1.5" data-testid="public-share-button"><Share2 size={12}/> Share</button>
          <button onClick={copyUrl} className="pmos-btn-secondary flex items-center gap-1.5"><Copy size={12}/> Copy URL</button>
          <a href={`${BACKEND}/canon/${id}`} target="_blank" rel="noreferrer" className="pmos-btn-secondary flex items-center gap-1.5" data-testid="public-open-server-page"><ExternalLink size={12}/> Open server page</a>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 gap-3">
        <Card title="Lore">
          <p className="text-slate-300 text-sm leading-relaxed">{e.Lore?.summary || "—"}</p>
          <div className="mt-2 flex gap-1 flex-wrap">
            {(e.Lore?.tags || []).map((t) => <span key={t} className="pmos-badge pmos-badge-idle">{t}</span>)}
          </div>
        </Card>
        <Card title="Identity Record">
          <KV k="Species" v={e.Species?.name}/>
          <KV k="Faction" v={e.Faction?.name}/>
          <KV k="House" v={identity.house}/>
          <KV k="Soul Index" v={identity.soul_index}/>
          <KV k="Generation" v={e.Continuity?.generation}/>
          <KV k="Influence" v={`${e.Influence?.influence_score} (${e.Influence?.reach_class})`}/>
        </Card>
        <Card title="On-chain (simulated)">
          <KV k="Token ID" v={asset.token_id}/>
          <KV k="Chain hash" v={asset.chain_hash} mono/>
          <KV k="Chain" v={e.NFTMint?.chain}/>
        </Card>
        <Card title="Universe Time">
          <KV k="Epoch" v={e.UniverseTime?.wmeu_epoch}/>
          <KV k="Era" v={e.UniverseTime?.era}/>
          <KV k="Solstice" v={String(e.UniverseTime?.is_solstice)}/>
        </Card>
      </div>

      <div className="pmos-card p-4 text-center" data-testid="public-cta">
        <div className="pmos-eyebrow mb-2">Mint your own civilization</div>
        <Link to="/" className="pmos-btn-primary inline-flex">→ Run PMOS</Link>
      </div>
    </div>
  );
}

function Card({ title, children }) {
  return (
    <div className="pmos-card p-4">
      <div className="pmos-eyebrow mb-2">{title}</div>
      {children}
    </div>
  );
}
function KV({ k, v, mono }) {
  return (
    <div className="flex justify-between gap-3 py-1 border-b border-[#111322] last:border-b-0">
      <span className="font-display text-[11px] uppercase tracking-widest text-slate-500">{k}</span>
      <span className={`text-cyan-300 ${mono ? "font-mono text-[10px] break-all text-right" : "font-mono text-xs"}`}>{v ?? "—"}</span>
    </div>
  );
}
