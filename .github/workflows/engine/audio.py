"""Voix off (TTS gratuits, cascade de moteurs), effets sonores synthétisés et mixage."""
import os
import shutil
import subprocess
import wave
import numpy as np

SR = 44100


# ------------------------------------------------------------------ TTS
def _run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, **kw)


def tts_piper(text, out, voice_model):
    exe = shutil.which("piper")
    if not exe or not voice_model or not os.path.exists(voice_model):
        raise RuntimeError("piper indisponible")
    raw = out + ".raw.wav"
    _run([exe, "--model", voice_model, "--output_file", raw], input=text.encode("utf-8"))
    _to_sr(raw, out)


def tts_espeak(text, out, lang="fr"):
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise RuntimeError("espeak indisponible")
    raw = out + ".raw.wav"
    _run([exe, "-v", lang, "-s", "165", "-w", raw, text])
    _to_sr(raw, out)


def tts_flite(text, out, voice="rms"):
    txt = out + ".txt"
    with open(txt, "w") as f:
        f.write(text)
    raw = out + ".raw.wav"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"flite=textfile={txt}:voice={voice}", raw])
    # flite est lent et monotone : on accélère légèrement et on hausse un peu la hauteur
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af",
          "asetrate=16000*1.06,aresample=16000,atempo=1.08,highpass=f=90,acompressor=threshold=-18dB:ratio=3,volume=1.6",
          "-ar", str(SR), "-ac", "1", out])


def _to_sr(src, dst):
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", "acompressor=threshold=-18dB:ratio=2.5",
          "-ar", str(SR), "-ac", "1", dst])


def synthesize(text, out, engine="auto", lang="en", piper_model=None):
    """Essaie les moteurs dans l'ordre : piper (naturel) > espeak-ng > flite. Renvoie le moteur utilisé."""
    order = {"auto": ["piper", "espeak", "flite"], "piper": ["piper", "espeak", "flite"],
             "espeak": ["espeak", "flite"], "flite": ["flite"]}[engine]
    if lang != "en" and "flite" in order and order[0] == "flite":
        order = ["espeak", "flite"]
    errs = []
    for eng in order:
        try:
            if eng == "piper":
                tts_piper(text, out, piper_model or os.environ.get("PIPER_MODEL"))
            elif eng == "espeak":
                tts_espeak(text, out, lang)
            else:
                if lang != "en":
                    errs.append("flite ne parle qu'anglais")
                tts_flite(text, out)
            return eng
        except Exception as e:  # noqa
            errs.append(f"{eng}: {e}")
    raise RuntimeError("Aucun moteur TTS disponible: " + "; ".join(errs))


def read_wav(path):
    with wave.open(path) as w:
        n = w.getnframes()
        data = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2:
            data = data.reshape(-1, 2).mean(1)
        return data


def write_wav(path, data):
    data = np.clip(data, -1, 1)
    with wave.open(path, "w") as w:
        w.setnchannels(2 if data.ndim == 2 else 1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((data * 32767).astype(np.int16).tobytes())


def trim_silence(x, thresh=0.01):
    idx = np.where(np.abs(x) > thresh)[0]
    if len(idx) == 0:
        return x
    a = max(0, idx[0] - int(0.02 * SR))
    b = min(len(x), idx[-1] + int(0.06 * SR))
    return x[a:b]


# ------------------------------------------------------------------ SFX
_rng = np.random.default_rng(7)


def _env(n, a=0.005, r=0.2):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / max(r, 1e-4))
    return e


def _lowpass(x, alpha):
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += alpha * (x[i] - acc)
        y[i] = acc
    return y


def sfx_whoosh(d=0.45):
    n = int(d * SR)
    noise = _rng.standard_normal(n).astype(np.float32)
    t = np.linspace(0, 1, n)
    # balayage de filtre via moyenne glissante variable (approx. rapide)
    lo = np.convolve(noise, np.ones(30) / 30, mode="same")
    hi = noise - np.convolve(noise, np.ones(4) / 4, mode="same")
    mix = lo * (1 - t) + hi * t * 0.5 + lo * 0.4
    env = np.sin(np.pi * t) ** 1.5
    return (mix * env * 0.9).astype(np.float32)


def sfx_pop():
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    f = 900 * np.exp(-t * 18) + 300
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * _env(n, 0.001, 0.04) * 0.6).astype(np.float32)


def sfx_step(heavy=False):
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    thump = np.sin(2 * np.pi * (70 if heavy else 110) * t) * _env(n, 0.001, 0.03)
    click = np.convolve(_rng.standard_normal(n), np.ones(6) / 6, mode="same") * _env(n, 0.0005, 0.012)
    return ((thump * 0.7 + click * 0.5) * (0.55 if heavy else 0.35)).astype(np.float32)


