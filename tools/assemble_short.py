#!/usr/bin/env python3
"""Собирает шортс из кусков: склейка, плашки в стиле серии, чёрный финал.

Пример (Part 2 с женой):
    python3 tools/assemble_short.py -o part2.mp4 \\
        --clip кусок1.mp4:3.0 --clip кусок2.mp4 \\
        --top "Part 2. 3:13 AM. Bedroom camera" --top-until 3.6 \\
        --end "Which one did I marry?" --end-from 26.0

--clip файл[:начало[:конец]]  — секунды; можно указывать несколько раз, по порядку.
Куски лучше заранее прогнать через remove_watermark.py.
"""
import argparse, json, os, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "templates", "Inter-Medium.otf")


def plate(text, path, size):
    f = ImageFont.truetype(FONT, size)
    l, t, r, b = f.getbbox(text)
    w, h = r - l + 36, size + 26
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=12, fill=(238, 238, 238, 225))
    d.text((18, (h - size) // 2 - 3), text, font=f, fill=(20, 20, 20, 255))
    im.save(path)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
                          "-of", "json", path], capture_output=True, text=True).stdout
    j = json.loads(out); st = j["streams"]
    v = next(s for s in st if s["codec_type"] == "video")
    return v["width"], v["height"], any(s["codec_type"] == "audio" for s in st), float(j["format"]["duration"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--clip", action="append", required=True)
    ap.add_argument("--top"); ap.add_argument("--top-until", type=float, default=3.5)
    ap.add_argument("--end"); ap.add_argument("--end-from", type=float)
    ap.add_argument("--tail", type=float, default=2.2, help="секунд чёрного экрана в конце")
    ap.add_argument("--fps", type=int, default=24)
    a = ap.parse_args()

    tmp = tempfile.mkdtemp()
    W, H, _, _ = probe(a.clip[0].split(":")[0])
    inputs, fc, cat = [], [], []
    for i, spec in enumerate(a.clip):
        parts = spec.split(":")
        path = parts[0]
        ss = parts[1] if len(parts) > 1 and parts[1] else None
        to = parts[2] if len(parts) > 2 and parts[2] else None
        args = []
        if ss: args += ["-ss", ss]
        if to: args += ["-to", to]
        inputs += args + ["-i", path]
        _, _, has_a, dur = probe(path)
        dur = (float(to) if to else dur) - (float(ss) if ss else 0)
        fc.append(f"[{i}:v]fps={a.fps},scale={W}:{H},setsar=1,setpts=PTS-STARTPTS,format=yuv420p[v{i}]")
        if has_a:
            fc.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}]")
        else:
            fc.append(f"anullsrc=r=44100:cl=stereo,atrim=0:{dur:.3f}[a{i}]")
        cat.append(f"[v{i}][a{i}]")
    n = len(a.clip)
    inputs += ["-f", "lavfi", "-t", str(a.tail), "-i", f"color=c=black:s={W}x{H}:r={a.fps}",
               "-f", "lavfi", "-t", str(a.tail), "-i", "anullsrc=r=44100:cl=stereo"]
    fc.append(f"[{n}:v]format=yuv420p[vb]"); fc.append(f"[{n+1}:a]aformat=channel_layouts=stereo[ab]")
    fc.append("".join(cat) + f"[vb][ab]concat=n={n+1}:v=1:a=1[cv][ca]")
    last, k = "cv", n + 2
    if a.top:
        p = os.path.join(tmp, "top.png"); plate(a.top, p, round(W / 21)); inputs += ["-i", p]
        fc.append(f"[{last}][{k}:v]overlay=x=24:y=24:enable='between(t,0.2,{a.top_until})'[o1]"); last = "o1"; k += 1
    if a.end:
        p = os.path.join(tmp, "end.png"); plate(a.end, p, round(W / 19)); inputs += ["-i", p]
        start = a.end_from if a.end_from is not None else 0
        fc.append(f"[{last}][{k}:v]overlay=x=(W-w)/2:y=H-h-{round(H*0.13)}:enable='gte(t,{start})'[o2]"); last = "o2"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc),
                    "-map", f"[{last}]", "-map", "[ca]", "-shortest",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", a.out], check=True)
    print("Готово:", a.out)


if __name__ == "__main__":
    main()
