import { useMemo, useState } from "react";

interface Props {
  measureCount: number;
  busy: boolean;
  notice: string | null;
  onRegenerate: (opts: {
    measures: number[];
    pitch_sensitivity?: number;
    quantize_division?: number;
  }) => void;
}

const DIVISIONS = [8, 16, 32];

export function MeasureInspector({ measureCount, busy, notice, onRegenerate }: Props) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [sensitivity, setSensitivity] = useState(0.5);
  const [division, setDivision] = useState(16);

  const numbers = useMemo(
    () => Array.from({ length: measureCount }, (_, i) => i + 1),
    [measureCount],
  );

  function toggle(n: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(n)) next.delete(n);
      else next.add(n);
      return next;
    });
  }

  const chosen = [...selected].sort((a, b) => a - b);

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink">마디 검수 · 부분 재분석</h2>
        {chosen.length > 0 && (
          <button
            onClick={() => setSelected(new Set())}
            className="text-xs text-slate-400 hover:text-slate-600"
          >
            선택 해제
          </button>
        )}
      </div>

      <p className="mb-2 text-xs text-slate-500">
        오인식된 마디를 선택하면 해당 구간만 다시 분석하여 악보를 패치합니다.
      </p>

      <div className="mb-3 flex flex-wrap gap-1">
        {numbers.map((n) => (
          <button
            key={n}
            onClick={() => toggle(n)}
            className={`h-8 w-8 rounded text-xs font-medium transition ${
              selected.has(n)
                ? "bg-emerald-600 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {n}
          </button>
        ))}
      </div>

      <div className="mb-3 grid grid-cols-2 gap-3 text-xs text-slate-600">
        <label className="flex flex-col gap-1">
          피치 감도 {sensitivity.toFixed(2)}
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={sensitivity}
            onChange={(e) => setSensitivity(Number(e.target.value))}
            className="accent-emerald-600"
          />
        </label>
        <label className="flex flex-col gap-1">
          양자화 단위
          <select
            value={division}
            onChange={(e) => setDivision(Number(e.target.value))}
            className="rounded border border-slate-300 px-2 py-1"
          >
            {DIVISIONS.map((d) => (
              <option key={d} value={d}>
                1/{d} 음표
              </option>
            ))}
          </select>
        </label>
      </div>

      <button
        onClick={() =>
          onRegenerate({
            measures: chosen,
            pitch_sensitivity: sensitivity,
            quantize_division: division,
          })
        }
        disabled={busy || chosen.length === 0}
        className="w-full rounded-md bg-ink py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        {busy
          ? "재분석 중…"
          : chosen.length > 0
            ? `마디 ${chosen.join(", ")} 재분석`
            : "마디를 선택하세요"}
      </button>

      {notice && <p className="mt-2 text-xs text-emerald-700">✅ {notice}</p>}
    </div>
  );
}
