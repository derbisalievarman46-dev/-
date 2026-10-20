#!/usr/bin/env python3
"""Субтитры по голосу: точный текст из сценария + тайминг из распознавания речи.

Использование:
    python3 tools/subtitles.py --audio озвучка.mp3 --script сценарий.txt --lang ru --out palata9
    -> palata9.srt (для YouTube) и palata9.ass (для вшивания через grade.sh)

сценарий.txt — текст озвучки, как есть (абзацы с новой строки).
Модели качаются один раз: bash tools/setup_models.sh
"""
import argparse, json, os, re, subprocess, tempfile, wave, difflib
import numpy as np

MODELS = os.path.expanduser(os.environ.get("HORROR_MODELS", "~/.cache/horror-models"))

NUM = {
    "ru": [("2009", "две тысячи девятого"), ("9-й", "девятой"), ("9-я", "девятая"), ("40", "сорок"),
           ("20", "двадцать"), ("15", "пятнадцать"), ("10", "десять"), ("12", "двенадцать"), ("3", "три"), ("9", "девять")],
    "en": [("2009", "two thousand nine"), ("3:40", "three forty"), ("340", "three forty"), ("3:10", "three ten"),
           ("310", "three ten"), ("15", "fifteen"), ("20", "twenty"), ("12", "twelve"), ("9", "nine")],
}


def recognize(audio, lang):
    import sherpa_onnx
    m = os.path.join(MODELS, "sherpa-onnx-whisper-small")
    rec = sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=f"{m}/small-encoder.int8.onnx", decoder=f"{m}/small-decoder.int8.onnx",
        tokens=f"{m}/small-tokens.txt", language=lang, task="transcribe", num_threads=4)
    cfg = sherpa_onnx.VadModelConfig()
    cfg.silero_vad.model = os.path.join(MODELS, "silero_vad.onnx")
    cfg.silero_vad.min_silence_duration = 0.25
    cfg.silero_vad.min_speech_duration = 0.2
    cfg.silero_vad.max_speech_duration = 12
    cfg.sample_rate = 16000
    vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=600)
    wav = os.path.join(tempfile.mkdtemp(), "a.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", audio, "-ac", "1", "-ar", "16000", wav], check=True)
    with wave.open(wav) as f:
        a = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    res = []
    def drain():
        while not vad.empty():
            seg = vad.front
            s = rec.create_stream(); s.accept_waveform(16000, seg.samples); rec.decode_stream(s)
            st = seg.start / 16000
            res.append({"start": st, "end": st + len(seg.samples) / 16000, "text": s.result.text.strip()})
            vad.pop()
    win = cfg.silero_vad.window_size
    for i in range(0, len(a), win):
        vad.accept_waveform(a[i:i + win]); drain()
    vad.flush(); drain()
    return res


def letters(t, lang):
    t = t.lower()
    for x, y in NUM[lang]:
        t = t.replace(x, y)
    if lang == "ru":
        return re.sub(r"[^а-яё]", "", t).replace("ё", "е")
    return re.sub(r"[^a-z]", "", t)


def split_cues(text, lim=44):
    cues = []
    for line in text.strip().split("\n"):
        if not line.strip():
            continue
        buf = ""
        for p in re.split(r'(?<=[.!?…»"])\s+', line.strip()):
            if buf and len(buf) + 1 + len(p) <= lim:
                buf += " " + p
            else:
                if buf: cues.append(buf)
                buf = p
        if buf: cues.append(buf)
    return cues


def align(asr, cues, lang):
    ac, at, ach = [], [], []
    for ci, c in enumerate(asr):
        L = letters(c["text"], lang)
        for k, ch in enumerate(L):
            ac.append(ch); at.append(c["start"] + (k + .5) / len(L) * (c["end"] - c["start"])); ach.append(ci)
    sc, su = [], []
    for ui, u in enumerate(cues):
        for ch in letters(u, lang):
            sc.append(ch); su.append(ui)
    sm = difflib.SequenceMatcher(None, "".join(sc), "".join(ac), autojunk=False)
    s2a = np.full(len(sc), -1)
    for b in sm.get_matching_blocks():
        for k in range(b.size): s2a[b.a + k] = b.b + k
    idx = np.arange(len(sc)); g = s2a >= 0
    print(f"совпадение текста с голосом: {g.mean():.0%}")
    t = np.interp(idx, idx[g], np.array(at)[s2a[g]])
    chn = np.round(np.interp(idx, idx[g], np.array(ach)[s2a[g]])).astype(int)
    su = np.array(su); out = []
    for ui in range(len(cues)):
        p = np.where(su == ui)[0]; a, b = p[0], p[-1]
        st = asr[chn[a]]["start"] if t[a] - asr[chn[a]]["start"] < 0.6 else t[a] - 0.15
        en = asr[chn[b]]["end"] if asr[chn[b]]["end"] - t[b] < 1.2 else t[b] + 0.2
        out.append([float(st), float(en)])
    return out


def wrap(t, lim=34):
    if len(t) <= lim: return [t]
    w = t.split(" "); best = None
    for k in range(1, len(w)):
        l1, l2 = " ".join(w[:k]), " ".join(w[k:]); sc = abs(len(l1) - len(l2))
        if best is None or sc < best[0]: best = (sc, l1, l2)
    return [best[1], best[2]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audio", required=True); ap.add_argument("--script", required=True)
    ap.add_argument("--lang", choices=["ru", "en"], required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=1920); ap.add_argument("--height", type=int, default=1080)
    a = ap.parse_args()
    cues = split_cues(open(a.script, encoding="utf-8").read())
    times = align(recognize(a.audio, a.lang), cues, a.lang)
    srt, ass = [], []
    def s_ts(x): return f"{int(x//3600):02d}:{int(x%3600//60):02d}:{int(x%60):02d},{int(round((x%1)*1000)) % 1000:03d}"
    def a_ts(x): return f"{int(x//3600)}:{int(x%3600//60):02d}:{x%60:05.2f}"
    for k, (txt, (s, e)) in enumerate(zip(cues, times)):
        s = max(0, s - 0.05); e = e + 0.35
        if k + 1 < len(cues): e = min(e, times[k + 1][0] - 0.08)
        e = max(e, s + 0.7)
        lines = wrap(txt)
        srt.append(f"{k+1}\n{s_ts(s)} --> {s_ts(e)}\n" + "\n".join(lines) + "\n")
        ass.append(f"Dialogue: 0,{a_ts(s)},{a_ts(e)},Sub,,0,0,0,,{{\\fad(150,150)}}" + r"\N".join(lines))
    fs = round(a.height * 0.046)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {a.width}
PlayResY: {a.height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Inter Medium,{fs},&H00E6E6E6,&H00E6E6E6,&H00000000,&H78000000,0,0,0,0,100,100,0.5,0,1,2.0,3,2,200,200,{round(a.height*0.072)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    open(a.out + ".srt", "w", encoding="utf-8").write("\n".join(srt))
    open(a.out + ".ass", "w", encoding="utf-8").write(head + "\n".join(ass) + "\n")
    print("Готово:", a.out + ".srt", a.out + ".ass")


if __name__ == "__main__":
    main()
