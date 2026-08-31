# Frontend — AutoScore 웹 GUI (Step 3)

Vite 6 + React 18 + TypeScript(strict) + Tailwind CSS 3.
악보 렌더링 `opensheetmusicdisplay`, 재생 `tone`.

## 실행

레포 루트에서 `./run` 이면 백엔드까지 함께 뜹니다. 프론트만 직접 다룰 때:

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173  (dev proxy: /api -> http://127.0.0.1:8000)
```

| 스크립트 | 설명 |
|---|---|
| `npm run dev` | 개발 서버 (HMR + `/api` 프록시) |
| `npm run build` | `tsc` 타입체크 후 `vite build` → `dist/` |
| `npm run typecheck` | 타입체크만 |

`.env` (선택): `VITE_API_BASE` 로 절대 백엔드 주소 지정, `VITE_API_TARGET` 로 프록시 타깃 변경.

## 구조

```
src/
├── App.tsx                  레이아웃 + 파이프라인 상태 오케스트레이션
├── api/client.ts            타입드 fetch 래퍼 (ApiRequestError)
├── types.ts                 백엔드 응답 타입
├── hooks/usePipeline.ts     모드별 스텝 체인 실행 + 진행 상태
├── audio/player.ts          ScorePlayer — Tone.PolySynth + OSMD 커서 lockstep
└── components/
    ├── UploadPanel.tsx       4탭: 단일음원 / YouTube URL / 분리Stem(다중) / 악보이미지
    ├── MetaHeader.tsx        Key · BPM · TimeSig · Measures · backends
    ├── ScoreView.tsx         OpenSheetMusicDisplay 래퍼
    ├── PlayerBar.tsx         재생/정지 · seek · tempo(0.4~2×) 슬라이더
    ├── MeasureInspector.tsx  마디 다중선택 + 감도/양자화 → 부분 재분석 (Step 4)
    └── FormCompressor.tsx    축약 리드시트 생성 · 전체/축약 토글 · 다운로드 (Step 5)
```

## 파이프라인 (모드별)

| 모드 | 스텝 |
|---|---|
| ① 단일 음원 | `upload` → `separate`(Stemdeck) → `analyze` → `build` → `score` |
| ② YouTube URL | `upload-url`(yt-dlp) → `separate` → `analyze` → `build` → `score` |
| ③ 분리 Stem | `upload-stems` → `analyze` → `build` → `score` |
| ④ 악보 이미지 | `upload` → `omr`(Audiveris) → `score` |

빌드 후: `regenerate-measure`(마디 검수) · `compress`(축약 리드시트) 는 수동 트리거.

데모 stem: `cd backend && python -m scripts.make_demo_stems <dir>` 로 4개 WAV 생성 후
③ 분리 Stem 탭에 드롭.
