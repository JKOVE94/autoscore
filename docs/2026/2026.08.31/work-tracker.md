# Work Tracker — AI 기반 오디오/이미지 통합 인터랙티브 리드 시트 생성 시스템

- **목적**: 오디오/Stem/악보이미지 → MusicXML 생성 → 웹 GUI 시각화·재생·검수 → 반복기호 기반 축약형 리드 시트 변환 엔드투엔드 파이프라인 구축
- **작성일**: 2026-08-31
- **작성자**: Claude Code (총괄 PM & 아키텍트)
- **상태**: 🔄 진행 중 — Step 1·2 완료 (audio_analyzer + xml_builder), Step 3(프론트엔드) 대기
- **타깃 환경**: Apple Silicon (M1 Pro, macOS), 로컬 구동

---

## 아키텍처 개요

```
                    ┌─────────────── Frontend (React + Vite + TS) ───────────────┐
                    │  Upload Panel · OSMD 렌더링 · Tone.js 재생 · 마디 검수 UI     │
                    └───────────────────────────┬───────────────────────────────┘
                                                │ REST (FastAPI)
        ┌───────────────────────────────────────┴───────────────────────────────┐
        │                          Backend (Python 3.11, FastAPI)                │
        │                                                                       │
        │  입력모드 1: 단일 오디오 ──► stem_splitter.py (Stemdeck / CoreML)       │
        │  입력모드 2: 사전분리 Stem ─┐                                            │
        │                            ├─► audio_analyzer.py (basic-pitch,          │
        │                            │     essentia/BTC, madmom)                  │
        │                            └─► xml_builder.py (music21 quantize/조립)   │
        │  입력모드 3: 악보 이미지 ──► omr_engine.py (Audiveris CLI subprocess)   │
        │                                                                       │
        │  검수 루프: /api/regenerate-measure — 구간 슬라이싱 후 <measure> 패치    │
        │  축약 엔진: form_compressor.py — 반복/볼타/D.S. al Coda 삽입             │
        └───────────────────────────────────────────────────────────────────────┘
```

---

## 착수 로드맵

| # | 단계 | 작업 내용 | 파일 | 상태 | 비고 |
|---|------|-----------|------|------|------|
| 1 | Step 1 | FastAPI 프로젝트 구조 + 업로드 파이프라인 | `backend/app/main.py`, `api/routes/upload.py` | ✅ | 스캐폴딩 완료 |
| 2 | Step 1 | Stemdeck 연동 래퍼 | `backend/app/services/stem_splitter.py` | ✅ | CLI 래퍼 + 폴백(demucs) 훅, 단위테스트 포함 |
| 3 | Step 1 | Audiveris OMR 연동 래퍼 | `backend/app/services/omr_engine.py` | ✅ | subprocess + music21 파싱, 단위테스트 포함 |
| 4 | Step 1 | 외부 엔진 경로/설정 검증 CLI | `backend/scripts/check_engines.py` | ✅ | `python -m scripts.check_engines` |
| 5 | Step 2 | 오디오 분석 (멜로디/리듬/화성) | `backend/app/services/audio_analyzer/` | ✅ | 패키지화. basic-pitch/essentia/madmom lazy + librosa 폴백. `/api/analyze/{job_id}`. 20 테스트 |
| 6 | Step 2 | MusicXML 빌더 (music21 양자화/조립) | `backend/app/services/xml_builder.py` | ✅ | QuantGrid 양자화 + 리드시트(멜로디+코드심볼) 조립. `POST /api/build/{job_id}`. 9 테스트 |
| 7 | Step 3 | 프론트엔드 (Vite + React + TS + Tailwind) | `frontend/` | 📋 | 디렉터리만 생성 |
| 8 | Step 3 | OSMD 렌더링 컴포넌트 | `frontend/src/components/ScoreView.tsx` | 📋 | 미착수 |
| 9 | Step 3 | Tone.js 재생기 + OSMD 커서 동기화 | `frontend/src/components/Player.tsx` | 📋 | 미착수 |
| 10 | Step 4 | 마디 단위 검수 UI + `/api/regenerate-measure` | `backend/app/api/routes/regenerate.py` | 📋 | 미착수 |
| 11 | Step 5 | 송 폼 분석 + 축약 엔진 (Form Compressor) | `backend/app/services/form_compressor.py` | 📋 | 미착수 |

