import type { OpenSheetMusicDisplay } from "opensheetmusicdisplay";
import { useCallback, useEffect, useState } from "react";
import { api } from "./api/client";
import { ScorePlayer } from "./audio/player";
import { MetaHeader } from "./components/MetaHeader";
import { PlayerBar } from "./components/PlayerBar";
import { ScoreView } from "./components/ScoreView";
import { UploadPanel } from "./components/UploadPanel";
import { usePipeline } from "./hooks/usePipeline";
import type { BackendStatus } from "./types";

const STATUS_ICON: Record<string, string> = { run: "⏳", ok: "✅", fail: "❌", skip: "➖" };

export default function App() {
  const pipe = usePipeline();
  const [osmd, setOsmd] = useState<OpenSheetMusicDisplay | null>(null);
  const [player, setPlayer] = useState<ScorePlayer | null>(null);
  const [backends, setBackends] = useState<BackendStatus | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);

  useEffect(() => {
    api.backends().then(setBackends).catch(() => setBackends(null));
  }, []);

  const running = pipe.phase === "running";

  const handleReady = useCallback((instance: OpenSheetMusicDisplay) => {
    setOsmd(instance);
    setRenderError(null);
  }, []);

  useEffect(() => {
    if (!osmd || !pipe.analysis) {
      setPlayer(null);
      return;
    }
    const p = new ScorePlayer(osmd, pipe.analysis);
    setPlayer(p);
    return () => p.dispose();
  }, [osmd, pipe.analysis]);

  return (
    <div className="mx-auto max-w-6xl p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-ink">AutoScore</h1>
        <p className="text-sm text-slate-500">
          오디오 · Stem · 악보 이미지 → 인터랙티브 리드 시트
        </p>
        {backends && (
          <p className="mt-1 text-xs text-slate-400">
            분석 백엔드 — melody: {backends.selected.melody} · rhythm: {backends.selected.rhythm} ·
            harmony: {backends.selected.harmony}
          </p>
        )}
      </header>

      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <div className="space-y-4">
          <UploadPanel
            disabled={running}
            onRunSingle={pipe.runSingle}
            onRunStems={pipe.runStems}
            onRunImage={pipe.runImage}
          />

          {pipe.steps.length > 0 && (
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="mb-2 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-ink">파이프라인</h2>
                {pipe.phase !== "running" && (
                  <button
                    onClick={pipe.reset}
                    className="text-xs text-slate-400 hover:text-slate-600"
                  >
                    초기화
                  </button>
                )}
              </div>
              <ol className="space-y-1 text-sm">
                {pipe.steps.map((s) => (
                  <li key={s.key} className="flex flex-col">
                    <span>
                      {STATUS_ICON[s.status]} {s.label}
                    </span>
                    {s.detail && <span className="pl-5 text-xs text-rose-600">{s.detail}</span>}
                  </li>
                ))}
              </ol>
              {pipe.error && (
                <p className="mt-2 rounded bg-rose-50 p-2 text-xs text-rose-700">{pipe.error}</p>
              )}
            </div>
          )}

          {pipe.build && pipe.build.warnings.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
              <p className="mb-1 font-semibold">빌드 경고</p>
              <ul className="list-disc pl-4">
                {pipe.build.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <MetaHeader analysis={pipe.analysis} build={pipe.build} />
          {player && <PlayerBar player={player} />}
          {renderError && (
            <p className="rounded bg-rose-50 p-2 text-xs text-rose-700">
              악보 렌더 오류: {renderError}
            </p>
          )}
          <ScoreView xml={pipe.xml} onReady={handleReady} onError={setRenderError} />
        </div>
      </div>
    </div>
  );
}
