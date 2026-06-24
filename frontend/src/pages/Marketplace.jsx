import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Store, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

export default function Marketplace() {
  const { user } = useAuth();
  const [listings, setListings] = useState([]);
  const [assets, setAssets] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ asset_id: "", price_usd: 9.99, description: "" });
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const { data } = await api.get("/marketplace");
      setListings(data);
      if (user) {
        const a = await api.get("/meme-assets");
        setAssets(a.data.filter((x) => x.canon_approved));
      }
    } finally { setLoading(false); }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [user]);

  async function submit(e) {
    e.preventDefault();
    try {
      await api.post("/marketplace", { ...form, price_usd: parseFloat(form.price_usd) });
      toast.success("Listed on marketplace");
      setShowCreate(false);
      setForm({ asset_id: "", price_usd: 9.99, description: "" });
      load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail) || e.message); }
  }

  async function delist(id) {
    try { await api.delete(`/marketplace/${id}`); toast.success("Delisted"); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail) || e.message); }
  }

  return (
    <div className="space-y-5" data-testid="marketplace-page">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <div className="pmos-eyebrow mb-1">Marketplace</div>
          <h1 className="pmos-h2 flex items-center gap-2"><Store size={26} className="text-cyan-300" strokeWidth={1.5}/>Canon Listings</h1>
          <p className="text-slate-400 text-sm mt-1">Canon-approved Meme Assets only. Safety engine vetoes apply.</p>
        </div>
        {user ? (
          <button onClick={() => setShowCreate(!showCreate)} className="pmos-btn-primary flex items-center gap-1.5" data-testid="new-listing-button">
            <Plus size={12} /> List an asset
          </button>
        ) : (
          <Link to="/login" className="pmos-btn-secondary" data-testid="market-login-link">Login to list</Link>
        )}
      </div>

      {showCreate && (
        <form onSubmit={submit} className="pmos-card-elevated p-5 space-y-3" data-testid="new-listing-form">
          <div>
            <label className="pmos-label">Asset (canon-approved)</label>
            <select required className="pmos-input" value={form.asset_id} onChange={(e) => setForm({ ...form, asset_id: e.target.value })} data-testid="listing-asset-select">
              <option value="">— select —</option>
              {assets.map((a) => <option key={a.id} value={a.id}>{a.seed} · {a.rarity?.tier}</option>)}
            </select>
            {assets.length === 0 && <div className="pmos-meta mt-1">No canon-approved assets yet. Approve one first.</div>}
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <label className="pmos-label">Price (USD)</label>
              <input required type="number" step="0.01" min="0" className="pmos-input" value={form.price_usd} onChange={(e) => setForm({ ...form, price_usd: e.target.value })} data-testid="listing-price-input"/>
            </div>
            <div>
              <label className="pmos-label">Description (optional)</label>
              <input className="pmos-input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="pmos-btn-primary" data-testid="submit-listing">Publish listing</button>
            <button type="button" onClick={() => setShowCreate(false)} className="pmos-btn-secondary">Cancel</button>
          </div>
        </form>
      )}

      {loading && <div className="pmos-meta">Loading…</div>}
      {!loading && listings.length === 0 && (
        <div className="pmos-card p-8 text-center pmos-meta" data-testid="market-empty">No listings yet. Approve a canon asset and list it.</div>
      )}

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {listings.map((l) => (
          <article key={l.id} className="pmos-card p-4 flex flex-col" data-testid={`listing-${l.id.slice(0,8)}`}>
            <div className="flex items-center justify-between mb-2">
              <span className="pmos-badge pmos-badge-magenta">{l.rarity?.tier}</span>
              <span className="font-display font-bold text-cyan-300 text-xl">${l.price_usd}</span>
            </div>
            <div className="font-display text-lg text-white truncate">{l.seed}</div>
            {l.description && <p className="text-slate-400 text-xs mt-1 line-clamp-2">{l.description}</p>}
            <div className="pmos-meta mt-1">seller {l.seller_email}</div>
            <div className="pmos-meta">listed {new Date(l.created_at).toLocaleDateString()}</div>
            <div className="mt-3 flex gap-2">
              <Link to={`/public/${l.asset_id}`} className="pmos-btn-secondary flex-1 text-center" data-testid={`view-public-${l.id.slice(0,8)}`}>View canon page</Link>
              {user?.email === l.seller_email && (
                <button onClick={() => delist(l.id)} className="pmos-btn-danger flex items-center gap-1" data-testid={`delist-${l.id.slice(0,8)}`}>
                  <Trash2 size={11}/> Delist
                </button>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