상태 범례: 📋 대기 · 🔄 진행중 · 🚧 블록 · ✅ 완료

---

## 환경 주의사항

- **로컬 Python 3.14 감지됨** — `basic-pitch`, `essentia`, `madmom` 는 3.14 휠 미제공.
  → `backend/` 는 **Python 3.11 venv** 사용 권장 (`python3.11 -m venv .venv`).
- **Java 17 감지됨** (Temurin 17.0.19) — Audiveris 5.x 요구사항 충족 ✅
- **Node 26 감지됨** — Vite 최신 호환 ✅
- Stemdeck: https://github.com/stemdeckapp/stemdeck — CLI/모듈 설치 후 `STEMDECK_BIN` 환경변수로 경로 지정.
- Audiveris: 별도 설치 후 `AUDIVERIS_BIN` (또는 배포 스크립트 경로) 환경변수 지정.

---

## Step 2 audio_analyzer 설계 메모 (완료)

`backend/app/services/audio_analyzer/` 패키지:

| 모듈 | 역할 | 프리미엄 백엔드 | 폴백 (현재 활성) |
|------|------|-----------------|------------------|
| `melody.py` | vocal → NoteEvent | basic-pitch | `librosa.pyin` + 노트 분절 |
| `rhythm.py` | BPM/beat/downbeat | madmom (DBN downbeat) | `librosa.beat_track` + 다운비트 phase 탐색 |
| `harmony.py` | key + chord span | essentia (KeyExtractor/HPCP) | CQT chroma + Krumhansl 키 + 코드템플릿 코사인매칭 |
| `theory.py` | 키프로필·코드템플릿·PC네이밍 | — | 순수 numpy (단위테스트) |
| `loader.py` | 오디오 로드/믹스/윈도우 슬라이스 | — | soundfile→librosa 폴백 |
| `pipeline.py` | `analyze(stems, window=)` 오케스트레이션 | — | — |
| `backends.py` | 옵션 의존성 probe / 백엔드 선택 | — | — |

- 무거운 의존성은 전부 lazy import → 최소 환경에서도 패키지 import 안전.
- `window=(t0,t1)` 파라미터로 구간 분석 후 절대시간 재앵커 → Step 4 마디 재생성에 재사용.
- librosa 폴백은 박자표를 추측하지 않고 `default_time_signature`(4/4) numerator 신뢰, downbeat phase만 탐색.
- API: `POST /api/analyze/{job_id}` (stems 자동탐색: `storage/stems/{id}` → `storage/uploads/{id}`), `GET /api/analyze/backends`.
- 결과 JSON → `storage/outputs/{job_id}/analysis.json`.

## Step 2 xml_builder 설계 메모 (완료)

- `QuantGrid(beat_times, beat_unit, division)`: 초 → quarterLength 매핑. beat 위치를
  선형보간 후 subdivision(4/4·division16 → 비트당 4개)에 스냅. 마지막 비트 이후는
  median 비트 주기로 외삽.
- 마디 원점 = `beat_times[0]` (다운비트 phase보다 비트트래킹을 신뢰).
  `downbeat_times[0]` 이 반박자 이상 어긋나면 warning (아나크루시스 무시).
- 멜로디: 양자화 → 모노포니 강제(다음 온셋에서 이전 음 절단) → 갭 rest → music21
  `makeNotation`(마디분할·타이·빔). 음표 없으면 마디 수만큼 rest.
- 코드심볼: `root_pc`+`quality` → music21 `ChordSymbol(root, kind)`. onset을 비트로
  스냅, 해당 마디에 삽입, 연속 중복 제거, `N.C.` 스킵. `writeAsChord=False`.
- 출력: `storage/outputs/{job_id}/full.musicxml`. `BuildResult`(마디/음표/rest/코드/드롭 수 + warnings).
- 전체 체인: `upload → separate → analyze → build`.

## 다음 액션

1. **Step 3 — 프론트엔드**: Vite+React+TS, 업로드 패널(모드1/2/3), 메타헤더,
   `OpenSheetMusicDisplay` 렌더링, `Tone.js` 재생 + OSMD 커서 동기화.
2. `audio_analyzer` 프리미엄 백엔드(basic-pitch/essentia/madmom) 실제 설치·검증.
3. Step 4 마디 검수(`/api/regenerate-measure`) — `analyze(window=)` + `<measure>` 패치 재사용.
