# Frontend — AutoScore 웹 GUI (Step 3)

Vite 6 + React 18 + TypeScript(strict) + Tailwind CSS 3.
악보 렌더링 `opensheetmusicdisplay`, 재생 `tone`.

## 실행

레포 루트에서 통합 실행:

- `./run` — `vite build` → `backend/static/` 에 넣고 API가 함께 서빙 (한 프로세스 :8000)
- `./run docker` — 같은 걸 한 컨테이너로
- `./run dev` — 이 개발 서버(:5173, HMR) + API(:8000) 두 프로세스

프론트만 직접:

```bash
cd frontend && npm install
npm run dev          # http://localhost:5173  (dev proxy: /api -> :8000)
npm run build        # tsc + vite build -> dist/
```

빌드된 UI는 API 호출을 상대경로 `/api` 로 하므로, 백엔드가 같은 오리진에서 서빙하면
프록시·CORS 불필요. `.env` 로 `VITE_API_BASE`(절대 주소) / `VITE_API_TARGET`(프록시 타깃) 조정 가능.

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
