import type { AnalysisResponse, BuildResponse } from "../types";

interface Props {
  analysis: AnalysisResponse | null;
  build: BuildResponse | null;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[11px] uppercase tracking-wide text-slate-400">{label}</span>
      <span className="text-lg font-semibold text-ink">{value}</span>
    </div>
  );
}

export function MetaHeader({ analysis, build }: Props) {
  if (!analysis) return null;
  return (
    <div className="grid grid-cols-2 gap-4 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-4 lg:grid-cols-6">
      <Stat label="Key" value={analysis.key} />
      <Stat label="Tempo" value={`${Math.round(analysis.bpm)} BPM`} />
      <Stat label="Time Sig" value={analysis.time_signature} />
      <Stat label="Duration" value={`${analysis.duration_sec.toFixed(1)}s`} />
      <Stat label="Measures" value={build ? String(build.measure_count) : "—"} />
      <Stat
        label="Song Form"
        value="—"
      />
      <div className="col-span-2 flex flex-col sm:col-span-4 lg:col-span-6">
        <span className="text-[11px] uppercase tracking-wide text-slate-400">Backends</span>
        <span className="text-xs text-slate-500">
          {Object.entries(analysis.backends)
            .map(([k, v]) => `${k}: ${v}`)
            .join("  ·  ")}
        </span>
      </div>
    </div>
  );
}
