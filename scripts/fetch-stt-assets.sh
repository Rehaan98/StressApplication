#!/usr/bin/env bash
# Fetches StressAI's on-device speech assets into frontend/public/ (local-only,
# never committed — see frontend/.gitignore).
#
#   1. ONNX Runtime WASM binaries — copied from the installed
#      @xenova/transformers npm package (version-matched by construction,
#      no network needed).
#   2. Whisper tiny.en model files (~155MB) — downloaded once from Hugging
#      Face, then served from /models/ with zero external requests at runtime.
#
# Usage: ./scripts/fetch-stt-assets.sh   (run from the repo root)
set -e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$ROOT_DIR/frontend"
ORT_SRC="$FRONTEND/node_modules/@xenova/transformers/dist"
ORT_DST="$FRONTEND/public/vendor/ort"
MODEL_DST="$FRONTEND/public/models/Xenova/whisper-tiny.en"
BASE="https://huggingface.co/Xenova/whisper-tiny.en/resolve/main"

mkdir -p "$ORT_DST" "$MODEL_DST/onnx" "$FRONTEND/public/vendor"

echo "[stt-assets] building browser speech bundle (esbuild, fully local)..."
SHIM="$ROOT_DIR/scripts/esbuild-shims/empty.js"
(cd "$FRONTEND" && npx -y esbuild@0.24.2 \
  node_modules/@xenova/transformers/src/transformers.js \
  --bundle --format=esm --platform=browser --minify \
  --outfile=public/vendor/transformers.bundle.mjs \
  --alias:onnxruntime-node="$SHIM" --alias:sharp="$SHIM" \
  --alias:fs="$SHIM" --alias:path="$SHIM" --alias:url="$SHIM" \
  --log-level=warning)

echo "[stt-assets] copying ONNX Runtime WASM from npm package..."
cp "$ORT_SRC"/ort-wasm.wasm "$ORT_SRC"/ort-wasm-simd.wasm \
   "$ORT_SRC"/ort-wasm-threaded.wasm "$ORT_SRC"/ort-wasm-simd-threaded.wasm \
   "$ORT_DST"/

echo "[stt-assets] downloading Whisper tiny.en model files (~155MB, one time)..."
FILES="config.json generation_config.json preprocessor_config.json
tokenizer.json tokenizer_config.json vocab.json merges.txt normalizer.json
added_tokens.json special_tokens_map.json"
for f in $FILES; do
  [ -s "$MODEL_DST/$f" ] || curl -sSL --retry 3 -o "$MODEL_DST/$f" "$BASE/$f"
done
for f in onnx/encoder_model.onnx onnx/decoder_model_merged.onnx; do
  [ -s "$MODEL_DST/$f" ] || curl -sSL --retry 3 -o "$MODEL_DST/$f" "$BASE/$f"
done

echo "[stt-assets] verifying..."
ls "$ORT_DST" "$MODEL_DST" "$MODEL_DST/onnx"
du -sh "$MODEL_DST"
echo "[stt-assets] done. Restart the frontend dev server."
