import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { ShieldQuestion, Plus, Scale } from "lucide-react";
import { toast } from "sonner";

export default function Governance() {
  const { user } = useAuth();
  const [proposals, setProposals] = useState([]);
  const [amendments, setAmendments] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", target_asset_id: "", proposal_type: "canon_approval" });
  const [amendForm, setAmendForm] = useState({ title: "", description: "" });

  async function load() {
    const [p, a] = await Promise.all([api.get("/governance/proposals"), api.get("/governance/amendments")]);
    setProposals(p.data);
    setAmendments(a.data);
  }
  useEffect(() => { load(); }, []);

  async function createProposal(e) {
    e.preventDefault();
    try {
      await api.post("/governance/proposals", form);
      toast.success("Proposal created");
      setShowCreate(false);
      setForm({ title: "", description: "", target_asset_id: "", proposal_type: "canon_approval" });
      load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail) || e.message); }
  }

  async function vote(proposal_id, choice) {
    try {
      await api.post("/governance/vote", { proposal_id, choice });
      toast.success(`Vote cast: ${choice}`);
      load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail) || e.message); }
  }

  async function addAmendment(e) {
    e.preventDefault();
    try {
      await api.post("/governance/amendments", amendForm);
      toast.success("Amendment added");
      setAmendForm({ title: "", description: "" });
      load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail) || e.message); }
  }

  if (user === undefined) return <div className="pmos-meta">Loading…</div>;

  if (!user) {
    return (
      <div className="pmos-card-elevated p-10 max-w-xl mx-auto text-center" data-testid="governance-login-required">
        <ShieldQuestion size={36} className="text-cyan-300 mx-auto mb-3" strokeWidth={1.4} />
        <h2 className="pmos-h2 mb-2">Operator Login Required</h2>
        <p className="text-slate-400 text-sm mb-5">
          Governance and economics actions are gated. Generation engines remain freely accessible to all visitors.
        </p>
        <Link to="/login" className="pmos-btn-primary inline-flex" data-testid="governance-login-link">Login to participate</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="governance-page">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <div className="pmos-eyebrow mb-1">Governance Panel</div>
          <h1 className="pmos-h2 flex items-center gap-2"><Scale size={26} className="text-cyan-300" strokeWidth={1.5}/>Proposals & Amendments</h1>
        </div>
        <button onClick={() => setShowCreate(!showCreate)} className="pmos-btn-primary flex items-center gap-1.5" data-testid="new-proposal-button">
          <Plus size={12} /> New Proposal
        </button>
      </div>

      {showCreate && (
        <form onSubmit={createProposal} className="pmos-card-elevated p-5 space-y-3" data-testid="new-proposal-form">
          <div>
            <label className="pmos-label">Title</label>
            <input required className="pmos-input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="proposal-title-input" />
          </div>
          <div>
            <label className="pmos-label">Description</label>
            <textarea required rows={3} className="pmos-input resize-y" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="proposal-description-input" />
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <label className="pmos-label">Target Asset ID (optional)</label>
              <input className="pmos-input" value={form.target_asset_id} onChange={(e) => setForm({ ...form, target_asset_id: e.target.value })} />
            </div>
            <div>
              <label className="pmos-label">Type</label>
              <select className="pmos-input" value={form.proposal_type} onChange={(e) => setForm({ ...form, proposal_type: e.target.value })}>
                <option value="canon_approval">canon_approval</option>
                <option value="constitution_amendment">constitution_amendment</option>
                <option value="parameter_change">parameter_change</option>
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="pmos-btn-primary" data-testid="submit-proposal-button">Submit</button>
            <button type="button" onClick={() => setShowCreate(false)} className="pmos-btn-secondary">Cancel</button>
          </div>
        </form>
      )}

      {/* Proposals */}
      <section>
        <h2 className="pmos-h3 mb-3">Active Proposals</h2>
        {proposals.length === 0 && <div className="pmos-card p-6 pmos-meta">No proposals yet.</div>}
        <div className="space-y-3">
          {proposals.map((p) => (
            <article key={p.id} className="pmos-card p-4" data-testid={`proposal-${p.id.slice(0, 8)}`}>
              <div className="flex items-start justify-between flex-wrap gap-2">
                <div>
                  <div className="font-display text-lg text-white">{p.title}</div>
                  <div className="pmos-meta mt-0.5">type {p.proposal_type} · by {p.created_by}</div>
                </div>
                <div className="flex gap-1">
                  <span className="pmos-badge pmos-badge-success">yes {p.tally?.yes || 0}</span>
                  <span className="pmos-badge pmos-badge-error">no {p.tally?.no || 0}</span>
                  <span className="pmos-badge pmos-badge-idle">abstain {p.tally?.abstain || 0}</span>
                </div>
              </div>
              <p className="text-slate-400 text-sm mt-2 leading-relaxed">{p.description}</p>
              {p.target_asset_id && <div className="pmos-meta mt-1">target asset · {p.target_asset_id}</div>}
              <div className="flex gap-2 mt-3">
                <button onClick={() => vote(p.id, "yes")} className="pmos-btn-primary" data-testid={`vote-yes-${p.id.slice(0,8)}`}>Vote Yes</button>
                <button onClick={() => vote(p.id, "no")} className="pmos-btn-danger" data-testid={`vote-no-${p.id.slice(0,8)}`}>Vote No</button>
                <button onClick={() => vote(p.id, "abstain")} className="pmos-btn-secondary" data-testid={`vote-abstain-${p.id.slice(0,8)}`}>Abstain</button>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* Amendments */}
      <section>
        <div className="flex justify-between items-end mb-3">
          <h2 className="pmos-h3">Constitution Amendments</h2>
          <span className="pmos-meta">{amendments.length} on record</span>
        </div>
        {user.role === "admin" && (
          <form onSubmit={addAmendment} className="pmos-card-elevated p-4 mb-3 space-y-2" data-testid="amendment-form">
            <div className="pmos-eyebrow">Admin · add amendment</div>
            <input required placeholder="Title" className="pmos-input" value={amendForm.title} onChange={(e) => setAmendForm({ ...amendForm, title: e.target.value })} data-testid="amendment-title-input" />
            <textarea required placeholder="Body" rows={2} className="pmos-input resize-y" value={amendForm.description} onChange={(e) => setAmendForm({ ...amendForm, description: e.target.value })} data-testid="amendment-body-input" />
            <button type="submit" className="pmos-btn-primary" data-testid="submit-amendment">Ratify Amendment</button>
          </form>
        )}
        <div className="space-y-2">
          {amendments.length === 0 && <div className="pmos-card p-6 pmos-meta">No amendments yet.</div>}
          {amendments.map((a) => (
            <div key={a.id} className="pmos-card p-3" data-testid={`amendment-${a.id.slice(0,8)}`}>
              <div className="flex items-center justify-between">
                <div className="font-display text-white">{a.title}</div>
                <span className="pmos-meta">v{a.version}</span>
              </div>
              <p className="text-slate-400 text-sm mt-1">{a.body}</p>
              <div className="pmos-meta mt-1">by {a.created_by} · {new Date(a.created_at).toLocaleString()}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
