"""Bibliothèque d'actions : convertit (action, temps) -> pose + position.

Chaque action est une vraie animation procédurale (cycles de marche,
anticipation, rebonds amortis, clignements...), pas un zoom sur image fixe.
"""
import math
from .easing import clamp, lerp, ease_in_out, ease_out, ease_out_back, spring

STRIDE = {"walk": 120.0, "run": 190.0, "sneak": 80.0}
SPEED = {"walk": 330.0, "run": 900.0, "sneak": 170.0}  # px/s monde


def blink_amount(t, seed=0.0):
    """Clignement naturel toutes les ~2.7 s."""
    period = 2.7 + (seed % 1.0) * 0.8
    ph = (t + seed * 1.3) % period
    if ph < 0.12:
        return math.sin(ph / 0.12 * math.pi)
    return 0.0


def idle(t, dur, a):
    br = math.sin(t * 2.4)
    return dict(lift=br * 2.5, sh_b=-10 + br * 2, sh_f=10 - br * 2, el_b=16, el_f=16,
                head=math.sin(t * 0.9) * 4, torso=br * 0.8,
                expr=a.get("expr", "neutral"))


def think(t, dur, a):
    k = ease_out(t / 0.45)
    tap = math.sin(t * 9) * 3 * k
    return dict(lift=math.sin(t * 2.2) * 2, torso=lerp(0, -3, k),
                sh_f=lerp(10, 48, k) + tap * 0.3, el_f=lerp(16, 152, k),
                sh_b=lerp(-10, 22, k), el_b=lerp(16, 95, k),
                head=lerp(0, -10, k) + math.sin(t * 1.7) * 2,
                look_x=0.4, look_y=-0.9 * k, expr=a.get("expr", "think"))


def type_(t, dur, a):
    k = ease_out(t / 0.3)
    f1 = math.sin(t * 26) * 6
    f2 = math.sin(t * 26 + 2.1) * 6
    return dict(lift=-6 * k, torso=lerp(0, 14, k), head=lerp(0, 6, k) + math.sin(t * 13) * 1.2,
                sh_f=lerp(10, 50, k) + f1, el_f=lerp(16, 42, k) - f1 * 0.6,
                sh_b=lerp(-10, 44, k) + f2, el_b=lerp(16, 46, k) - f2 * 0.6,
                hip_f=8, hip_b=-4, look_y=0.8 * k, look_x=0.6,
                expr=a.get("expr", "smirk"))


def locomotion(kind, phase, a):
    s = math.sin(phase)
    c = math.cos(phase)
    if kind == "run":
        return dict(torso=16, head=-6, lift=-6 + abs(s) * 26,
                    hip_f=34 * s + 8, kn_f=20 + 70 * max(0, -c) + 18,
                    hip_b=-34 * s + 8, kn_b=20 + 70 * max(0, c) + 18,
                    sh_f=-55 * s + 5, el_f=95, sh_b=55 * s + 5, el_b=95,
                    expr=a.get("expr", "worried"), mouth_open=0.3 + 0.2 * abs(s))
    if kind == "sneak":
        return dict(torso=24, head=-14, lift=-38 + abs(s) * 6,
                    hip_f=22 * s + 22, kn_f=50 + 25 * max(0, -c),
                    hip_b=-22 * s + 22, kn_b=50 + 25 * max(0, c),
                    sh_f=40 + 8 * s, el_f=60, sh_b=30 - 8 * s, el_b=70,
                    look_x=1.0, expr=a.get("expr", "smirk"))
    return dict(torso=4, head=math.sin(phase * 2) * 1.5, lift=abs(s) * 9 - 3,
                hip_f=26 * s, kn_f=6 + 34 * max(0, -c),
                hip_b=-26 * s, kn_b=6 + 34 * max(0, c),
                sh_f=-24 * s, el_f=22 + 8 * max(0, s), sh_b=24 * s, el_b=22 + 8 * max(0, -s),
                expr=a.get("expr", "neutral"))


def shocked(t, dur, a):
    t0 = a.get("at", 0.15)
    u = t - t0
    if u < 0:  # anticipation : petit accroupissement
        k = ease_in_out((t / t0) if t0 > 0 else 1)
        return dict(lift=-14 * k, torso=6 * k, expr="neutral")
    j = spring(u * 0.9, freq=1.6, decay=4.0)
    hop = max(0.0, math.sin(min(u / 0.38, 1) * math.pi)) * 60
    tremble = math.sin(u * 60) * 2.2 * math.exp(-u * 1.2)
    return dict(lift=hop + tremble, torso=-12 * j + tremble, head=-8 * j,
                sh_f=lerp(10, 150, j), el_f=lerp(16, 30, j),
                sh_b=lerp(-10, 140, j), el_b=lerp(16, 30, j),
                hip_f=14, kn_f=8, hip_b=-14, kn_b=8,
                expr="shocked", mouth_open=0.8)


def throw(t, dur, a):
    rel = a.get("release", 0.55)
    if t < rel * 0.8:
        k = ease_in_out(t / (rel * 0.8))
        return dict(torso=lerp(0, -12, k), sh_f=lerp(10, -125, k), el_f=lerp(16, 40, k),
                    sh_b=lerp(-10, 40, k), el_b=40, hip_f=18, hip_b=-14, lift=-8 * k,
                    expr="angry")
    k = ease_out((t - rel * 0.8) / 0.25)
    settle = ease_in_out((t - rel - 0.4) / 0.5)
    return dict(torso=lerp(-12, 22, k) - 10 * settle, sh_f=lerp(-125, 120, k) - 105 * settle,
                el_f=lerp(40, 5, k) + 15 * settle, sh_b=lerp(40, -35, k), el_b=30,
                hip_f=lerp(18, 26, k), kn_f=12, hip_b=-20, kn_b=20, lift=-8 * (1 - k),
                expr="angry" if settle < 0.5 else "smirk")


