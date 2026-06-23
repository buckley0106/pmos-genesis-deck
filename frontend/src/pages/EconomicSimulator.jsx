import { useState } from "react";
import { api } from "@/lib/api";
import { JsonViewer } from "@/components/JsonViewer";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { Activity } from "lucide-react";

export default function EconomicSimulator() {
  const [input, setInput] = useState({
    initial_supply: 1_000_000,
    mint_cost: 0.01,
    demand_factor: 1.5,
    burn_rate: 0.02,
    horizon_months: 12,
  });
  const [result, setResult] = useState(null);

  async function run() {
    const { data } = await api.post("/economic/simulate", input);
    setResult(data);
  }

  const setNum = (k, v) => setInput({ ...input, [k]: v });

  return (
    <div className="space-y-5" data-testid="economic-page">
      <div>
        <div className="pmos-eyebrow mb-1">Economic Simulator</div>
        <h1 className="pmos-h2 flex items-center gap-2"><Activity size={26} className="text-cyan-300" strokeWidth={1.5}/>Tokenomics Projection</h1>
      </div>

      <div className="grid lg:grid-cols-[380px_1fr] gap-5">
        <div className="pmos-card-elevated p-5 space-y-3">
          {[
            ["initial_supply", "Initial supply", 0.01, 1, 0],
            ["mint_cost", "Mint cost (USD)", 0, 0.001, 6],
            ["demand_factor", "Demand factor", 0, 0.05, 2],
            ["burn_rate", "Burn rate", 0, 0.001, 4],
            ["horizon_months", "Horizon (months)", 1, 1, 0],
          ].map(([k, label, _min, step, dec]) => (
            <div key={k}>
              <label className="pmos-label">{label}</label>
              <input
                type="number"
                step={step}
                value={input[k]}
                onChange={(e) => setNum(k, k === "horizon_months" ? parseInt(e.target.value || 0) : parseFloat(e.target.value || 0))}
                className="pmos-input"
                data-testid={`econ-input-${k}`}
              />
            </div>
          ))}
          <button onClick={run} className="pmos-btn-primary w-full" data-testid="econ-run-button">Run Simulation</button>
        </div>

        <div className="space-y-4">
          {result && (
            <>
              <div className="grid sm:grid-cols-3 gap-3">
                <Stat label="Final supply" value={result.rows.at(-1)?.supply?.toLocaleString()} />
                <Stat label="Final price" value={`$${result.rows.at(-1)?.price_usd?.toFixed(6)}`} />
                <Stat label="Final mcap" value={`$${result.rows.at(-1)?.market_cap?.toLocaleString()}`} accent="fuchsia" />
              </div>
              <div className="pmos-card-elevated p-4" style={{ height: 320 }} data-testid="econ-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={result.rows}>
                    <CartesianGrid stroke="#1A1D2E" strokeDasharray="2 4" />
                    <XAxis dataKey="month" stroke="#4A4D6B" fontSize={11} />
                    <YAxis stroke="#4A4D6B" fontSize={11} yAxisId="left" />
                    <YAxis stroke="#4A4D6B" fontSize={11} yAxisId="right" orientation="right" />
                    <Tooltip contentStyle={{ background: "#0B0C15", border: "1px solid #1A1D2E", color: "#E2E8F0", fontFamily: "JetBrains Mono" }} />
                    <Legend wrapperStyle={{ fontFamily: "Rajdhani", textTransform: "uppercase", letterSpacing: 2, fontSize: 11 }} />
                    <Line yAxisId="left" type="monotone" dataKey="supply" stroke="#00F0FF" strokeWidth={2} dot={false} />
                    <Line yAxisId="right" type="monotone" dataKey="price_usd" stroke="#FF00FF" strokeWidth={2} dot={false} />
                    <Line yAxisId="right" type="monotone" dataKey="market_cap" stroke="#00FF66" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <JsonViewer data={result} label="Simulation result" testId="econ-result-json" maxHeight={320} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, accent = "cyan" }) {
  const c = accent === "fuchsia" ? "text-fuchsia-300" : "text-cyan-300";
  return (
    <div className="pmos-card p-4">
      <div className="pmos-eyebrow">{label}</div>
      <div className={`font-display font-bold text-2xl ${c} mt-1`}>{value}</div>
    </div>
  );
}
