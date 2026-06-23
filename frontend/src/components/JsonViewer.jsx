import { useState } from "react";
import { Copy, Check } from "lucide-react";

function renderValue(value, depth = 0) {
  if (value === null) return <span className="jv-null">null</span>;
  if (typeof value === "boolean") return <span className="jv-bool">{String(value)}</span>;
  if (typeof value === "number") return <span className="jv-number">{value}</span>;
  if (typeof value === "string") return <span className="jv-string">{`"${value}"`}</span>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-slate-500">[]</span>;
    return (
      <span>
        <span className="text-slate-500">[</span>
        <div style={{ paddingLeft: 16 }}>
          {value.map((v, i) => (
            <div key={i}>
              {renderValue(v, depth + 1)}
              {i < value.length - 1 && <span className="text-slate-500">,</span>}
            </div>
          ))}
        </div>
        <span className="text-slate-500">]</span>
      </span>
    );
  }
  if (typeof value === "object") {
    const entries = Object.entries(value);
    if (entries.length === 0) return <span className="text-slate-500">{"{}"}</span>;
    return (
      <span>
        <span className="text-slate-500">{"{"}</span>
        <div style={{ paddingLeft: 16 }}>
          {entries.map(([k, v], i) => (
            <div key={k}>
              <span className="jv-key">{`"${k}"`}</span>
              <span className="text-slate-500">: </span>
              {renderValue(v, depth + 1)}
              {i < entries.length - 1 && <span className="text-slate-500">,</span>}
            </div>
          ))}
        </div>
        <span className="text-slate-500">{"}"}</span>
      </span>
    );
  }
  return <span>{String(value)}</span>;
}

export function JsonViewer({ data, label, testId = "json-viewer", maxHeight = 480 }) {
  const [copied, setCopied] = useState(false);
  const text = JSON.stringify(data, null, 2);

  function copy() {
    navigator.clipboard?.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  }

  return (
    <div className="pmos-card relative" data-testid={testId}>
      <div className="flex items-center justify-between px-3 py-2 border-b border-[#1A1D2E]">
        <span className="pmos-eyebrow">{label || "JSON"}</span>
        <button
          onClick={copy}
          className="text-slate-400 hover:text-cyan-300 transition-colors"
          aria-label="Copy JSON"
          data-testid={`${testId}-copy`}
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
        </button>
      </div>
      <div className="p-3 overflow-auto font-mono text-xs leading-relaxed" style={{ maxHeight }}>
        {renderValue(data)}
      </div>
    </div>
  );
}