def sfx_impact():
    n = int(1.1 * SR)
    t = np.arange(n) / SR
    f = 120 * np.exp(-t * 4) + 38
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.35)
    noise = np.convolve(_rng.standard_normal(n), np.ones(12) / 12, mode="same") * _env(n, 0.001, 0.08)
    sting = sum(np.sin(2 * np.pi * fr * t) for fr in (440, 466, 622)) / 3 * _env(n, 0.01, 0.5) * 0.25
    return ((boom * 0.9 + noise * 0.6 + sting) * 0.9).astype(np.float32)


def sfx_click():
    n = int(0.03 * SR)
    return (_rng.standard_normal(n) * _env(n, 0.0002, 0.004) * 0.25).astype(np.float32)


def sfx_crash():
    n = int(0.6 * SR)
    noise = _rng.standard_normal(n) - np.convolve(_rng.standard_normal(n), np.ones(3) / 3, mode="same")
    t = np.arange(n) / SR
    tink = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * (8 + i)) for i, f in enumerate((2100, 3300, 4700)))
    return ((noise * _env(n, 0.001, 0.09) * 0.5 + tink * 0.15)).astype(np.float32)


def sfx_ding():
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    return ((np.sin(2 * np.pi * 1318 * t) + 0.5 * np.sin(2 * np.pi * 1976 * t)) * _env(n, 0.002, 0.25) * 0.3).astype(np.float32)


SFX = {"whoosh": sfx_whoosh, "pop": sfx_pop, "step": sfx_step, "step_heavy": lambda: sfx_step(True),
       "impact": sfx_impact, "click": sfx_click, "crash": sfx_crash, "ding": sfx_ding}


def music_bed(duration, mood="mystery"):
    """Nappe musicale originale générée (accords + pulsation), sans droits d'auteur."""
    n = int(duration * SR)
    t = np.arange(n) / SR
    chords = [(110, 130.8, 164.8), (87.3, 110, 130.8), (98, 123.5, 146.8), (82.4, 103.8, 123.5)]
    out = np.zeros(n, dtype=np.float32)
    bar = 2.0
    for i in range(int(duration / bar) + 1):
        a = int(i * bar * SR); b = min(n, int((i + 1) * bar * SR + 0.3 * SR))
        if a >= n:
            break
        tt = t[a:b] - t[a]
        env = np.minimum(1, tt / 0.4) * np.exp(-np.maximum(0, tt - bar) * 8)
        for f in chords[i % 4]:
            out[a:b] += (np.sin(2 * np.pi * f * tt) * 0.5 + np.sin(2 * np.pi * f * 2.003 * tt) * 0.15) * env * 0.09
    # pulsation (basse + hi-hat léger) pour la tension
    beat = 0.5
    for k in range(int(duration / beat)):
        a = int(k * beat * SR)
        m = min(n - a, int(0.25 * SR))
        if m <= 0:
            break
        tt = np.arange(m) / SR
        out[a:a + m] += np.sin(2 * np.pi * 55 * tt) * np.exp(-tt * 14) * 0.22
        if k % 2:
            hh = _rng.standard_normal(m) * np.exp(-tt * 60) * 0.03
            out[a:a + m] += hh
    fade = np.minimum(1, np.minimum(t / 0.8, (duration - t) / 1.2))
    return out * np.clip(fade, 0, 1)


def mix(duration, voice_clips, sfx_events, music=True):
    """voice_clips: [(start_s, np.array)], sfx_events: [(time_s, name, gain)] -> stéréo float32."""
    n = int(duration * SR) + SR
    voice = np.zeros(n, dtype=np.float32)
    for st, clip in voice_clips:
        a = int(st * SR)
        b = min(n, a + len(clip))
        voice[a:b] += clip[: b - a]
    left = voice.copy(); right = voice.copy()
    cache = {}
    for tm, name, gain, pan in sfx_events:
        if name not in cache:
            cache[name] = SFX[name]()
        c = cache[name] * gain
        a = int(tm * SR)
        if a >= n:
            continue
        b = min(n, a + len(c))
        left[a:b] += c[: b - a] * (1 - max(0, pan))
        right[a:b] += c[: b - a] * (1 + min(0, pan))
    if music:
        m = music_bed(duration)
        # ducking : la musique baisse quand la voix parle
        envv = np.convolve(np.abs(voice[: len(m)]), np.ones(4410) / 4410, mode="same")
        duck = 1 - np.clip(envv * 6, 0, 0.6)
        left[: len(m)] += m * duck
        right[: len(m)] += m * duck
    st = np.stack([left, right], 1)[: int(duration * SR)]
    peak = np.max(np.abs(st)) or 1
    return st / max(1.0, peak / 0.95)
