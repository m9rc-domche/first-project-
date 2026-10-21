"""Pipeline complet : plan -> voix -> pré-passe (événements, caméra, QA) -> rendu -> mixage -> MP4."""
import json
import math
import os
import random
import re
import subprocess
import time

import cairocffi as cairo
import numpy as np

from . import audio, rig, world
from .easing import clamp, lerp, ease_in_out, ease_out, ease_out_back
from .motion import actor_state
from .world import W, H, GROUND

FPS = 30
ACTOR_SCALE = 1.32
FONT = "Noto Sans"
SAFE = 30


# ================================================================ planification
def _word_times(text, start, dur):
    words = text.split()
    weights = [max(2, len(re.sub(r"\W", "", w))) + (3 if re.search(r"[,.!?;:…]$", w) else 0) for w in words]
    tot = sum(weights) or 1
    out, t = [], start
    for w, k in zip(words, weights):
        d = dur * k / tot
        out.append((w, t, t + d))
        t += d
    return out


def _chunks(words, maxn=3):
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= maxn or re.search(r"[,.!?;:…]$", w[0]):
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)
    return chunks


def prepare_audio(spec, work, tts_engine="auto", log=print):
    lang = spec.get("lang", "en")
    t = 0.0
    used = set()
    for i, sc in enumerate(spec["scenes"]):
        wav = os.path.join(work, f"voice_{i:02d}.wav")
        used.add(audio.synthesize(sc["text"], wav, tts_engine, lang))
        clip = audio.trim_silence(audio.read_wav(wav))
        sc["_voice"] = clip
        vd = len(clip) / audio.SR
        lead = 0.12
        sc["start"] = t
        sc["voice_start"] = t + lead
        sc["voice_dur"] = vd
        sc["dur"] = max(1.6, vd + lead + 0.28) + (0.9 if i == len(spec["scenes"]) - 1 else 0)
        sc["words"] = _word_times(sc["text"], sc["voice_start"], vd)
        t += sc["dur"]
    spec["duration"] = t
    spec["_tts"] = sorted(used)
    log(f"voix: {', '.join(used)} | durée totale {t:.2f}s")
    return spec


def _hero(states):
    for aid, st in states.items():
        if aid == "hero":
            return st
    return next(iter(states.values()), None)


