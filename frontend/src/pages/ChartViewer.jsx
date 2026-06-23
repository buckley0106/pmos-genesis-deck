import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell, Legend } from "recharts";
import { LineChart as IconChart } from "lucide-react";

const COLORS = ["#00F0FF", "#FF00FF", "#00FF66", "#FFB800", "#7000FF", "#FF003C"];

export default function ChartViewer() {
  const [rarity, setRarity] = useState([]);
  const [factions, setFactions] = useState([]);
  const [econ, setEcon] = useState([]);

  useEffect(() => { (async () => {
    const [r, f, e] = await Promise.all([
      api.get("/charts/rarity-distribution"),
      api.get("/charts/faction-breakdown"),
      api.get("/charts/economic-curve"),
    ]);
    setRarity(r.data); setFactions(f.data); setEcon(e.data);
  })(); }, []);

  return (
    <div className="space-y-5" data-testid="charts-page">
      <div>
        <div className="pmos-eyebrow mb-1">Chart Viewer</div>
        <h1 className="pmos-h2 flex items-center gap-2"><IconChart size={26} className="text-cyan-300" strokeWidth={1.5}/>Civilization Telemetry</h1>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <ChartCard title="Rarity Distribution" testId="chart-rarity">
          {rarity.length === 0 ? <Empty/> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={rarity}>
                <CartesianGrid stroke="#1A1D2E" strokeDasharray="2 4" />
                <XAxis dataKey="tier" stroke="#4A4D6B" fontSize={11} />
                <YAxis stroke="#4A4D6B" fontSize={11} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(0,240,255,0.05)" }}/>
                <Bar dataKey="count" fill="#00F0FF" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Faction Breakdown" testId="chart-factions">
          {factions.length === 0 ? <Empty/> : (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={factions} dataKey="count" nameKey="faction" outerRadius={90} stroke="#05050A">
                  {factions.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Legend wrapperStyle={legendStyle} />
                <Tooltip contentStyle={tooltipStyle}/>
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Latest Economic Curve" testId="chart-economic" className="lg:col-span-2">
          {econ.length === 0 ? <Empty/> : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={econ}>
                <CartesianGrid stroke="#1A1D2E" strokeDasharray="2 4" />
                <XAxis dataKey="month" stroke="#4A4D6B" fontSize={11} />
                <YAxis stroke="#4A4D6B" fontSize={11} />
                <Tooltip contentStyle={tooltipStyle}/>
                <Line type="monotone" dataKey="supply" stroke="#FF00FF" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>
    </div>
  );
}

function ChartCard({ title, children, testId, className = "" }) {
  return (
    <div className={`pmos-card-elevated p-4 ${className}`} data-testid={testId}>
      <div className="pmos-eyebrow mb-3">{title}</div>
      {children}
    </div>
  );
}
function Empty() { return <div className="h-[260px] grid place-items-center pmos-meta">no data yet — run PMOS</div>; }
const tooltipStyle = { background: "#0B0C15", border: "1px solid #1A1D2E", color: "#E2E8F0", fontFamily: "JetBrains Mono", fontSize: 11 };
const legendStyle = { fontFamily: "Rajdhani", textTransform: "uppercase", letterSpacing: 2, fontSize: 11 };
