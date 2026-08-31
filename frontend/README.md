# Frontend (Step 3 — 미착수)

Step 3에서 아래 스택으로 스캐폴딩 예정:

```bash
npm create vite@latest . -- --template react-ts
npm i tailwindcss @tailwindcss/vite opensheetmusicdisplay tone
```

계획 컴포넌트:

- `src/components/UploadPanel.tsx` — 입력모드 1/2/3 업로드
- `src/components/MetaHeader.tsx` — Key / BPM / Time Signature / Song Form
- `src/components/ScoreView.tsx` — OpenSheetMusicDisplay 렌더링
- `src/components/Player.tsx` — Tone.js 재생 + OSMD 커서 동기화
- `src/components/MeasureInspector.tsx` — 마디 선택 → 부분 재생성 (Step 4)

백엔드 기본 주소: `http://127.0.0.1:8000` (CORS는 `backend/.env`의 `CORS_ORIGINS`로 제어).
