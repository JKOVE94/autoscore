#!/usr/bin/env bash
# AutoScore environment bootstrap (macOS / Apple Silicon).
#
# Installs system prerequisites via Homebrew, then runs `./run setup`.
#
#   scripts/bootstrap.sh              system prereqs + ./run setup
#   scripts/bootstrap.sh --full       + premium backends (demucs, basic-pitch,
#                                       madmom, essentia) into the venv
#   scripts/bootstrap.sh --yes        don't prompt before `brew install`
#
# Idempotent: re-running only installs what is missing.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FULL=0 ; ASSUME_YES=0
for a in "$@"; do
  case "$a" in
    --full) FULL=1 ;;
    --yes|-y) ASSUME_YES=1 ;;
    -h|--help) sed -n '2,11p' "${BASH_SOURCE[0]}" | sed 's/^#\{0,1\} \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $a" >&2; exit 1 ;;
  esac
done

c_reset=$'\033[0m'; c_bold=$'\033[1m'; c_grn=$'\033[32m'; c_yel=$'\033[33m'; c_red=$'\033[31m'; c_dim=$'\033[2m'
ok()   { printf "  ${c_grn}✓${c_reset} %s\n" "$1"; }
warn() { printf "  ${c_yel}!${c_reset} %s\n" "$1"; }
err()  { printf "  ${c_red}✗${c_reset} %s\n" "$1"; }
step() { printf "\n${c_bold}%s${c_reset}\n" "$1"; }

confirm() {
  [ "$ASSUME_YES" -eq 1 ] && return 0
  printf "  %s [y/N] " "$1"
  read -r reply
  case "$reply" in y|Y|yes) return 0 ;; *) return 1 ;; esac
}

[ "$(uname -s)" = "Darwin" ] || { err "This bootstrap targets macOS. On Linux, install python3.11/node/ffmpeg with your package manager, then run ./run setup."; exit 1; }

# --- Homebrew -------------------------------------------------------------
step "Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  err "Homebrew is not installed. Install it first:"
  echo '    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  exit 1
fi
ok "brew $(brew --version | head -1 | awk '{print $2}')"

# --- system packages ----------------------------------------------------
have_python() {
  local c
  for c in python3.12 python3.11 python3.10 \
           "$HOME/anaconda3/bin/python3.11" "$HOME/miniconda3/bin/python3.11" \
           /opt/homebrew/bin/python3.11 /opt/homebrew/bin/python3.12; do
    command -v "$c" >/dev/null 2>&1 && return 0
    [ -x "$c" ] && return 0
  done
  return 1
}

need_pkgs=()
have_python || need_pkgs+=("python@3.11")
command -v node >/dev/null 2>&1 || need_pkgs+=("node")
command -v ffmpeg >/dev/null 2>&1 || need_pkgs+=("ffmpeg")

java_ok=0
if /usr/libexec/java_home -v 17 >/dev/null 2>&1; then java_ok=1; fi
[ "$java_ok" -eq 1 ] || need_pkgs+=("openjdk@17")

step "System packages"
if [ ${#need_pkgs[@]} -eq 0 ]; then
  ok "python@3.11, node, ffmpeg, Java 17 all present"
else
  echo "  will install: ${need_pkgs[*]}"
  if confirm "run 'brew install ${need_pkgs[*]}'?"; then
    brew install "${need_pkgs[@]}"
    ok "installed ${need_pkgs[*]}"
    if printf '%s\n' "${need_pkgs[@]}" | grep -q openjdk@17; then
      warn "openjdk@17 is keg-only. To let Audiveris find Java 17, run:"
      echo "    sudo ln -sfn $(brew --prefix)/opt/openjdk@17/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk-17.jdk"
    fi
  else
    warn "skipped — ./run setup may fail without Python 3.11 / Node"
  fi
fi

# --- project setup (venv + npm + .env) --------------------------------
step "Project setup"
"$ROOT/run" setup

# --- premium backends (optional) -------------------------------------
if [ "$FULL" -eq 1 ]; then
  step "Premium analysis backends (--full)"
  PIP="$ROOT/backend/.venv/bin/pip"
  ENV_FILE="$ROOT/backend/.env"

  printf "  ${c_dim}demucs (stem separation fallback)…${c_reset}\n"
  if "$PIP" install -q demucs; then
    ok "demucs installed"
    if grep -q '^STEM_FALLBACK=none' "$ENV_FILE" 2>/dev/null; then
      sed -i '' 's/^STEM_FALLBACK=none/STEM_FALLBACK=demucs/' "$ENV_FILE"
      ok "backend/.env: STEM_FALLBACK=demucs (mode 1/2 now work without Stemdeck)"
    fi
  else
    warn "demucs install failed — keep using Stemdeck for separation"
  fi

  printf "  ${c_dim}basic-pitch[coreml] (melody transcription)…${c_reset}\n"
  "$PIP" install -q "basic-pitch[coreml]" && ok "basic-pitch installed" \
    || warn "basic-pitch install failed — melody uses the librosa/pyin fallback"

  printf "  ${c_dim}madmom (downbeat tracking)…${c_reset}\n"
  "$PIP" install -q cython "numpy<2" >/dev/null 2>&1 || true
  "$PIP" install -q madmom && ok "madmom installed" \
    || warn "madmom install failed (common on new numpy) — rhythm uses librosa"

  printf "  ${c_dim}essentia (key + chords)…${c_reset}\n"
  "$PIP" install -q essentia && ok "essentia installed" \
    || warn "essentia install failed (hard on Apple Silicon) — harmony uses chroma templates"
fi

# --- summary --------------------------------------------------------
step "Result"
"$ROOT/run" doctor || true

printf "\n${c_bold}Bootstrap done.${c_reset}  Start with:  ${c_grn}./run${c_reset}\n"
[ "$FULL" -eq 0 ] && printf "${c_dim}For higher-quality analysis and demucs separation: scripts/bootstrap.sh --full${c_reset}\n"
echo "Stemdeck (CoreML separation) and Audiveris (OMR) are manual installs — see README."
