# Work Tracker — AI 기반 오디오/이미지 통합 인터랙티브 리드 시트 생성 시스템

- **목적**: 오디오/Stem/악보이미지 → MusicXML 생성 → 웹 GUI 시각화·재생·검수 → 반복기호 기반 축약형 리드 시트 변환 엔드투엔드 파이프라인 구축
- **작성일**: 2026-08-31
- **작성자**: Claude Code (총괄 PM & 아키텍트)
- **상태**: ✅ Step 1~5 전 단계 구현 완료 (엔드투엔드 파이프라인 + 웹 GUI). 프리미엄 백엔드 설치·브라우저 E2E는 후속 검증 항목.
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
| 7 | Step 3 | 프론트엔드 (Vite + React 18 + TS + Tailwind3) | `frontend/` | ✅ | tsc/vite build 통과. dev proxy `/api`→:8000 |
| 8 | Step 3 | OSMD 렌더링 컴포넌트 | `frontend/src/components/ScoreView.tsx` | ✅ | MusicXML 문자열 → SVG, cursor.show |
| 9 | Step 3 | Tone.js 재생기 + OSMD 커서 동기화 | `frontend/src/audio/player.ts`, `components/PlayerBar.tsx` | ✅ | PolySynth + AudioContext 클럭, tempo 슬라이더, seek, 커서 lockstep |
| 7b | Step 3 | 백엔드 아티팩트 서빙 | `backend/app/api/routes/jobs.py`, `upload-stems` | ✅ | `/api/score`·`/api/analysis`·`/api/jobs/{id}`, 다중 stem 업로드, OMR→full.musicxml 복사 |
| 10 | Step 4 | 마디 단위 검수 + 부분 재생성 | `backend/app/services/audio_analyzer/regen.py`, `api/routes/regenerate.py`, `frontend/.../MeasureInspector.tsx` | ✅ | 글로벌 비트그리드 유지, 윈도우만 melody+harmony 재추출 → merge → 재빌드. 6 테스트 |
| 11 | Step 5 | 송 폼 분석 + 축약 엔진 (Form Compressor) | `backend/app/services/form_compressor.py`, `api/routes/compress.py`, `frontend/.../FormCompressor.tsx` | ✅ | music21 RepeatFinder(도돌이표/볼타) + D.S. al Coda 폴백 + 송폼 문자열. `POST /api/compress`, `GET /api/lead-sheet`. 6 테스트 |

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

## Step 3 프론트엔드 설계 메모 (완료)

- `frontend/` : Vite 6 + React 18 + TS(strict) + Tailwind 3. dev proxy `/api`→`http://127.0.0.1:8000`.
- `UploadPanel` : 3탭(단일음원/분리Stem/악보이미지). Stem은 다중선택 → `/api/upload-stems`.
- `usePipeline` 훅 : 모드별 스텝 체인 실행(upload→[separate|omr]→analyze→build→scoreXml),
  각 스텝 상태(run/ok/fail) + 에러코드 표시.
- `ScoreView` : `OpenSheetMusicDisplay`(SVG, autoResize, followCursor). `onReady(osmd)` 콜백.
- `ScorePlayer`(`audio/player.ts`) : `Tone.PolySynth`를 AudioContext 클럭으로 스케줄.
  `rate`(0.4~2×) 슬라이더, `seek`, OSMD `cursor.iterator.currentTimeStamp` 로 스텝 타임라인
  계산 후 rAF 루프에서 `cursor.next()` lockstep. `PlayerBar` UI.
- `MetaHeader` : Key / BPM / TimeSig / Duration / Measures / (Song Form=Step5 placeholder) / backends.
- 백엔드 추가: `jobs.py`(`/api/score`,`/api/analysis`,`/api/jobs/{id}`), `/api/upload-stems`(다중),
  OMR 결과를 `outputs/{id}/full.musicxml` 로도 복사.
- 데모: `python -m scripts.make_demo_stems <dir>` → 4 stem WAV.
- ⚠️ 브라우저 E2E 미실행(크롬 확장 미연결). tsc/vite build/42 pytest 는 통과.

## Step 4 마디 검수 설계 메모 (완료)

