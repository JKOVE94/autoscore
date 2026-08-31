import { useRef, useState } from "react";
import type { InputMode } from "../types";

interface Props {
  disabled: boolean;
  onRunSingle: (file: File) => void;
  onRunStems: (files: File[]) => void;
  onRunImage: (file: File) => void;
}

const TABS: { mode: InputMode; label: string; hint: string; accept: string; multiple: boolean }[] = [
  {
    mode: "single_audio",
    label: "① 단일 음원",
    hint: "MP3 / WAV — Stemdeck으로 자동 분리 후 분석",
    accept: "audio/*,.wav,.mp3,.flac,.m4a",
    multiple: false,
  },
  {
    mode: "presplit_stems",
    label: "② 분리 Stem",
    hint: "vocal / bass / drums / other 등 여러 WAV 선택",
    accept: "audio/*,.wav,.mp3,.flac",
    multiple: true,
  },
  {
    mode: "score_image",
    label: "③ 악보 이미지",
    hint: "PNG / JPG / PDF — Audiveris OMR",
    accept: "image/*,.png,.jpg,.jpeg,.pdf,.tif,.tiff",
    multiple: false,
  },
];

export function UploadPanel({ disabled, onRunSingle, onRunStems, onRunImage }: Props) {
  const [active, setActive] = useState<InputMode>("single_audio");
  const [picked, setPicked] = useState<File[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const tab = TABS.find((t) => t.mode === active)!;

  function submit() {
    if (picked.length === 0) return;
    if (active === "single_audio") onRunSingle(picked[0]);
    else if (active === "presplit_stems") onRunStems(picked);
    else onRunImage(picked[0]);
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex gap-1">
        {TABS.map((t) => (
          <button
            key={t.mode}
            onClick={() => {
              setActive(t.mode);
              setPicked([]);
              if (inputRef.current) inputRef.current.value = "";
            }}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
              active === t.mode
                ? "bg-ink text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <p className="mb-3 text-xs text-slate-500">{tab.hint}</p>

      <input
        ref={inputRef}
        type="file"
        accept={tab.accept}
        multiple={tab.multiple}
        disabled={disabled}
        onChange={(e) => setPicked(Array.from(e.target.files ?? []))}
        className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium hover:file:bg-slate-200"
      />

      {picked.length > 0 && (
        <ul className="mt-2 text-xs text-slate-500">
          {picked.map((f) => (
            <li key={f.name}>
              {f.name} · {(f.size / 1024 / 1024).toFixed(2)} MB
            </li>
          ))}
        </ul>
      )}

      <button
        onClick={submit}
        disabled={disabled || picked.length === 0}
        className="mt-3 w-full rounded-md bg-emerald-600 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        파이프라인 실행
      </button>
    </div>
  );
}
