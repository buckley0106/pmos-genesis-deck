import { useState } from "react";
import { api } from "@/lib/api";
import { JsonViewer } from "@/components/JsonViewer";
import { Sigma } from "lucide-react";

const fields = [
  { key: "legendary_traits", label: "Legendary traits", min: 0, max: 10 },
  { key: "rare_traits", label: "Rare traits", min: 0, max: 15 },
  { key: "uncommon_traits", label: "Uncommon traits", min: 0, max: 20 },
  { key: "common_traits", label: "Common traits", min: 0, max: 30 },
];

export default function RarityCalculator() {
  const [input, setInput] = useState({ trait_count: 8, legendary_traits: 1, rare_traits: 2, uncommon_traits: 3, common_traits: 2, canon_status: false });
  const [result, setResult] = useState(null);

  async function calc() {
    const { data } = await api.post("/rarity/calculate", input);
    setResult(data);
  }

  return (
    <div className="space-y-5" data-testid="rarity-page">
      <div>
        <div className="pmos-eyebrow mb-1">Rarity Calculator</div>
        <h1 className="pmos-h2 flex items-center gap-2"><Sigma size={26} strokeWidth={1.5} className="text-cyan-300"/>Score Composer</h1>
        <p className="text-slate-400 text-sm mt-1">Σ(traits × weight) × (1.5 if canon)</p>
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        <div className="pmos-card-elevated p-5 space-y-4">
          {fields.map((f) => (
            <div key={f.key}>
              <div className="flex justify-between items-center mb-1">
                <label className="pmos-label">{f.label}</label>
                <span className="font-mono text-cyan-300 text-sm" data-testid={`rarity-value-${f.key}`}>{input[f.key]}</span>
              </div>
              <input
                type="range"
                min={f.min}
                max={f.max}
                value={input[f.key]}
                onChange={(e) => setInput({ ...input, [f.key]: parseInt(e.target.value) })}
                className="w-full accent-cyan-400"
                data-testid={`rarity-slider-${f.key}`}
              />
            </div>
          ))}
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={input.canon_status} onChange={(e) => setInput({ ...input, canon_status: e.target.checked })} data-testid="rarity-canon-checkbox" />
            <span className="font-display uppercase tracking-widest text-xs text-cyan-300">Canon approved (×1.5 bonus)</span>
          </label>
          <button onClick={calc} className="pmos-btn-primary w-full" data-testid="rarity-calculate-button">Calculate</button>
        </div>

        <div className="space-y-4">
          {result && (
            <div className="pmos-card-elevated p-6 text-center" data-testid="rarity-result">
              <div className="pmos-eyebrow mb-1">Rarity Tier</div>
              <div className="font-display font-bold text-5xl text-white uppercase" data-testid="rarity-tier">{result.tier}</div>
              <div className="font-mono text-cyan-300 text-2xl mt-2" data-testid="rarity-score">{result.score} pts</div>
              <div className="pmos-divider my-4" />
              <div className="grid grid-cols-2 gap-2 text-left">
                {Object.entries(result.weights).map(([k, v]) => (
                  <div key={k} className="font-mono text-xs">
                    <span className="text-slate-500">{k}</span>
                    <span className="text-fuchsia-400 ml-2">× {v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {result && <JsonViewer data={result} label="Calc result" testId="rarity-json" />}
        </div>
      </div>
    </div>
  );
}
