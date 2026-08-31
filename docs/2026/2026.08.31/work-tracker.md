# Work Tracker — AI 기반 오디오/이미지 통합 인터랙티브 리드 시트 생성 시스템

- **목적**: 오디오/Stem/악보이미지 → MusicXML 생성 → 웹 GUI 시각화·재생·검수 → 반복기호 기반 축약형 리드 시트 변환 엔드투엔드 파이프라인 구축
- **작성일**: 2026-08-31
- **작성자**: Claude Code (총괄 PM & 아키텍트)
- **상태**: 🔄 진행 중 — Step 1 착수 (프로젝트 스캐폴딩 완료)
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
| 5 | Step 2 | 오디오 분석 (basic-pitch / essentia / madmom) | `backend/app/services/audio_analyzer.py` | 📋 | 스텁 존재 — 미구현 |
| 6 | Step 2 | MusicXML 빌더 (music21 양자화/조립) | `backend/app/services/xml_builder.py` | 📋 | 스텁 존재 — 미구현 |
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

## 다음 액션

1. Python 3.11 venv 생성 후 `pip install -r backend/requirements.txt`
2. Stemdeck / Audiveris 설치 및 `.env` 경로 설정
3. `python -m scripts.check_engines` 로 외부 엔진 연동 검증
4. `uvicorn app.main:app --reload` 로 API 기동, `/docs` 확인
5. 검증 완료 후 Step 2 (audio_analyzer / xml_builder) 착수
