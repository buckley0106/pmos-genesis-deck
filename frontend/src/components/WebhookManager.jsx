import { useEffect, useState } from "react";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Webhook, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

const EVENT_OPTIONS = ["engine_error", "canon_approved", "engine_run", "proposal_created", "vote_cast", "marketplace_listed"];

export default function WebhookManager() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ url: "", label: "default", event_types: ["engine_error", "canon_approved"] });

  async function load() {
    if (user?.role !== "admin") return;
    const { data } = await api.get("/webhooks");
    setItems(data);
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [user]);

  if (user?.role !== "admin") return null;

  async function add(e) {
    e.preventDefault();
    try {
      await api.post("/webhooks", form);
      toast.success("Webhook added");
      setForm({ url: "", label: "default", event_types: ["engine_error", "canon_approved"] });
      load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail) || e.message); }
  }

  async function del(id) {
    await api.delete(`/webhooks/${id}`); toast.success("Webhook removed"); load();
  }

  function toggleEvent(ev) {
    setForm((f) => ({ ...f, event_types: f.event_types.includes(ev) ? f.event_types.filter((x) => x !== ev) : [...f.event_types, ev] }));
  }

  return (
    <div className="pmos-card p-4" data-testid="webhook-manager">
      <div className="flex items-center justify-between mb-3">
        <h2 className="pmos-h3 flex items-center gap-2"><Webhook size={18} strokeWidth={1.5} className="text-cyan-300"/>Webhooks (admin)</h2>
        <span className="pmos-meta">{items.length} configured</span>
      </div>
      <form onSubmit={add} className="space-y-2 mb-3">
        <input className="pmos-input" placeholder="https://discord.com/api/webhooks/… or Slack URL" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} required data-testid="webhook-url-input"/>
        <input className="pmos-input" placeholder="label" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} />
        <div className="flex flex-wrap gap-1.5">
          {EVENT_OPTIONS.map((ev) => (
            <button type="button" key={ev} onClick={() => toggleEvent(ev)} data-testid={`event-toggle-${ev}`}
              className={`pmos-badge ${form.event_types.includes(ev) ? "pmos-badge-running" : "pmos-badge-idle"}`}>{ev}</button>
          ))}
        </div>
        <button type="submit" className="pmos-btn-primary flex items-center gap-1.5" data-testid="webhook-add-button"><Plus size={12}/> Add webhook</button>
      </form>
      <div className="space-y-2">
        {items.map((w) => (
          <div key={w.id} className="border border-[#1A1D2E] p-2 flex items-start justify-between gap-2" data-testid={`webhook-${w.id.slice(0,8)}`}>
            <div className="flex-1 min-w-0">
              <div className="font-display text-sm text-white">{w.label}</div>
              <div className="font-mono text-[10px] text-slate-500 truncate">{w.url}</div>
              <div className="flex gap-1 mt-1 flex-wrap">
                {w.event_types.map((ev) => <span key={ev} className="pmos-badge pmos-badge-idle">{ev}</span>)}
              </div>
            </div>
            <button onClick={() => del(w.id)} className="text-rose-400 hover:text-rose-300" data-testid={`webhook-delete-${w.id.slice(0,8)}`}><Trash2 size={14}/></button>
          </div>
        ))}
      </div>
    </div>
  );
}
