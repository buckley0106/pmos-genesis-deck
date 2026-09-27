import { useEffect, useState } from "react";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { ShieldAlert, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

export default function SafetyManager() {
  const { user } = useAuth();
  const [words, setWords] = useState([]);
  const [newWord, setNewWord] = useState("");

  async function load() {
    if (user?.role !== "admin") return;
    try {
      const { data } = await api.get("/safety/blocklist");
      setWords(data.words || []);
    } catch (e) { /* ignore */ }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [user]);

  if (user?.role !== "admin") return null;

  async function add(e) {
    e.preventDefault();
    const w = newWord.trim().toLowerCase();
    if (!w) return;
    try {
      const { data } = await api.post("/safety/blocklist", { word: w });
      setWords(data.words || []);
      setNewWord("");
      toast.success(`Added "${w}" to Safety blocklist`);
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail) || e.message); }
  }

  async function remove(word) {
    try {
      const { data } = await api.delete(`/safety/blocklist/${encodeURIComponent(word)}`);
      setWords(data.words || []);
      toast.success(`Removed "${word}"`);
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail) || e.message); }
  }

  return (
    <div className="pmos-card p-4" data-testid="safety-manager">
      <div className="flex items-center justify-between mb-3">
        <h2 className="pmos-h3 flex items-center gap-2">
          <ShieldAlert size={18} strokeWidth={1.5} className="text-fuchsia-400"/>
          Safety Blocklist <span className="pmos-badge pmos-badge-magenta ml-1">admin</span>
        </h2>
        <span className="pmos-meta">{words.length} word{words.length !== 1 && "s"}</span>
      </div>
      <p className="text-slate-400 text-xs mb-3 leading-relaxed">
        Words matched (case-insensitive) in a seed's text will trip the Safety engine —
        blocking canon approval and marketplace listing for that asset. Changes are hot,
        no redeploy needed.
      </p>
      <form onSubmit={add} className="flex gap-2 mb-3">
        <input
          className="pmos-input flex-1"
          placeholder="add a blocked word (e.g. spam-slur)"
          value={newWord}
          onChange={(e) => setNewWord(e.target.value)}
          data-testid="safety-word-input"
        />
        <button type="submit" className="pmos-btn-primary flex items-center gap-1.5" data-testid="safety-word-add">
          <Plus size={12}/> Block
        </button>
      </form>
      <div className="flex flex-wrap gap-1.5">
        {words.length === 0 && <span className="pmos-meta">(empty — defaults will re-seed on next restart)</span>}
        {words.map((w) => (
          <span key={w} className="pmos-badge pmos-badge-error flex items-center gap-1" data-testid={`safety-word-${w}`}>
            {w}
            <button onClick={() => remove(w)} className="text-rose-300 hover:text-white" aria-label={`Remove ${w}`} data-testid={`safety-word-remove-${w}`}>
              <Trash2 size={10}/>
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}
