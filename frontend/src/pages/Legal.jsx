import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ScrollText, Download, ShieldCheck } from "lucide-react";

export default function Legal() {
  const [docs, setDocs] = useState(null);
  useEffect(() => { (async () => {
    const { data } = await api.get("/docs/all");
    setDocs(data);
  })(); }, []);

  if (!docs) return <div className="pmos-meta">Loading…</div>;
  const L = docs.legal;

  function download(name, body) {
    const blob = new Blob([body], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = name; a.click();
    URL.revokeObjectURL(url);
  }

  const docsList = [
    { key: "copyright", title: "Copyright Notice", body: L.copyright, file: "PMOS-WMEU-COPYRIGHT.txt" },
    { key: "trademark", title: "Trademark Notice", body: L.trademark, file: "PMOS-WMEU-TRADEMARK.txt" },
    { key: "license", title: "Proprietary License", body: L.license, file: "PMOS-WMEU-LICENSE.txt" },
    { key: "to_whom_it_may_concern", title: "To Whom It May Concern", body: L.to_whom_it_may_concern, file: "PMOS-WMEU-TO-WHOM-IT-MAY-CONCERN.txt" },
    { key: "universal_hub_clause", title: "Universal Hub Clause", body: L.universal_hub_clause, file: "PMOS-WMEU-UNIVERSAL-HUB.txt" },
  ];

  return (
    <div className="space-y-6" data-testid="legal-page">
      <div className="pmos-card-elevated p-6 sm:p-8 relative pmos-corner">
        <div className="flex items-center gap-3 mb-2">
          <ShieldCheck size={26} className="text-cyan-300" strokeWidth={1.5}/>
          <div>
            <div className="pmos-eyebrow">PMOS • WMEU Legal Pack</div>
            <h1 className="pmos-h2">Ownership & Protections</h1>
          </div>
        </div>
        <p className="text-slate-400 text-sm leading-relaxed max-w-3xl">
          The following instruments establish authorship, ownership, trademark protection, and the universal-hub
          designation for PMOS • WMEU — Meme Civilization Engine, attributed to <span className="text-cyan-300">Patrick Buckley</span>,
          year <span className="text-cyan-300">2026</span>. All marks and outputs are reserved pending the formal
          registration of <span className="text-fuchsia-300">Buckley Labs LLC</span>.
        </p>
        <div className="pmos-divider my-4" />
        <div className="grid sm:grid-cols-2 gap-3">
          <Pill label="Owner" value="Patrick Buckley" />
          <Pill label="Entity (pending)" value="Buckley Labs LLC" accent="fuchsia"/>
          <Pill label="Marks" value="P.BUCK · PMOS · WMEU · Waboot Meme Engine Universe" />
          <Pill label="Year" value="2026" accent="fuchsia"/>
        </div>
      </div>

      <section className="space-y-3">
        <h2 className="pmos-h3 flex items-center gap-2"><ScrollText size={20} className="text-cyan-300" strokeWidth={1.5}/>Documents</h2>
        {docsList.map((d) => (
          <article key={d.key} className="pmos-card p-5" data-testid={`legal-${d.key}`}>
            <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
              <h3 className="pmos-h3">{d.title}</h3>
              <button onClick={() => download(d.file, d.body)} className="pmos-btn-secondary flex items-center gap-1.5" data-testid={`legal-download-${d.key}`}>
                <Download size={12} /> Download .txt
              </button>
            </div>
            <pre className="whitespace-pre-wrap font-mono text-xs text-slate-300 leading-relaxed">{d.body}</pre>
          </article>
        ))}
      </section>

      <section className="pmos-card p-5" data-testid="legal-constitution">
        <h2 className="pmos-h3 mb-2">{docs.constitution.title}</h2>
        <pre className="whitespace-pre-wrap font-mono text-xs text-slate-300 leading-relaxed">{docs.constitution.body}</pre>
      </section>
    </div>
  );
}

function Pill({ label, value, accent = "cyan" }) {
  const c = accent === "fuchsia" ? "border-fuchsia-500/30 text-fuchsia-300" : "border-cyan-500/30 text-cyan-300";
  return (
    <div className={`pmos-card p-3 ${c} border`}>
      <div className="pmos-eyebrow">{label}</div>
      <div className="font-display text-sm mt-0.5 text-white">{value}</div>
    </div>
  );
}