def wave(t, dur, a):
    k = ease_out(t / 0.3)
    w = math.sin(t * 12) * 18 * k
    return dict(sh_f=lerp(10, 155, k), el_f=lerp(16, 20, k) + w, lift=math.sin(t * 3) * 2,
                head=6 * k, expr=a.get("expr", "happy"))


def point(t, dur, a):
    k = ease_out_back(t / 0.35)
    return dict(sh_f=lerp(10, 92, k), el_f=lerp(16, 0, k), torso=4 * k, head=-3 * k,
                lift=math.sin(t * 2.4) * 2, expr=a.get("expr", "smirk"), look_x=1)


def celebrate(t, dur, a):
    hop = abs(math.sin(t * 6)) * 45
    return dict(lift=hop, sh_f=160 + math.sin(t * 12) * 10, el_f=10,
                sh_b=160 - math.sin(t * 12) * 10, el_b=10, hip_f=12, hip_b=-12,
                kn_f=10 + hop * 0.3, kn_b=10 + hop * 0.3, expr="happy")


def look_phone(t, dur, a):
    k = ease_out(t / 0.4)
    return dict(sh_f=lerp(10, 42, k), el_f=lerp(16, 105, k), head=lerp(0, 16, k),
                look_y=1.0 * k, look_x=0.8, lift=math.sin(t * 2.2) * 2,
                torso=3 * k, expr=a.get("expr", "worried"))


def vanish(t, dur, a):
    p = idle(t, dur, a)
    p.update(expr="smirk", lift=p["lift"] + min(t, 1.2) * 18)
    return p


ACTIONS = {"vanish": vanish, "idle": idle, "think": think, "type": type_, "shocked": shocked,
           "throw": throw, "wave": wave, "point": point, "celebrate": celebrate,
           "look_phone": look_phone}
MOVES = ("walk", "run", "sneak")


def actor_state(actor, t_scene, scene_dur):
    """Retourne l'état d'un acteur à l'instant t (en secondes depuis le début de scène)."""
    segs = actor.get("actions") or [dict(action=actor.get("action", "idle"), **{
        k: v for k, v in actor.items() if k in ("to", "expr", "at", "release", "speed")})]
    x = float(actor.get("x", 540))
    facing = actor.get("facing", 1)
    start = float(actor.get("enter", 0.0))
    if t_scene < start:
        return None
    t = t_scene - start
    total = max(0.01, scene_dur - start)
    # durées des segments
    fixed = sum(s.get("dur", 0) for s in segs if "dur" in s)
    free = [s for s in segs if "dur" not in s]
    fill = max(0.2, (total - fixed) / max(1, len(free))) if free else 0
    cursor = 0.0
    state = None
    for i, sg in enumerate(segs):
        d = sg.get("dur", fill)
        last = i == len(segs) - 1
        act = sg.get("action", "idle")
        local = t - cursor
        if act in MOVES:
            target = sg.get("to", x + 400 * facing)
            spd = sg.get("speed", SPEED[act])
            dist_total = abs(target - x)
            move_time = max(0.3, dist_total / spd)
            if "dur" not in sg and not last:
                d = move_time
            if local < d or last:
                lt = max(0.0, local)
                # accélération / décélération douces
                ramp = 0.25 if act != "run" else 0.15
                u = clamp(lt / move_time)
                prog = ease_in_out(u) if dist_total < 250 else _ramp(u, ramp / move_time)
                dist = dist_total * prog
                fdir = 1 if target >= x else -1
                cx = x + dist * fdir
                phase = dist / STRIDE[act] * math.pi
                moving = u < 1.0
                if moving:
                    pose = locomotion(act, phase, sg)
                    amp = clamp(lt / 0.2) * clamp((move_time - lt) / 0.2 + 0.0001)
                    if amp < 1:
                        base = idle(t, d, sg)
                        pose = {k: (lerp(base.get(k, 0), v, amp) if isinstance(v, (int, float)) else v)
                                for k, v in pose.items()}
                else:
                    pose = idle(t, d, sg)
                    phase = None
                state = dict(pose=pose, x=cx, facing=fdir, phase=phase if moving else None,
                             kind=act, local=lt, seg=i)
                break
            facing = 1 if target >= x else -1
            x = target
        else:
            if local < d or last:
                lt = max(0.0, local)
                pose = ACTIONS.get(act, idle)(lt, d, sg)
                state = dict(pose=pose, x=x, facing=sg.get("facing", facing), phase=None,
                             kind=act, local=lt, seg=i, seg_def=sg)
                break
        cursor += d
    if state is None:
        state = dict(pose=idle(t, 1, {}), x=x, facing=facing, phase=None, kind="idle", local=0, seg=0)
    state["pose"].setdefault("blink", blink_amount(t_scene, hash(actor.get("id", "a")) % 7 / 7))
    if state["pose"].get("expr") == "shocked":
        state["pose"]["blink"] = 0
    return state


def _ramp(u, r):
    """Profil vitesse trapézoïdal normalisé (r = fraction d'accélération)."""
    r = clamp(r, 0.01, 0.45)
    vmax = 1 / (1 - r)
    if u < r:
        return 0.5 * vmax * u * u / r
    if u > 1 - r:
        v = 1 - u
        return 1 - 0.5 * vmax * v * v / r
    return 0.5 * vmax * r + vmax * (u - r)
