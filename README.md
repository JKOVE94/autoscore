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
│   │   │   ├── audio_analyzer/    멜로디·리듬·화성 분석 패키지      ✅ Step 2
│   │   │   └── xml_builder.py     music21 양자화·리드시트 조립       ✅ Step 2
│   │   └── schemas/          Pydantic 모델
│   ├── scripts/check_engines.py   외부 엔진 연동 검증 CLI
│   └── tests/                pytest 단위 테스트
├── frontend/                 React + Vite + TS + Tailwind — 웹 GUI  ✅ Step 3
└── docs/2026/2026.08.31/work-tracker.md   진행 추적 문서
```

---

## 빠른 시작 (한 줄)

```bash
./run            # 최초 실행 시 자동 설치 후 백엔드(:8000) + 프론트(:5173) 동시 기동
```

| 명령 | 설명 |
|------|------|
| `./run` | 필요하면 setup 후 두 서버 실행 (Ctrl+C로 둘 다 종료) |
| `./run setup` | venv 생성 · 백엔드/프론트 의존성 설치 · `.env` 생성 |
| `./run doctor` | 사전 요구사항 + 외부 엔진 상태 점검 |
| `./run test` | 백엔드 pytest + ruff + 프론트 타입체크 |
| `./run stop` | 8000 / 5173 포트 정리 |
| `./run clean` | venv · node_modules · storage 초기화 |

`make setup|dev|doctor|test|stop|clean` 도 동일하게 동작합니다.

**필요한 것**: Python 3.10–3.12, Node 20+, (선택) `ffmpeg` — YouTube/URL 입력용
(`brew install ffmpeg`). `./run setup` 이 anaconda 등에 설치된 3.11도 자동 탐지합니다.

<details>
<summary>수동 설정 (스크립트 없이)</summary>

```bash
cd backend && python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp backend/.env.example backend/.env
cd frontend && npm install && cp .env.example .env
# 백엔드: cd backend && .venv/bin/uvicorn app.main:app --reload
# 프론트: cd frontend && npm run dev
```
</details>

### 외부 엔진 (선택 — 없으면 폴백 동작)

| 엔진 | 용도 | 설치 | 환경변수 |
|------|------|------|----------|
| Stemdeck | 입력모드 1·2 음원 분리 | https://github.com/stemdeckapp/stemdeck | `STEMDECK_BIN` (또는 `STEM_FALLBACK=demucs`) |
| Audiveris | 입력모드 3 OMR | https://github.com/Audiveris/audiveris (Java 17+) | `AUDIVERIS_BIN` |
| ffmpeg | YouTube/URL 오디오 추출 | `brew install ffmpeg` | `FFMPEG_BIN` |

미설정 시: 분석은 librosa 폴백으로 동작, Stemdeck/Audiveris 필요 모드만 실패합니다.
`backend/.env` 로 경로·옵션을 조정하세요.

### API

http://127.0.0.1:8000/docs 에서 전체 확인.

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 앱 상태 + 엔진 구성 여부 |
| POST | `/api/upload` | 파일 업로드 → 입력모드 자동 판별 (`job_id` 반환) |
| POST | `/api/separate/{job_id}` | 입력모드 1: Stemdeck으로 vocal/drums/bass/other 분리 |
| POST | `/api/omr/{job_id}` | 입력모드 3: Audiveris OMR → MusicXML + music21 검증 |
| POST | `/api/analyze/{job_id}` | Step 2: 분리된 stem에서 BPM/key/코드/멜로디 추출 (`{"window":[t0,t1]}` 옵션) |
| GET | `/api/analyze/backends` | 분석 백엔드(basic-pitch/essentia/madmom/librosa) 가용성 |
| POST | `/api/upload-stems` | 입력모드 2: 사전 분리 stem 여러 개를 한 job으로 업로드 |
| POST | `/api/upload-url` | 입력모드 1(URL): YouTube 등 링크에서 오디오 추출(yt-dlp) → 이후 `/api/separate` |
| POST | `/api/build/{job_id}` | Step 2: 저장된 분석 → 리드시트 `full.musicxml` 조립 |
| GET | `/api/jobs/{job_id}` | job 아티팩트 상태(upload/stems/analysis/musicxml) |
| GET | `/api/analysis/{job_id}` | 저장된 분석 JSON |
| GET | `/api/score/{job_id}` | 생성된 `full.musicxml` 다운로드 |
| GET | `/api/measures/{job_id}` | Step 4: 마디별 시간 구간 목록 |
| POST | `/api/regenerate-measure/{job_id}` | Step 4: 선택 마디만 재분석 → 악보 패치 |
| POST | `/api/compress/{job_id}` | Step 5: 반복 감지 → 도돌이표/볼타/D.S. 축약 리드시트 |
| GET | `/api/lead-sheet/{job_id}` | Step 5: 축약 `lead_sheet.musicxml` 다운로드 |

### 테스트

```bash
./run test          # 백엔드 67 pytest + ruff + 프론트 타입체크
```

---

## Step 3 — 웹 GUI (frontend, 완료)

Vite + React 18 + TS + Tailwind. 악보 `opensheetmusicdisplay`, 재생 `tone`.

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173
# 백엔드(uvicorn app.main:app)를 먼저 기동
```

