#!/usr/bin/env bash
# Стиль канала для длинных видео: холодный цвет, зерно, виньетка (+ субтитры). Камера НЕ трясётся.
#
#   bash tools/grade.sh вход.mp4 выход.mp4 [субтитры.ass]
#
# Ночной таймкод камеры поверх старой надписи — см. README, раздел «Таймкод камеры».
set -e
IN="$1"; OUT="$2"; ASS="$3"
[ -z "$OUT" ] && { echo "bash tools/grade.sh вход.mp4 выход.mp4 [субтитры.ass]"; exit 1; }
VF="eq=contrast=1.07:saturation=0.86:gamma=0.97,colorbalance=rs=-0.04:bs=0.05:rh=0.03:bh=-0.02,vignette=angle=PI/4.6,noise=alls=5:allf=t"
[ -n "$ASS" ] && VF="$VF,ass=$ASS"
ffmpeg -v error -y -i "$IN" -vf "$VF" -c:v libx264 -preset medium -crf 21 -maxrate 12M -bufsize 24M \
  -pix_fmt yuv420p -c:a copy -movflags +faststart "$OUT"
echo "Готово: $OUT"
