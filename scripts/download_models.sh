#!/usr/bin/env bash
# ---------------------------------------------------------------------
# download_models.sh
# ---------------------------------------------------------------------
# Fetches the local model weights this repo intentionally does NOT
# commit to git (see the "Local model weights" section in README.md).
# Run this once after cloning:
#
#   bash scripts/download_models.sh
#
# Safe to re-run - it skips any file that's already present and valid.
# ---------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELS_DIR="$REPO_ROOT/python/models"
mkdir -p "$MODELS_DIR"

# ── 1. Facial emotion CNN (FER2013, MIT-licensed public checkpoint) ───
EMOTION_FILE="$MODELS_DIR/emotion_model.h5"
EMOTION_URL="https://raw.githubusercontent.com/oarriaga/face_classification/master/trained_models/emotion_models/simple_CNN.530-0.65.hdf5"

if [ -f "$EMOTION_FILE" ]; then
  echo "[emotion model] already present at $EMOTION_FILE, skipping."
else
  echo "[emotion model] downloading (~7.5MB) from oarriaga/face_classification (MIT license)..."
  curl -fL -o "$EMOTION_FILE" "$EMOTION_URL"
  echo "[emotion model] saved to $EMOTION_FILE"
fi

# ── 2. Local LLM weights (Qwen2.5-1.5B-Instruct, Q4_K_M GGUF) ─────────
LLM_FILE="$REPO_ROOT/qwen2.5-1.5b-instruct-q4_k_m.gguf"
LLM_URL="https://github.com/KulboyRaj/Nova-social_Robot/releases/download/llm-weights-v1/qwen2.5-1.5b-instruct-q4_k_m.gguf"
LLM_SHA256="6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"

verify_llm() {
  echo "$LLM_SHA256  $LLM_FILE" | sha256sum -c - >/dev/null 2>&1
}

if [ -f "$LLM_FILE" ] && verify_llm; then
  echo "[llm weights] already present and verified at $LLM_FILE, skipping."
else
  echo "[llm weights] downloading (~1.1GB) from the llm-weights-v1 GitHub release..."
  curl -fL -o "$LLM_FILE" "$LLM_URL"
  echo "[llm weights] verifying checksum..."
  if ! verify_llm; then
    echo "ERROR: checksum mismatch for $LLM_FILE - download may be corrupt. Aborting." >&2
    exit 1
  fi
  echo "[llm weights] saved and verified at $LLM_FILE"
fi

cat <<'EOF'

Done. Next step for the LLM:
  cd "$(dirname "$0")/.."   # repo root, where the Modelfile lives
  ollama create qwen2.5:1.5b-instruct -f Modelfile

Then verify:
  curl http://localhost:11434/api/chat -d '{"model":"qwen2.5:1.5b-instruct","messages":[{"role":"user","content":"hi"}],"stream":false}'
EOF    