- `regen.py`:
  - `measure_windows(analysis)` → 마디별 (t0,t1). xml_builder QuantGrid와 동일 규칙
    (원점 `beat_times[0]`, 마디당 numerator 비트, 범위 밖은 median 주기 외삽).
  - `selected_span(analysis, [2,3])` → 선택 마디 enclosing 구간 + 유효 번호.
  - `analyze_window(stems, base, span)` : **비트트래킹은 재실행 안 함**. base 글로벌
    그리드를 슬라이스-상대로 옮겨 melody(pyin)+harmony(chroma)만 재추출, 절대시간 복원.
    앞마디 2비트 컨텍스트 패딩, 리딩엣지 0.2비트 grace.
  - `merge_window(base, notes, chords, span)` : span 안 이벤트만 교체(코드는 midpoint 기준).
- `pitch_sensitivity`(0~1) → `min_note_sec` 0.16~0.03 매핑. `quantize_division` → build 오버라이드.
- API: `GET /api/measures/{id}`, `POST /api/regenerate-measure/{id}` {measures, pitch_sensitivity, quantize_division}
  → analysis.json 갱신 + full.musicxml 재빌드 + 전체 musicxml 문자열 반환.
- 프론트 `MeasureInspector`: 마디 번호 칩 다중선택 + 감도 슬라이더 + 양자화 select →
  재분석 후 `osmd.load(musicxml)` 리렌더, analysis 재fetch.
- `discover_stems` 를 `audio_analyzer/stems.py` 로 분리(analyze 라우트와 공유).

## Step 5 Form Compressor 설계 메모 (완료)

- `compress_musicxml(src, out, analysis=)`:
  - `music21.repeat.RepeatFinder.simplify()` — 인접 반복 → 도돌이표(`:|`), 끝부분
    변주 → 1·2절 볼타(RepeatBracket). 대부분의 축약을 여기서 처리.
  - `_apply_dal_segno()` — RepeatFinder가 못 접는 **비인접 반복**(len≥3) 폴백:
    Segno + To Coda + `D.S. al Coda`(코다 tail 있으면) / `D.S. al Fine`(없으면),
    반복 마디 삭제·재번호. (단독 호출 시 검증됨; 실사용은 RepeatFinder가 먼저 처리)
  - `_song_form(analysis)` — 마디별 (코드시퀀스, 피치클래스셋) 지문 → A/B/C 라벨 →
    런 축약 `"A B C D×2 ..."` 문자열.
- API: `POST /api/compress/{id}` → `lead_sheet.musicxml` + 리포트(ops, song_form),
  `GET /api/lead-sheet/{id}` 다운로드.
- 프론트 `FormCompressor`: "축약 리드 시트 생성" → 전체/축약 토글, ops 리스트,
  송폼 표시(MetaHeader에도), MusicXML 다운로드(Blob). 축약 뷰에선 재생기 숨김.
- 재생 시 regen 하면 축약 결과 무효화(`compressed=null`).

## 추가 기능 — YouTube/URL 오디오 입력 (완료)

- `app/services/youtube.py` : `yt-dlp` + `ffmpeg` 로 URL → `source.wav` 추출.
  - `validate_url()` : http(s) 만, 호스트 allowlist(`YOUTUBE_ALLOWED_HOSTS`, 기본 youtube 계열).
  - `fetch_audio()` : `bestaudio` → `FFmpegExtractAudio(wav)`, `noplaylist`,
    `YOUTUBE_MAX_DURATION_SEC`(기본 900s) 초과 거부, 중간 파일 정리.
  - `_run_ytdlp()` 분리(테스트에서 mock). `engine_available()` → health/check_engines 표시.
- `POST /api/upload-url {url}` → mode 1 job 생성 → 이후 `/api/separate` 부터 동일 체인.
- 프론트 `UploadPanel` : "② YouTube" 탭(URL 입력) → `usePipeline.runUrl()`.
- `requirements.txt` : `yt-dlp`(unpinned — YouTube 변경 대응). ffmpeg는 시스템 설치.
- 8 테스트(URL 검증 / mock 추출 / 라우트 / health). 총 67 pytest.
- ⚠️ 실제 YouTube 다운로드는 미실행(mock 테스트만). 링크 저작권/ToS는 이용자 책임.

## 개발 자동화 스크립트 (완료)