def prepass(spec):
    """Simule chaque frame : états des acteurs, caméra (lissée), événements sonores, données QA."""
    frames = []
    events = []
    nframes = int(math.ceil(spec["duration"] * FPS))
    cam_state = None
    last_step = {}
    last_click = -1
    rnd = random.Random(1)
    impacts = []
    phone_release = {}
    vanish_done = set()
    prev_bg = None
    for si, sc in enumerate(spec["scenes"]):
        sc["_bg_changed"] = sc["bg"] != prev_bg
        prev_bg = sc["bg"]
        events.append((sc["start"] + 0.0, "whoosh", 0.35 if sc["_bg_changed"] else 0.18, 0.0))
        if sc.get("emote"):
            events.append((sc["start"] + 0.55, "ding" if sc["emote"] == "idea" else "pop", 0.8, 0.0))
    for f in range(nframes):
        t = f / FPS
        si = max(i for i, s in enumerate(spec["scenes"]) if s["start"] <= t + 1e-6)
        sc = spec["scenes"][si]
        lt = t - sc["start"]
        states = {}
        for a in sc["actors"]:
            st = actor_state(a, lt, sc["dur"])
            if st is None:
                continue
            states[a["id"]] = st
            key = (si, a["id"])
            # pas synchronisés au cycle de marche
            if st["phase"] is not None:
                k = int(st["phase"] // math.pi)
                if key in last_step and k != last_step[key]:
                    pan = clamp((st["x"] - 540) / 900, -0.6, 0.6)
                    events.append((t, "step_heavy" if st["kind"] == "run" else "step",
                                   0.9 if a["id"] == "hero" else 0.6, pan))
                last_step[key] = k
            if st["kind"] == "type" and f - last_click >= 2 and rnd.random() < 0.7:
                events.append((t, "click", 0.7, 0.1)); last_click = f
            if st["kind"] == "shocked" and key not in vanish_done:
                at = st.get("seg_def", {}).get("at", 0.15)
                if st["local"] >= at:
                    events.append((t, "impact", 1.0, 0.0)); impacts.append(t); vanish_done.add(key)
            if st["kind"] == "throw" and key not in phone_release:
                rel = st.get("seg_def", {}).get("release", 0.55)
                if st["local"] >= rel:
                    j = rig.solve(st["pose"], st["x"], GROUND, ACTOR_SCALE, st["facing"])
                    phone_release[key] = (t, j["hand_f"], st["facing"])
                    events.append((t, "whoosh", 0.6, 0.3))
            if st["kind"] == "vanish" and (key, "v") not in vanish_done:
                vanish_done.add((key, "v")); events.append((t + 0.35, "whoosh", 0.5, 0.0)); events.append((t + 0.5, "ding", 0.5, 0.0))
        cam_state = _camera(sc, lt, states, cam_state, t, impacts, si)
        frames.append(dict(t=t, si=si, lt=lt, states=states, cam=cam_state["cam"]))
    # chute du téléphone -> fracas
    spec["_phones"] = {}
    for key, (t0, pos, facing) in phone_release.items():
        tg = _phone_ground_time(pos)
        spec["_phones"][key] = (t0, pos, facing)
        events.append((t0 + tg, "crash", 0.9, 0.2))
    events.sort()
    return frames, events


PHONE_V = (1050, -1350)
GRAV = 3200


def _phone_ground_time(pos):
    # résout y(t) = GROUND
    a, b, c = 0.5 * GRAV, PHONE_V[1], pos[1] - (GROUND - 20)
    return (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)


def _camera(sc, lt, states, prev, t, impacts, si):
    mode = sc.get("camera", "static")
    hero = _hero(states)
    hx = hero["x"] if hero else 540
    focus_y = GROUND - 520
    p = clamp(lt / sc["dur"])
    zoom = 1.0
    tx, ty = 540, 960
    if mode == "push_in":
        zoom = lerp(1.0, 1.22, ease_in_out(p)); tx = lerp(540, hx, 0.5 * ease_in_out(p)); ty = lerp(960, focus_y + 160, ease_in_out(p))
    elif mode == "pull_out":
        zoom = lerp(1.3, 1.0, ease_out(p)); tx = lerp(hx, 540, ease_out(p)); ty = lerp(focus_y + 160, 960, ease_out(p))
    elif mode == "track":
        lead = 140 * (hero["facing"] if hero else 1)
        tx = hx + lead; zoom = 1.08; ty = 990
    elif mode == "punch":
        zoom = 1.06; tx = 540
    rot = 0.0
    # punch-zoom + tremblement sur impact
    for it in impacts:
        u = t - it
        if 0 <= u < 0.9:
            zoom += 0.16 * math.exp(-u * 4) * (1 if mode != "pull_out" else 0.5)
            amp = 26 * math.exp(-u * 6)
            tx += math.sin(u * 83) * amp; ty += math.cos(u * 71) * amp
            rot += math.sin(u * 37) * 0.012 * math.exp(-u * 5)
            if mode == "punch" and hero:
                tx = lerp(tx, hx, 0.35 * math.exp(-u * 1.5))
    if prev is None or prev["si"] != si or mode != "track":
        cx, cy = tx, ty
        if prev is not None and prev["si"] == si and mode == "track":
            pass
    else:
        k = 0.12  # lissage caméra (suivi type "steadicam")
        cx = prev["cam"][0] + (tx - prev["cam"][0]) * k
        cy = prev["cam"][1] + (ty - prev["cam"][1]) * k
    if mode == "track" and (prev is None or prev["si"] != si):
        cx, cy = tx, ty
    return dict(si=si, cam=(cx, cy, zoom, rot))


# ================================================================ QA + corrections auto
def screen_bbox(j, cam):
    x0, y0, x1, y1 = rig.bbox(j)
    cx, cy, z, _ = cam
    f = lambda x, y: ((x - cx) * z + W / 2, (y - cy) * z + H / 2)
    a = f(x0, y0); b = f(x1, y1)
    return a[0], a[1], b[0], b[1]


def qa_frames(spec, frames):
    issues = []
    for si, sc in enumerate(spec["scenes"]):
        fr = [f for f in frames if f["si"] == si]
        out = 0
        for f in fr:
            st = f["states"].get("hero")
            if not st or st["kind"] == "vanish":
                continue
            j = rig.solve(st["pose"], st["x"], GROUND, ACTOR_SCALE, st["facing"])
            x0, y0, x1, y1 = screen_bbox(j, f["cam"])
            if x0 < SAFE or x1 > W - SAFE or y0 < SAFE or y1 > H - SAFE:
                out += 1
        ratio = out / max(1, len(fr))
        if ratio > 0.08:
            issues.append(dict(scene=si + 1, type="hero_hors_cadre", ratio=round(ratio, 2)))
        # texte trop long pour une scène
        if sc["voice_dur"] > 7.5:
            issues.append(dict(scene=si + 1, type="scene_trop_longue", seconds=round(sc["voice_dur"], 1)))
    return issues


def autofix(spec, issues, log=print):
    fixed = []
    for it in issues:
        sc = spec["scenes"][it["scene"] - 1]
        if it["type"] == "hero_hors_cadre":
            moving = any(sg.get("action") in ("walk", "run", "sneak") for a in sc["actors"] if a["id"] == "hero"
                         for sg in (a.get("actions") or [a]))
            if sc.get("camera") != "track" and moving:
                sc["camera"] = "track"; fixed.append(f"scène {it['scene']}: caméra -> suivi (héros sortait du cadre)")
            elif sc.get("camera") in ("push_in", "punch"):
                sc["camera"] = "static"; fixed.append(f"scène {it['scene']}: zoom retiré (héros coupé)")
            else:
                for a in sc["actors"]:
                    if a["id"] == "hero":
                        a["x"] = 540
                sc["camera"] = "static"; fixed.append(f"scène {it['scene']}: héros recentré")
    for m in fixed:
        log("auto-correction: " + m)
    return fixed


# ================================================================ dessin
def _caption(ctx, sc, t):
    words = sc["words"]
    chunks = _chunks(words)
    cur = None
    for ch in chunks:
        if ch[0][1] - 0.05 <= t:
            cur = ch
    if cur is None or t > cur[-1][2] + 0.6:
        return
    ctx.select_font_face(FONT, 0, 1)
    size = 92
    texts = [w[0].upper() for w in cur]
    ctx.set_font_size(size)
    space = size * 0.38
    widths = [ctx.text_extents(s)[4] * 1.1 for s in texts]
    total = sum(widths) + space * (len(texts) - 1)
    if total > W - 120:
        size *= (W - 120) / total; ctx.set_font_size(size)
        widths = [ctx.text_extents(s)[4] * 1.1 for s in texts]; space = size * 0.38
        total = sum(widths) + space * (len(texts) - 1)
    pop = ease_out_back(clamp((t - cur[0][1] + 0.05) / 0.18))
    y = 1680
    x = W / 2 - total / 2
    for (w, a, b), s, wd in zip(cur, texts, widths):
        active = a <= t < b + 0.05
        ctx.save()
        ctx.translate(x + wd / 2, y)
        sc_ = (0.6 + 0.4 * pop) * (1.08 if active else 0.98)
        ctx.scale(sc_, sc_)
        ctx.move_to(-wd / 2.2, size * 0.35)
        ctx.text_path(s)
        ctx.set_source_rgb(0, 0, 0); ctx.set_line_width(16); ctx.set_line_join(1); ctx.stroke_preserve()
        if active:
            ctx.set_source_rgb(1, 0.86, 0.1)
        else:
            ctx.set_source_rgb(1, 1, 1)
        ctx.fill()
        ctx.restore()
        x += wd + space


def _title(ctx, title, t):
    if not title:
        return
    a = clamp(t / 0.4)
    ctx.select_font_face(FONT, 0, 1); ctx.set_font_size(54)
    e = ctx.text_extents(title)
    w = min(W - 80, e[4] + 60)
    if e[4] + 60 > W - 80:
        ctx.set_font_size(54 * (W - 140) / e[4]); e = ctx.text_extents(title); w = e[4] + 60
    x = W / 2 - w / 2; y = 150
    ctx.set_source_rgba(0, 0, 0, 0.55 * a); world._rrect(ctx, x, y - 50, w, 80, 18); ctx.fill()
    ctx.set_source_rgba(1, 1, 1, a); ctx.move_to(W / 2 - e[4] / 2, y + 8); ctx.show_text(title)


def draw_frame(ctx, spec, fr):
    sc = spec["scenes"][fr["si"]]
    lt = fr["lt"]; t = fr["t"]; cam = fr["cam"]
    world.BACKGROUNDS.get(sc["bg"], world.bg_city_night)(ctx, cam, t)
    ctx.save(); world.layer(ctx, cam, 1.0)
    # ombres au sol
    for aid, st in fr["states"].items():
        ctx.save(); ctx.translate(st["x"], GROUND + 6); ctx.scale(1, 0.18)
        ctx.set_source_rgba(0, 0, 0, 0.35); ctx.arc(0, 0, 110, 0, 2 * math.pi); ctx.fill(); ctx.restore()
    actor_defs = {a["id"]: a for a in sc["actors"]}
    hero_head = None
    for aid in sorted(fr["states"], key=lambda k: 0 if k != "hero" else 1):
        st = fr["states"][aid]; ad = actor_defs[aid]
        j = rig.solve(st["pose"], st["x"], GROUND, ACTOR_SCALE, st["facing"])
        alpha = 1.0
        if st["kind"] == "vanish":
            alpha = 1 - clamp((st["local"] - 0.3) / 0.9)
            _sparkles(ctx, j, clamp((st["local"] - 0.3) / 1.2), t)
        if alpha <= 0.01:
            continue
        ctx.push_group()
        rig.draw(ctx, j, hat=ad.get("hat"))
        holds = ad.get("holds")
        key = (fr["si"], aid)
        released = key in spec.get("_phones", {}) and t >= spec["_phones"][key][0]
        if holds == "phone" and not released:
            hx, hy = j["hand_f"]
            world.draw_phone(ctx, hx + 6 * st["facing"], hy - 20, rot=-0.3 * st["facing"], s=ACTOR_SCALE * 0.8)
        ctx.pop_group_to_source(); ctx.paint_with_alpha(alpha)
        if aid == "hero":
            hero_head = j["head"]
    # téléphone lancé (balistique) + éclats
    for key, (t0, pos, facing) in spec.get("_phones", {}).items():
        if key[0] != fr["si"] or t < t0:
            continue
        u = t - t0; tg = _phone_ground_time(pos)
        if u < tg:
            px = pos[0] + PHONE_V[0] * facing * u; py = pos[1] + PHONE_V[1] * u + 0.5 * GRAV * u * u
            world.draw_phone(ctx, px, py, rot=u * 14 * facing, s=ACTOR_SCALE * 0.8)
        else:
            gx = pos[0] + PHONE_V[0] * facing * tg
            world.draw_shards(ctx, gx, GROUND - 20, clamp((u - tg) / 0.8))
    if sc["bg"] in world.FOREGROUNDS:
        ctx.restore(); world.FOREGROUNDS[sc["bg"]](ctx, cam, t); ctx.save(); world.layer(ctx, cam, 1.0)
    if sc.get("emote") and hero_head:
        k = (lt - 0.55) / 0.3
        world.draw_emote(ctx, sc["emote"], hero_head[0], hero_head[1] - 190, k, t)
    ctx.restore()
    world.vignette(ctx)


def draw_overlays(ctx, spec, fr):
    _title(ctx, spec.get("title"), fr["t"])
    _caption(ctx, spec["scenes"][fr["si"]], fr["t"])


def _sparkles(ctx, j, k, t):
    if k <= 0 or k >= 1:
        return
    r = random.Random(4)
    x0, y0, x1, y1 = rig.bbox(j)
    for i in range(60):
        px = r.uniform(x0, x1) + math.sin(t * 3 + i) * 20
        py = r.uniform(y0, y1) - k * r.uniform(150, 500)
        a = (1 - k) * (0.5 + 0.5 * math.sin(t * 10 + i))
        ctx.set_source_rgba(1, 0.95, 0.7, a); ctx.arc(px, py, r.uniform(3, 8) * (1 - k * 0.5), 0, 2 * math.pi); ctx.fill()


def _iris(ctx, prev_surface, k, center):
    """Transition en cercle : l'ancienne image reste dehors du cercle qui grandit."""
    if prev_surface is None or k >= 1:
        return
    r = ease_in_out(k) * 1.15 * math.hypot(W, H)
    ctx.save()
    ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    ctx.rectangle(0, 0, W, H); ctx.arc(center[0], center[1], max(1, r), 0, 2 * math.pi)
    ctx.clip()
    ctx.set_source_surface(prev_surface, 0, 0); ctx.paint()
    ctx.restore()
    if r > 40:
        ctx.save(); ctx.set_source_rgb(0, 0, 0); ctx.set_line_width(28)
        ctx.arc(center[0], center[1], r, 0, 2 * math.pi); ctx.stroke(); ctx.restore()


# ================================================================ orchestration
def render(spec, out_mp4, work, tts_engine="auto", preview_every=None, log=print, progress=None):
    os.makedirs(work, exist_ok=True)
    t0 = time.time()
    prepare_audio(spec, work, tts_engine, log)
    frames, events = prepass(spec)
    issues = qa_frames(spec, frames)
    fixes = []
    if issues:
        log(f"QA: {len(issues)} défaut(s) détecté(s): {issues}")
        fixes = autofix(spec, issues, log)
        if fixes:
            frames, events = prepass(spec)
            issues_after = qa_frames(spec, frames)
        else:
            issues_after = issues
    else:
        issues_after = []
    # --- audio
    clips = [(sc["voice_start"], sc["_voice"]) for sc in spec["scenes"]]
    mixwav = os.path.join(work, "mix.wav")
    audio.write_wav(mixwav, audio.mix(spec["duration"], clips, events))
    # --- vidéo
    silent = os.path.join(work, "video.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr0",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                           "-crf", "20", "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    prev_last = None
    last = None
    cur_si = -1
    for i, fr in enumerate(frames):
        if fr["si"] != cur_si:
            prev_last = last; cur_si = fr["si"]
        ctx = cairo.Context(surf)
        draw_frame(ctx, spec, fr)
        sc = spec["scenes"][fr["si"]]
        # mémorise la dernière image (sans sous-titres) de la scène courante pour la transition
        nxt = frames[i + 1]["si"] if i + 1 < len(frames) else None
        if nxt != fr["si"]:
            surf.flush()
            last = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
            c2 = cairo.Context(last); c2.set_source_surface(surf, 0, 0); c2.paint()
        if fr["si"] > 0 and sc["_bg_changed"] and fr["lt"] < 0.4:
            hero = fr["states"].get("hero")
            c = (W / 2, H * 0.55)
            _iris(ctx, prev_last, fr["lt"] / 0.4, c)
        elif fr["si"] > 0 and fr["lt"] < 0.1 and prev_last is not None:
            # coupe avec léger flash
            ctx.set_source_rgba(1, 1, 1, 0.15 * (1 - fr["lt"] / 0.1)); ctx.paint()
        draw_overlays(ctx, spec, fr)
        # fondu final
        rem = spec["duration"] - fr["t"]
        if rem < 0.4:
            ctx.set_source_rgba(0, 0, 0, 1 - rem / 0.4); ctx.paint()
        surf.flush()
        ff.stdin.write(bytes(surf.get_data()))
        if preview_every and i % preview_every == 0:
            surf.write_to_png(os.path.join(work, f"preview_{i:04d}.png"))
        if progress and i % 15 == 0:
            progress(i / len(frames))
    ff.stdin.close(); ff.wait()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", mixwav, "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out_mp4], check=True)
    report = dict(output=out_mp4, duration=round(spec["duration"], 2), frames=len(frames), fps=FPS,
                  resolution=f"{W}x{H}", tts=spec["_tts"], sfx_events=len(events),
                  qa_issues_initial=issues, auto_fixes=fixes, qa_issues_after=issues_after,
                  render_seconds=round(time.time() - t0, 1))
    report["post_checks"] = post_checks(out_mp4, spec["duration"])
    return report


def post_checks(mp4, expected):
    """Vérifie le fichier final : flux présents, durée, absence d'images noires prolongées, silence."""
    pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height:format=duration",
                         "-of", "json", mp4], capture_output=True, text=True)
    info = json.loads(pr.stdout)
    dur = float(info["format"]["duration"])
    bd = subprocess.run(["ffmpeg", "-i", mp4, "-vf", "blackdetect=d=0.5:pix_th=0.05", "-an", "-f", "null", "-"],
                        capture_output=True, text=True).stderr
    blacks = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", bd)
    sd = subprocess.run(["ffmpeg", "-i", mp4, "-af", "silencedetect=n=-45dB:d=1.5", "-vn", "-f", "null", "-"],
                        capture_output=True, text=True).stderr
    silences = re.findall(r"silence_start: ([\d.]+)", sd)
    return dict(streams=[s["codec_type"] + ":" + s["codec_name"] for s in info["streams"]],
                duration=round(dur, 2), duration_ok=abs(dur - expected) < 0.5,
                black_segments=blacks, long_silences=silences)
