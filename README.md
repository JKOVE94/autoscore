# AutoScore — AI 기반 오디오/이미지 통합 인터랙티브 리드 시트 생성 시스템

오디오 음원 · 사전 분리 Stem · 악보 이미지를 입력받아 표준 MusicXML을 생성하고,
웹 GUI에서 시각화·재생·검수한 뒤 반복 기호(도돌이표, D.S., D.C., 볼타)를 활용한
**축약형 리드 시트**로 변환하는 엔드투엔드 파이프라인.

타깃 환경: **Apple Silicon (M1 Pro, macOS) 로컬**.

---

## 저장소 구조

```
autoscore/
├── backend/                  FastAPI 파이프라인 (Python 3.11)
│   ├── app/
│   │   ├── main.py           앱 엔트리포인트 (create_app)
│   │   ├── config.py         .env 설정 로더
│   │   ├── api/routes/       health, upload/separate/omr 엔드포인트
│   │   ├── core/             예외, 로깅, 업로드 검증
│   │   ├── services/
│   │   │   ├── stem_splitter.py   Stemdeck CLI 래퍼 (입력모드 1)   ✅ Step 1
│   │   │   ├── omr_engine.py      Audiveris CLI 래퍼 (입력모드 3)  ✅ Step 1
│   │   │   ├── audio_analyzer.py  basic-pitch/essentia/madmom      📋 Step 2
│   │   │   └── xml_builder.py     music21 양자화·조립              📋 Step 2
│   │   └── schemas/          Pydantic 모델
│   ├── scripts/check_engines.py   외부 엔진 연동 검증 CLI
│   └── tests/                pytest 단위 테스트
├── frontend/                 React + Vite + TS (📋 Step 3)
└── docs/2026/2026.08.31/work-tracker.md   진행 추적 문서
```

---

## Step 1 — 백엔드 환경 설정 및 외부 엔진 연동 (현재 완료)

### 1. 가상환경 & 의존성

```bash
cd backend
python3.11 -m venv .venv          # 3.11 필수 (basic-pitch/essentia/madmom는 3.14 미지원)
source .venv/bin/activate
pip install -r requirements.txt
```

> Step 1 검증만 하려면 최소 셋만 설치해도 됩니다:
> `pip install fastapi "uvicorn[standard]" python-multipart pydantic-settings music21 pytest httpx ruff`

### 2. 환경변수

```bash
cp .env.example .env
# STEMDECK_BIN, AUDIVERIS_BIN 경로를 실제 설치 위치로 수정
```

| 엔진 | 설치 | 환경변수 |
|------|------|----------|
| Stemdeck | https://github.com/stemdeckapp/stemdeck | `STEMDECK_BIN` (미설정 시 `STEM_FALLBACK=demucs` 가능) |
| Audiveris | https://github.com/Audiveris/audiveris (Java 17+) | `AUDIVERIS_BIN` |

### 3. 엔진 연동 검증

```bash
cd backend
python -m scripts.check_engines
```

### 4. API 기동

```bash
cd backend
uvicorn app.main:app --reload
# http://127.0.0.1:8000/docs
```

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 앱 상태 + 엔진 구성 여부 |
| POST | `/api/upload` | 파일 업로드 → 입력모드 자동 판별 (`job_id` 반환) |
| POST | `/api/separate/{job_id}` | 입력모드 1: Stemdeck으로 vocal/drums/bass/other 분리 |
| POST | `/api/omr/{job_id}` | 입력모드 3: Audiveris OMR → MusicXML + music21 검증 |

### 5. 테스트 & 린트

```bash
cd backend
pytest -q          # 10 passed
ruff check .
```

---

## 다음 단계

- **Step 2**: `audio_analyzer.py` / `xml_builder.py` 구현 (스텁 존재)
- **Step 3**: 프론트엔드 (OSMD 렌더링 + Tone.js 재생)
- **Step 4**: 마디 단위 검수 & `/api/regenerate-measure`
- **Step 5**: 송 폼 분석 + 리드 시트 축약 엔진

진행 상황은 [`docs/2026/2026.08.31/work-tracker.md`](docs/2026/2026.08.31/work-tracker.md) 참고.
