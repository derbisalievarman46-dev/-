#!/usr/bin/env python3
"""Находит и убирает водяной знак «Dola AI» (в том числе прыгающий по кадру).

Использование:
    python3 tools/remove_watermark.py вход.mp4 выход.mp4

Как работает: в каждом кадре ищет надпись по шаблонам из tools/templates,
собирает места и отрезки времени, где она видна, и закрывает их фильтром
ffmpeg delogo. Звук копируется без изменений.
"""
import os, subprocess, sys
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = ["dola_small.png", "dola_large.png"]
SCALES = (0.85, 1.0, 1.15)
THRESHOLD = 0.45      # уверенность совпадения
SPREAD = 18           # сколько кадров до/после закрывать (появление/исчезание)
PAD = 6               # запас по краям, px


def hp(g):
    g = g.astype(np.float32)
    return g - cv2.GaussianBlur(g, (0, 0), 3)


def detect(video):
    tpls = []
    for name in TEMPLATES:
        t = hp(cv2.imread(os.path.join(HERE, "templates", name), 0))
        for s in SCALES:
            tpls.append(cv2.resize(t, None, fx=s, fy=s))
    cap = cv2.VideoCapture(video)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    hits, n = [], 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        g = hp(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY))
        # почти чёрный кадр пропускаем — там нечего закрывать
        if fr.mean() > 4:
            best = (0, None)
            for t in tpls:
                m = cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED)
                _, mx, _, loc = cv2.minMaxLoc(m)
                if mx > best[0]:
                    best = (mx, (loc[0], loc[1], t.shape[1], t.shape[0]))
            if best[0] >= THRESHOLD:
                hits.append((n, best[1]))
        n += 1
    return hits, n, W, H


def group(hits, total, W, H):
    clusters = []   # [x0,y0,x1,y1, set(frames)]
    for f, (x, y, w, h) in hits:
        for c in clusters:
            if abs(c[0] - x) < 40 and abs(c[1] - y) < 40:
                c[0] = min(c[0], x); c[1] = min(c[1], y)
                c[2] = max(c[2], x + w); c[3] = max(c[3], y + h)
                c[4].add(f); break
        else:
            clusters.append([x, y, x + w, y + h, {f}])
    out = []
    for x0, y0, x1, y1, frames in clusters:
        fs = set()
        for f in frames:
            fs.update(range(max(0, f - SPREAD), min(total - 1, f + SPREAD) + 1))
        fs = sorted(fs); ranges = []
        for f in fs:
            if ranges and f == ranges[-1][1] + 1:
                ranges[-1][1] = f
            else:
                ranges.append([f, f])
        x0 = max(1, x0 - PAD); y0 = max(1, y0 - PAD)
        x1 = min(W - 2, x1 + PAD); y1 = min(H - 2, y1 + PAD)
        out.append((x0, y0, x1 - x0, y1 - y0, ranges))
    return out


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]
    hits, total, W, H = detect(src)
    boxes = group(hits, total, W, H)
    if not boxes:
        print("Водяной знак не найден — копирую файл как есть.")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-c", "copy", dst], check=True)
        return
    filters = []
    for x, y, w, h, ranges in boxes:
        en = "+".join(f"between(n\\,{a}\\,{b})" for a, b in ranges)
        filters.append(f"delogo=x={x}:y={y}:w={w}:h={h}:enable='{en}'")
        print(f"знак в зоне x={x} y={y} {w}x{h}, кадры: {ranges}")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", ",".join(filters),
                    "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
                    "-c:a", "copy", dst], check=True)
    print("Готово:", dst)


if __name__ == "__main__":
    main()
