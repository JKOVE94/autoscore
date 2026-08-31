import { useEffect, useState } from "react";
import type { ScorePlayer, PlaybackState } from "../audio/player";

interface Props {
  player: ScorePlayer | null;
}

function fmt(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function PlayerBar({ player }: Props) {
  const [state, setState] = useState<PlaybackState>("stopped");
  const [elapsed, setElapsed] = useState(0);
  const [rate, setRate] = useState(1);

  useEffect(() => {
    if (!player) return;
    player.setCallbacks({
      onTick: setElapsed,
      onStateChange: setState,
      onEnd: () => setElapsed(0),
    });
    setRate(player.getRate());
    setState(player.playbackState);
    return () => player.pause();
  }, [player]);

  if (!player) return null;
  const duration = player.durationSec;

  return (
    <div className="flex flex-wrap items-center gap-4 rounded-lg border border-slate-200 bg-white p-4">
      <button
        onClick={() => (state === "playing" ? player.pause() : void player.play())}
        className="rounded-md bg-ink px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
      >
        {state === "playing" ? "⏸ 일시정지" : "▶ 재생"}
      </button>
      <button
        onClick={() => player.stop()}
        className="rounded-md bg-slate-100 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-200"
      >
        ⏹ 정지
      </button>

      <div className="flex flex-1 items-center gap-3">
        <span className="w-12 text-right text-xs tabular-nums text-slate-500">{fmt(elapsed)}</span>
        <input
          type="range"
          min={0}
          max={Math.max(duration, 0.1)}
          step={0.05}
          value={Math.min(elapsed, duration)}
          onChange={(e) => player.seek(Number(e.target.value))}
          className="flex-1 accent-emerald-600"
        />
        <span className="w-12 text-xs tabular-nums text-slate-500">{fmt(duration)}</span>
      </div>

      <label className="flex items-center gap-2 text-xs text-slate-500">
        Tempo ×{rate.toFixed(2)}
        <input
          type="range"
          min={0.4}
          max={2}
          step={0.05}
          value={rate}
          onChange={(e) => {
            const r = Number(e.target.value);
            setRate(r);
            player.setRate(r);
          }}
          className="accent-ink"
        />
      </label>
    </div>
  );
}