- 업로드 패널 4탭(단일음원 / YouTube URL / 분리Stem 다중 / 악보이미지) → 모드별 파이프라인 자동 실행
- OSMD SVG 렌더링 + 메타헤더(Key/BPM/TimeSig/Measures)
- Tone.js PolySynth 재생: play/pause/seek, tempo 0.4~2× 슬라이더, OSMD 커서 lockstep 동기화

자세한 내용은 [`frontend/README.md`](frontend/README.md).

---

## Step 2 — 오디오 분석 (audio_analyzer, 완료)

`app/services/audio_analyzer/` 패키지. 무거운 의존성은 lazy import이며 **librosa 폴백**으로
`numpy`/`librosa`/`soundfile`만 있어도 동작합니다.

| 스테이지 | 프리미엄 백엔드 | 폴백 |
|---|---|---|
| 멜로디 (`melody.py`) | basic-pitch | `librosa.pyin` + 노트 분절 |
| 리듬 (`rhythm.py`) | madmom | `librosa.beat_track` + downbeat phase 탐색 |
| 화성 (`harmony.py`) | essentia | CQT chroma + Krumhansl 키 + 코드템플릿 코사인 매칭 |

```bash
# 폴백만: 이미 설치됨 (numpy, librosa, soundfile)
# 프리미엄: pip install basic-pitch madmom ; pip install essentia
python -c "from app.services.audio_analyzer import analyze"
```

`analyze(stems, window=(t0,t1))` — `window`는 구간만 분석 후 절대시간으로 재앵커(Step 4 재사용).

### xml_builder (리드시트 조립)

`AnalysisResult` → `QuantGrid` 로 16분음표 양자화 → 단일 트레블 보표에 멜로디 +
`<harmony>` 코드심볼 → music21 `makeNotation`(마디분할/타이/빔) → `full.musicxml`.

```python
from app.services.xml_builder import build_musicxml
build_musicxml(analysis, "storage/outputs/<job>/full.musicxml", title="...")
```

전체 체인: **upload → separate → analyze → build**.

---

## Step 4 — 마디 검수 & 부분 재생성 (완료)

`MeasureInspector`에서 오인식된 마디를 선택하고 피치 감도·양자화 단위를 조절해
재분석하면, 글로벌 비트 그리드는 유지한 채 해당 구간의 멜로디·화성만 다시 추출하여
악보를 패치합니다 (`audio_analyzer/regen.py` → `analyze_window` / `merge_window`).

## Step 5 — 리드 시트 축약 & 송 폼 (완료)

`FormCompressor`에서 "축약 리드 시트 생성"을 누르면 반복 구간을 감지해 축약합니다
(`form_compressor.py`):

- **도돌이표 · 1·2절 볼타** — music21 `RepeatFinder.simplify()`
- **D.S. al Coda / al Fine** — RepeatFinder가 못 접는 비인접 반복에 Segno/Coda/D.S. 삽입
- **송 폼 문자열** — 마디별 코드·음정 지문으로 `A B C D×2 …` 라벨

전체/축약 뷰 토글, 축약 MusicXML 다운로드 지원.

## 후속 검증

기능은 전 단계 구현 완료. 환경 제약으로 아래는 미실행:
- 프리미엄 분석 백엔드(basic-pitch/essentia/madmom) 실제 설치·비교
- 브라우저 E2E (크롬 확장 연결 후 OSMD 렌더/재생/축약뷰 확인)
- **Step 4**: 마디 단위 검수 & `/api/regenerate-measure`
- **Step 5**: 송 폼 분석 + 리드 시트 축약 엔진

진행 상황은 [`docs/2026/2026.08.31/work-tracker.md`](docs/2026/2026.08.31/work-tracker.md) 참고.