- 루트 `./run` (bash 3.2 호환, macOS 기본 셸 OK):
  - 인자 없음 → 필요 시 setup 후 백엔드(:8000)+프론트(:5173) 동시 기동, Ctrl+C로 둘 다 종료
  - `setup` : Python 3.10–12 자동탐지(anaconda 포함) → venv → `pip -r` → `npm install` → `.env` 생성 → check_engines
  - `doctor` : 사전요구사항 + 엔진 상태 / `test` : pytest+ruff+tsc / `stop` : 포트 정리 / `clean` : 초기화
- `Makefile` 은 `./run` 으로 위임하는 얇은 래퍼.
- 검증: `./run doctor`, `./run test`(67 pass), `./run dev`(양 서버 기동 확인), `./run stop` 정상.

- `scripts/bootstrap.sh` (= `./run bootstrap`, macOS): Homebrew 로 `python@3.11`·`node`·
  `ffmpeg`·`openjdk@17` 중 없는 것만 설치(있으면 스킵, `--yes` 로 무프롬프트) → `./run setup` → `./run doctor`.
  `--full` : venv 에 `demucs`(+`.env` STEM_FALLBACK=demucs 자동 전환)·`basic-pitch[coreml]`·
  `madmom`·`essentia` best-effort 설치. Homebrew 자체는 미설치 시 공식 명령 안내 후 종료.
  검증: 전 패키지 존재 상태에서 스킵→setup→doctor 정상.

## Docker 컨테이너화 (완료)

- `backend/Dockerfile` : `python:3.11-slim-bookworm` + `ffmpeg`·`libsndfile1`.
  `requirements.txt` 설치, `ARG WITH_DEMUCS=1` 시 demucs 추가. `TORCH_DEVICE=cpu`,
  `STORAGE_DIR=/data`, healthcheck(`/health`).
- `frontend/Dockerfile` : `node:22-slim`, `npm ci`, `vite --host 0.0.0.0`.
- `docker-compose.yml` (`name: autoscore`) :
  - backend :8000, frontend :5173, `VITE_API_TARGET=http://backend:8000`(프록시).
  - 소스 bind-mount + 핫리로드(`WATCHFILES_FORCE_POLLING`, `CHOKIDAR_USEPOLLING`).
  - `autoscore-data` 네임드 볼륨에 storage 유지. `STEM_FALLBACK=demucs`.
- `vite.config.ts` : `server.host=true`, `CHOKIDAR_USEPOLLING=true` 시 폴링 watch.
- `./run docker`(= `up --build`), `./run docker-down`. `WITH_DEMUCS=1 ./run docker`.
- ⚠️ 컨테이너는 Linux — CoreML/MPS 없음. Stemdeck 미동작(→demucs), torch CPU.
  librosa 폴백 분석은 정상. CoreML 필요 시 로컬 `./run`.
- `.github/workflows/docker-publish.yml` : `main` push / `v*.*.*` 태그 / 수동 시
  amd64(`ubuntu-latest`)+arm64(`ubuntu-24.04-arm`) 매트릭스 빌드 → push-by-digest →
  merge job이 멀티아치 매니페스트를 GHCR에 발행
  (`ghcr.io/jkove94/autoscore-{backend,frontend}`, `provenance:false`, gha 캐시).
  `docker-compose.yml` 에 `image:` 추가 → `docker compose pull` 가능.
  `.dockerignore` 에 `.env`/`.github` 추가. **최초 발행 후 Packages 를 Public 전환 필요.**
- Docker Hub 동시 발행(선택): merge job이 repo Secret `DOCKERHUB_USERNAME` +
  `DOCKERHUB_TOKEN` 있으면 `docker.io/<user>/autoscore-{backend,frontend}` 에도
  `imagetools create` 로 태그 발행(GHCR 다이제스트 소스 → 크로스 레지스트리 복사).
  미설정 시 GHCR 만(기존 동작). Docker Desktop 검색은 Hub 전용이라 이게 있어야 검색됨.

## 후속 검증 항목 (기능 구현 완료, 환경 제약으로 미실행)

1. `audio_analyzer` 프리미엄 백엔드(basic-pitch/essentia/madmom) 실제 설치·품질 비교.
2. 브라우저 E2E (크롬 확장 연결 후) — OSMD 렌더/커서/재생/축약뷰 시각 확인.
3. 마디 클릭 선택(OSMD SVG hit-test) 고도화 — 현재는 번호 칩 선택.
4. D.S. al Coda 를 RepeatFinder 앞단에서 우선 적용하는 옵션(후렴 반복 가독성).
