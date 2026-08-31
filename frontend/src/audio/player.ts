import type { OpenSheetMusicDisplay } from "opensheetmusicdisplay";
import * as Tone from "tone";
import type { AnalysisResponse } from "../types";

export interface PlayerCallbacks {
  onTick?: (elapsedSec: number) => void;
  onStateChange?: (state: PlaybackState) => void;
  onEnd?: () => void;
}

export type PlaybackState = "stopped" | "playing" | "paused";

/**
 * Drives a Tone.js PolySynth from the analysed melody while stepping the OSMD
 * cursor in lockstep. All scheduling is done in the AudioContext clock; the
 * `rate` multiplier scales the original analysis timeline (1 = analysed tempo).
 */
export class ScorePlayer {
  private osmd: OpenSheetMusicDisplay;
  private analysis: AnalysisResponse;
  private cb: PlayerCallbacks;

  private synth: Tone.PolySynth;
  private cursorTimes: number[] = [];
  private cursorIndex = 0;
  private rate = 1;

  private state: PlaybackState = "stopped";
  private ctxStart = 0; // AudioContext time mapped to elapsed 0
  private pausedElapsed = 0;
  private raf = 0;

  constructor(osmd: OpenSheetMusicDisplay, analysis: AnalysisResponse, cb: PlayerCallbacks = {}) {
    this.osmd = osmd;
    this.analysis = analysis;
    this.cb = cb;
    this.synth = new Tone.PolySynth(Tone.Synth, {
      oscillator: { type: "triangle" },
      envelope: { attack: 0.01, decay: 0.15, sustain: 0.3, release: 0.4 },
    }).toDestination();
    this.synth.volume.value = -8;
    this.buildCursorTimeline();
  }

  get playbackState(): PlaybackState {
    return this.state;
  }

  setCallbacks(cb: PlayerCallbacks): void {
    this.cb = { ...this.cb, ...cb };
  }

  get durationSec(): number {
    const lastNote = this.analysis.notes.at(-1)?.end_sec ?? 0;
    return Math.max(this.analysis.duration_sec, lastNote, this.cursorTimes.at(-1) ?? 0);
  }

  /** Whole-note timestamp of each cursor step -> seconds at the analysed tempo. */
  private buildCursorTimeline(): void {
    const bpm = this.analysis.bpm > 0 ? this.analysis.bpm : 120;
    const wholeToSec = (4 * 60) / bpm;
    const cursor = this.osmd.cursor;
    if (!cursor) return;
    try {
      cursor.reset();
      const it = cursor.iterator;
      const times: number[] = [];
      let guard = 0;
      while (it && !it.EndReached && guard < 100000) {
        const ts = it.currentTimeStamp?.RealValue ?? 0;
        times.push(ts * wholeToSec);
        cursor.next();
        guard += 1;
      }
      cursor.reset();
      this.cursorTimes = times;
    } catch {
      this.cursorTimes = [];
    }
  }

  private showCursor(): void {
    try {
      this.osmd.cursor?.show();
    } catch {
      /* cursor not ready */
    }
  }

  private setState(s: PlaybackState): void {
    this.state = s;
    this.cb.onStateChange?.(s);
  }

  private scheduleNotes(fromElapsed: number): void {
    const now = Tone.now() + 0.05;
    for (const n of this.analysis.notes) {
      if (n.end_sec <= fromElapsed) continue;
      const startAt = now + Math.max(0, n.start_sec - fromElapsed) / this.rate;
      const dur = Math.max(0.05, (n.end_sec - n.start_sec) / this.rate);
      const freq = Tone.Frequency(n.midi, "midi").toFrequency();
      this.synth.triggerAttackRelease(freq, dur, startAt, Math.min(1, Math.max(0.2, n.velocity)));
    }
  }

  private loop = (): void => {
    if (this.state !== "playing") return;
    const elapsed = (Tone.now() - this.ctxStart) * this.rate;

    while (
      this.cursorIndex < this.cursorTimes.length - 1 &&
      this.cursorTimes[this.cursorIndex + 1] <= elapsed
    ) {
      this.osmd.cursor?.next();
      this.cursorIndex += 1;
    }
    this.cb.onTick?.(elapsed);

    if (elapsed >= this.durationSec) {
      this.stop();
      this.cb.onEnd?.();
      return;
    }
    this.raf = requestAnimationFrame(this.loop);
  };

  async play(): Promise<void> {
    if (this.state === "playing") return;
    await Tone.start();
    const fromElapsed = this.pausedElapsed;
    this.ctxStart = Tone.now() - fromElapsed / this.rate;
    this.scheduleNotes(fromElapsed);
    this.showCursor();
    this.syncCursorTo(fromElapsed);
    this.setState("playing");
    this.raf = requestAnimationFrame(this.loop);
  }

  pause(): void {
    if (this.state !== "playing") return;
    this.pausedElapsed = (Tone.now() - this.ctxStart) * this.rate;
    cancelAnimationFrame(this.raf);
    this.synth.releaseAll();
    this.setState("paused");
  }

  stop(): void {
    cancelAnimationFrame(this.raf);
    this.synth.releaseAll();
    this.pausedElapsed = 0;
    this.cursorIndex = 0;
    try {
      this.osmd.cursor?.reset();
    } catch {
      /* noop */
    }
    this.setState("stopped");
    this.cb.onTick?.(0);
  }

  setRate(rate: number): void {
    const clamped = Math.min(2, Math.max(0.4, rate));
    if (this.state === "playing") {
      this.pause();
      this.rate = clamped;
      void this.play();
    } else {
      this.rate = clamped;
    }
  }

  getRate(): number {
    return this.rate;
  }

  seek(elapsedSec: number): void {
    const wasPlaying = this.state === "playing";
    if (wasPlaying) this.pause();
    this.pausedElapsed = Math.min(Math.max(0, elapsedSec), this.durationSec);
    this.syncCursorTo(this.pausedElapsed);
    this.cb.onTick?.(this.pausedElapsed);
    if (wasPlaying) void this.play();
  }

  private syncCursorTo(elapsed: number): void {
    if (!this.osmd.cursor) return;
    try {
      this.osmd.cursor.reset();
      this.cursorIndex = 0;
      while (
        this.cursorIndex < this.cursorTimes.length - 1 &&
        this.cursorTimes[this.cursorIndex + 1] <= elapsed
      ) {
        this.osmd.cursor.next();
        this.cursorIndex += 1;
      }
    } catch {
      /* noop */
    }
  }

  dispose(): void {
    this.stop();
    this.synth.dispose();
  }
}
