#!/usr/bin/env bash
# Linux counterpart of setup.ps1. Run from anywhere:
#   bash scripts/setup.sh            # or: PYTHON=python3.12 bash scripts/setup.sh
# Creates .venv/, prepares .runtime/ (external tools only), downloads model, builds frontend.
set -euo pipefail

PYTHON="${PYTHON:-python3}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

die() { echo "ERROR: $*" >&2; exit 1; }
warn() { echo "WARNING: $*" >&2; }

# Enable corepack (ignore errors if no permission; corepack commands still work)
corepack enable 2>/dev/null || true

command -v "$PYTHON" >/dev/null 2>&1 || die "Python 3.12 or later is required (PYTHON=$PYTHON not found)."
TASK_PYTHON="$("$PYTHON" -c 'import sys; print(sys.executable)')"
"$TASK_PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' \
  || die "Python 3.12 or later is required (found $("$TASK_PYTHON" -V 2>&1))."

# 1) Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  "$TASK_PYTHON" -m venv .venv || die "Virtual environment creation failed."
fi

# Use venv python
VENV_PYTHON="$ROOT/.venv/bin/python"

# 2) Install all Python dependencies in venv
echo "Installing Python dependencies..."
"$VENV_PYTHON" -m pip install --upgrade pip

# App packages. The lock file also lists Windows-only packages (pythonnet, clr_loader);
# they install as plain Python packages and are only used by the Windows desktop window.
"$VENV_PYTHON" -m pip install --upgrade -r requirements.lock.txt \
  || die "Python dependency installation failed."

# Document packages. tesserocr compiles against Tesseract; if its headers are missing,
# continue without it and say so (image OCR is then unavailable).
if ! "$VENV_PYTHON" -m pip install --upgrade -r requirements.files.lock.txt; then
  warn "Document packages failed to install; retrying without tesserocr (image OCR will be unavailable)."
  warn "To enable OCR install the build headers first, e.g.: sudo apt install libtesseract-dev libleptonica-dev tesseract-ocr-kor (see README.md)"
  FILES_NO_OCR="$(mktemp)"
  grep -vi '^tesserocr' requirements.files.lock.txt > "$FILES_NO_OCR"
  "$VENV_PYTHON" -m pip install --upgrade -r "$FILES_NO_OCR" \
    || { rm -f "$FILES_NO_OCR"; die "Document dependency installation failed."; }
  rm -f "$FILES_NO_OCR"
fi

# CPU model runtime. The +cpu local version exists on the PyTorch CPU index for x86_64 Linux;
# other CPUs (for example aarch64) use the plain 2.9.1 wheel from the same index.
case "$(uname -m)" in
  x86_64|amd64) TORCH="torch==2.9.1+cpu" ;;
  *)            TORCH="torch==2.9.1" ;;
esac
"$VENV_PYTHON" -m pip install --upgrade --index-url https://download.pytorch.org/whl/cpu "$TORCH" \
  || die "CPU model runtime installation failed."
"$VENV_PYTHON" -m pip install --upgrade -r requirements.model-a.lock.txt \
  || die "Model dependency installation failed."

# 3) Prepare external tools (not pip packages)
echo "Preparing external tools..."
# Drop links from a previous run first so its SHA-256 check never sees system files.
find .runtime/file-tools/tessdata -maxdepth 1 -type l -delete 2>/dev/null || true
"$VENV_PYTHON" scripts/prepare/prepare_file_tools.py \
  || die "Document tool preparation failed."

# Linux has no portable LibreOffice / pinned OCR data here: reuse system installs through
# links with the file names the backend expects. These are not the pinned Windows builds.
TOOLS=".runtime/file-tools"
if [ ! -e "$TOOLS/libreoffice/program/soffice.com" ]; then
  if SOFFICE="$(command -v soffice || command -v libreoffice)"; then
    mkdir -p "$TOOLS/libreoffice/program"
    ln -sf "$(readlink -f "$SOFFICE")" "$TOOLS/libreoffice/program/soffice.com"
    echo "Linked system LibreOffice: $SOFFICE"
  else
    warn "LibreOffice not found; XLSX value-copy checks are unavailable (sudo apt install libreoffice-calc)."
  fi
fi
for lang in eng kor; do
  if [ ! -e "$TOOLS/tessdata/$lang.traineddata" ]; then
    FOUND=""
    for dir in /usr/share/tesseract-ocr/*/tessdata /usr/share/tessdata /usr/local/share/tessdata /usr/share/tesseract-ocr/tessdata; do
      [ -f "$dir/$lang.traineddata" ] && { FOUND="$dir/$lang.traineddata"; break; }
    done
    if [ -n "$FOUND" ]; then
      mkdir -p "$TOOLS/tessdata"
      ln -sf "$FOUND" "$TOOLS/tessdata/$lang.traineddata"
      echo "Linked system OCR data: $FOUND"
    else
      warn "Tesseract '$lang' data not found; image OCR is limited (sudo apt install tesseract-ocr-$([ "$lang" = kor ] && echo kor || echo eng))."
    fi
  fi
done
command -v java >/dev/null 2>&1 || warn "Java not found; HWP reading is unavailable (HWPX works without it)."

# Download and verify A model
"$VENV_PYTHON" scripts/prepare/prepare_model_a.py \
  || die "A model preparation failed."

# 4) Frontend (using npx pnpm)
echo "Installing frontend dependencies..."
npx --yes pnpm@12.15.0 install --frozen-lockfile || die "Frontend dependency installation failed."
npx --yes pnpm@12.15.0 run build || die "Frontend build failed."

echo "Setup complete. Start the app with: bash scripts/start.sh"
