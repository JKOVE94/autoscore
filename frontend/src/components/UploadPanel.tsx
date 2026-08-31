import { useRef, useState } from "react";

type TabId = "single_audio" | "youtube" | "presplit_stems" | "score_image";

interface Props {
  disabled: boolean;
  onRunSingle: (file: File) => void;
  onRunUrl: (url: string) => void;
  onRunStems: (files: File[]) => void;
  onRunImage: (file: File) => void;
}

interface TabDef {
  id: TabId;
  label: string;
  hint: string;
  kind: "file" | "url";
  accept?: string;
  multiple?: boolean;
}

const TABS: TabDef[] = [
  {
    id: "single_audio",
    label: "① 단일 음원",
    hint: "MP3 / WAV — Stemdeck으로 자동 분리 후 분석",
    kind: "file",
    accept: "audio/*,.wav,.mp3,.flac,.m4a",
  },
  {
    id: "youtube",
    label: "② YouTube",
    hint: "영상 링크에서 오디오를 추출(yt-dlp) 후 단일 음원과 동일하게 처리",
    kind: "url",
  },
  {
    id: "presplit_stems",
    label: "③ 분리 Stem",
    hint: "vocal / bass / drums / other 등 여러 WAV 선택",
    kind: "file",
    accept: "audio/*,.wav,.mp3,.flac",
    multiple: true,
  },
  {
    id: "score_image",
    label: "④ 악보 이미지",
    hint: "PNG / JPG / PDF — Audiveris OMR",
    kind: "file",
    accept: "image/*,.png,.jpg,.jpeg,.pdf,.tif,.tiff",
  },
];

export function UploadPanel({ disabled, onRunSingle, onRunUrl, onRunStems, onRunImage }: Props) {
  const [active, setActive] = useState<TabId>("single_audio");
  const [picked, setPicked] = useState<File[]>([]);
  const [url, setUrl] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const tab = TABS.find((t) => t.id === active)!;

  function reset() {
    setPicked([]);
    setUrl("");
    if (inputRef.current) inputRef.current.value = "";
  }

  const canSubmit = tab.kind === "url" ? url.trim().length > 0 : picked.length > 0;

  function submit() {
    if (!canSubmit) return;
    if (active === "single_audio") onRunSingle(picked[0]);
    else if (active === "youtube") onRunUrl(url.trim());
    else if (active === "presplit_stems") onRunStems(picked);
    else onRunImage(picked[0]);
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex flex-wrap gap-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => {
              setActive(t.id);
              reset();
            }}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
              active === t.id
                ? "bg-ink text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <p className="mb-3 text-xs text-slate-500">{tab.hint}</p>

      {tab.kind === "url" ? (
        <input
          type="url"
          inputMode="url"
          placeholder="https://www.youtube.com/watch?v=…"
          value={url}
          disabled={disabled}
          onChange={(e) => setUrl(e.target.value)}
          className="block w-full rounded-md border border-slate-300 px-3 py-2 text-sm placeholder:text-slate-400"
        />
      ) : (
        <input
          ref={inputRef}
          type="file"
          accept={tab.accept}
          multiple={tab.multiple}
          disabled={disabled}
          onChange={(e) => setPicked(Array.from(e.target.files ?? []))}
          className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium hover:file:bg-slate-200"
        />
      )}

      {picked.length > 0 && (
        <ul className="mt-2 text-xs text-slate-500">
          {picked.map((f) => (
            <li key={f.name}>
              {f.name} · {(f.size / 1024 / 1024).toFixed(2)} MB
            </li>
          ))}
        </ul>
      )}

      {active === "youtube" && (
        <p className="mt-2 text-[11px] text-slate-400">
          링크의 저작권·서비스 약관 준수는 이용자 책임입니다. 15분 이하 영상만 허용됩니다.
        </p>
      )}

      <button
        onClick={submit}
        disabled={disabled || !canSubmit}
        className="mt-3 w-full rounded-md bg-emerald-600 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        파이프라인 실행
      </button>
    </div>
  );
}
