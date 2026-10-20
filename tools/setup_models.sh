#!/usr/bin/env bash
# Один раз: ставит распознавание речи для subtitles.py (≈650 МБ, качается с GitHub).
set -e
DIR="${HORROR_MODELS:-$HOME/.cache/horror-models}"
mkdir -p "$DIR"
pip install --break-system-packages -q sherpa-onnx opencv-python-headless pillow numpy 2>/dev/null \
  || pip install -q sherpa-onnx opencv-python-headless pillow numpy
BASE=https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models
[ -f "$DIR/silero_vad.onnx" ] || curl -sSL -o "$DIR/silero_vad.onnx" "$BASE/silero_vad.onnx"
if [ ! -d "$DIR/sherpa-onnx-whisper-small" ]; then
  curl -sSL -o "$DIR/w.tar.bz2" "$BASE/sherpa-onnx-whisper-small.tar.bz2"
  tar xjf "$DIR/w.tar.bz2" -C "$DIR" && rm "$DIR/w.tar.bz2"
fi
echo "Модели готовы в $DIR"
