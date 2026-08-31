import type { CompressResponse } from "../types";

interface Props {
  jobId: string;
  compressed: CompressResponse | null;
  busy: boolean;
  view: "full" | "lead";
  onCompress: () => void;
  onView: (v: "full" | "lead") => void;
}

function download(name: string, xml: string) {
  const blob = new Blob([xml], { type: "application/vnd.recordare.musicxml+xml" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function FormCompressor({ jobId, compressed, busy, view, onCompress, onView }: Props) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="mb-2 text-sm font-semibold text-ink">리드 시트 축약 · 송 폼</h2>
      <p className="mb-3 text-xs text-slate-500">
        반복 구간을 도돌이표 · 1·2절 볼타 · D.S. al Coda 로 접어 축약 리드 시트를 만듭니다.
      </p>

      <button
        onClick={onCompress}
        disabled={busy}
        className="w-full rounded-md bg-ink py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:bg-slate-300"
      >
        {busy ? "분석 중…" : compressed ? "다시 축약" : "축약 리드 시트 생성"}
      </button>

      {compressed && (
        <div className="mt-3 space-y-2 text-xs">
          <div className="flex gap-1">
            <button
              onClick={() => onView("full")}
              className={`flex-1 rounded px-2 py-1 font-medium ${
                view === "full" ? "bg-slate-200 text-ink" : "bg-slate-50 text-slate-500"
              }`}
            >
              전체 악보
            </button>
            <button
              onClick={() => onView("lead")}
              className={`flex-1 rounded px-2 py-1 font-medium ${
                view === "lead" ? "bg-slate-200 text-ink" : "bg-slate-50 text-slate-500"
              }`}
            >
              축약 ({compressed.compressed_measures}마디)
            </button>
          </div>

          <p className="text-slate-500">
            {compressed.original_measures} → {compressed.compressed_measures} 마디
            {compressed.song_form && (
              <>
                {" · "}
                <span className="font-medium text-ink">폼: {compressed.song_form}</span>
              </>
            )}
          </p>

          <ul className="list-disc space-y-0.5 pl-4 text-slate-500">
            {compressed.operations.map((op) => (
              <li key={op}>{op}</li>
            ))}
          </ul>

          <button
            onClick={() => download(`${jobId}-lead-sheet.musicxml`, compressed.musicxml)}
            className="w-full rounded-md border border-slate-300 py-1.5 font-medium text-slate-600 hover:bg-slate-50"
          >
            ⬇ 축약 MusicXML 다운로드
          </button>
        </div>
      )}
    </div>
  );
}
