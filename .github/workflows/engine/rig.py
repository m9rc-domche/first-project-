"""Personnage stickman vectoriel riggé (squelette 2D à angles articulaires).

Angles en degrés, 0 = membre pointant vers le bas, positif = vers l'avant
(sens du regard). Le torse: 0 = vertical, positif = penché vers l'avant.
"""
import math

# Longueurs du squelette (unités monde, avant échelle)
TORSO = 175
HEAD_R = 66
NECK = 18
UPPER_ARM = 92
FOREARM = 88
THIGH = 112
SHIN = 108
LINE_W = 21

BASE_POSE = dict(
    torso=0.0, head=0.0,
    sh_b=-12.0, el_b=18.0,      # bras arrière
    sh_f=12.0, el_f=18.0,       # bras avant
    hip_b=-6.0, kn_b=4.0,       # jambe arrière
    hip_f=6.0, kn_f=4.0,        # jambe avant
    lift=0.0,                   # hanche vers le haut (+) / accroupi (-)
    expr="neutral", look_x=0.0, look_y=0.0, blink=0.0, mouth_open=0.0,
)


def _dir(angle_deg, facing):
    a = math.radians(angle_deg)
    return (math.sin(a) * facing, math.cos(a))


def solve(pose, x, ground_y, scale=1.0, facing=1):
    """Calcule les positions des articulations en coordonnées monde."""
    p = dict(BASE_POSE)
    p.update(pose)
    s = scale
    # hauteur de hanche: jambes tendues
    leg_len = (THIGH + SHIN) * s
    hip = (x, ground_y - leg_len * 0.985 - p["lift"] * s)
    j = {"hip": hip}
    # torse
    t = math.radians(p["torso"])
    neck = (hip[0] + math.sin(t) * TORSO * s * facing, hip[1] - math.cos(t) * TORSO * s)
    j["neck"] = neck
    ht = math.radians(p["torso"] + p["head"])
    head = (neck[0] + math.sin(ht) * (NECK + HEAD_R) * s * facing,
            neck[1] - math.cos(ht) * (NECK + HEAD_R) * s)
    j["head"] = head
    sh = (neck[0] - math.sin(t) * 8 * s * facing, neck[1] + 10 * s)
    j["shoulder"] = sh
    for side in ("b", "f"):
        ua = p["sh_" + side] + p["torso"]
        d = _dir(ua, facing)
        el = (sh[0] + d[0] * UPPER_ARM * s, sh[1] + d[1] * UPPER_ARM * s)
        d2 = _dir(ua + p["el_" + side], facing)
        ha = (el[0] + d2[0] * FOREARM * s, el[1] + d2[1] * FOREARM * s)
        j["elbow_" + side] = el
        j["hand_" + side] = ha
        th = p["hip_" + side]
        d = _dir(th, facing)
        kn = (hip[0] + d[0] * THIGH * s, hip[1] + d[1] * THIGH * s)
        d2 = _dir(th - p["kn_" + side], facing)
        ft = (kn[0] + d2[0] * SHIN * s, kn[1] + d2[1] * SHIN * s)
        j["knee_" + side] = kn
        j["foot_" + side] = ft
    j["_pose"] = p
    j["_scale"] = s
    j["_facing"] = facing
    return j


def bbox(j):
    xs, ys = [], []
    s = j["_scale"]
    for k, v in j.items():
        if k.startswith("_"):
            continue
        r = HEAD_R * s if k == "head" else LINE_W * s
        xs += [v[0] - r, v[0] + r]
        ys += [v[1] - r, v[1] + r]
    return min(xs), min(ys), max(xs), max(ys)


def _limb(ctx, pts):
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)


def draw(ctx, j, color=(0.05, 0.05, 0.07), outline=(1, 1, 1), hat=None, outline_w=7):
    s = j["_scale"]
    p = j["_pose"]
    f = j["_facing"]
    lw = LINE_W * s
    limbs_back = [
        [j["shoulder"], j["elbow_b"], j["hand_b"]],
        [j["hip"], j["knee_b"], j["foot_b"]],
    ]
    limbs_front = [
        [j["hip"], j["knee_f"], j["foot_f"]],
        [j["hip"], j["neck"]],
        [j["shoulder"], j["elbow_f"], j["hand_f"]],
    ]
    ctx.set_line_cap(1)  # ROUND
    ctx.set_line_join(1)

    def stroke_pass(limbs, width, rgb):
        ctx.set_source_rgb(*rgb)
        ctx.set_line_width(width)
        for l in limbs:
            _limb(ctx, l)
            ctx.stroke()

    # contour clair (lisibilité sur fonds sombres) puis trait noir
    if outline is not None:
        stroke_pass(limbs_back + limbs_front, lw + outline_w * s * 2, outline)
        ctx.arc(j["head"][0], j["head"][1], HEAD_R * s + outline_w * s, 0, 2 * math.pi)
        ctx.set_source_rgb(*outline)
        ctx.fill()
    # membres arrière légèrement plus clairs => profondeur
    back = tuple(min(1, c + 0.18) for c in color)
    stroke_pass(limbs_back, lw, back)
    stroke_pass(limbs_front, lw, color)
    # tête
    hx, hy = j["head"]
    ctx.arc(hx, hy, HEAD_R * s, 0, 2 * math.pi)
    ctx.set_source_rgb(*color)
    ctx.fill()
    if hat == "cap":
        _draw_cap(ctx, hx, hy, s, f)
    _draw_face(ctx, hx, hy, s, f, p)


def _draw_cap(ctx, hx, hy, s, f):
    ctx.save()
    ctx.set_source_rgb(0.12, 0.22, 0.55)
    ctx.arc(hx, hy - 8 * s, HEAD_R * s * 1.02, math.pi, 2 * math.pi)
    ctx.fill()
    ctx.rectangle(hx - HEAD_R * s * (0.2 if f > 0 else 1.5), hy - 14 * s, HEAD_R * s * 1.7, 12 * s)
    ctx.fill()
    ctx.set_source_rgb(1, 0.85, 0.2)
    ctx.arc(hx + 6 * s * f, hy - 40 * s, 9 * s, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()


def _draw_face(ctx, hx, hy, s, f, p):
    expr = p.get("expr", "neutral")
    lx, ly = p.get("look_x", 0), p.get("look_y", 0)
    blink = max(0.0, min(1.0, p.get("blink", 0)))
    cx = hx + 16 * s * f + lx * 6 * s * f
    cy = hy - 6 * s + ly * 5 * s
    ex = 19 * s
    ew, eh = 11 * s, 15 * s
    if expr == "shocked":
        ew, eh = 14 * s, 19 * s
    if expr in ("happy", "smirk"):
        eh *= 0.85
    eh *= (1 - 0.9 * blink)
    white = (1, 1, 1)
    ctx.set_source_rgb(*white)
    for side in (-1, 1):
        ctx.save()
        ctx.translate(cx + side * ex, cy)
        ctx.scale(ew, max(eh, 1.5 * s))
        ctx.arc(0, 0, 1, 0, 2 * math.pi)
        ctx.restore()
        ctx.fill()
    # pupilles
    if blink < 0.6 and expr != "happy":
        ctx.set_source_rgb(0.05, 0.05, 0.07)
        pr = 5.5 * s if expr != "shocked" else 4.5 * s
        for side in (-1, 1):
            ctx.arc(cx + side * ex + (2 + lx * 3) * s * f, cy + (1 + ly * 3) * s, pr, 0, 2 * math.pi)
            ctx.fill()
    if expr == "happy" and blink < 0.6:  # yeux "^ ^"
        ctx.set_source_rgb(0.05, 0.05, 0.07)
        for side in (-1, 1):
            ctx.rectangle(cx + side * ex - ew, cy + 2 * s, ew * 2, eh)
            ctx.fill()
    # sourcils
    ctx.set_source_rgb(*white)
    ctx.set_line_width(5 * s)
    ctx.set_line_cap(1)
    brow = {"neutral": (0, 0), "happy": (-2, 0), "shocked": (-10, 0), "angry": (4, 18),
            "worried": (-4, -16), "smirk": (2, 10), "think": (-6, -10)}.get(expr, (0, 0))
    by = cy - eh - 9 * s + brow[0] * s
    for side in (-1, 1):
        tilt = brow[1] * s * 0.5
        if expr == "smirk" and side < 0:
            tilt = 0
        inner_x = cx + side * ex - side * 10 * s
        outer_x = cx + side * ex + side * 10 * s
        ctx.move_to(inner_x, by + tilt)   # tilt>0 : sourcil froncé (colère)
        ctx.line_to(outer_x, by - tilt)
        ctx.stroke()
    # bouche
    mx, my = cx, cy + 30 * s
    mo = p.get("mouth_open", 0)
    ctx.set_line_width(5 * s)
    if expr == "shocked" or mo > 0.15:
        r = (9 + 6 * max(mo, 0.6 if expr == "shocked" else 0)) * s
        ctx.save()
        ctx.translate(mx, my + 3 * s)
        ctx.scale(r * 0.8, r)
        ctx.arc(0, 0, 1, 0, 2 * math.pi)
        ctx.restore()
        ctx.fill()
    elif expr == "happy":
        ctx.arc(mx, my - 8 * s, 16 * s, 0.15 * math.pi, 0.85 * math.pi)
        ctx.stroke()
    elif expr == "smirk":
        ctx.move_to(mx - 14 * s, my + 2 * s)
        ctx.curve_to(mx - 2 * s, my + 6 * s, mx + 8 * s, my + 2 * s, mx + 16 * s, my - 8 * s)
        ctx.stroke()
    elif expr in ("worried", "angry"):
        ctx.arc_negative(mx, my + 14 * s, 13 * s, -0.2 * math.pi, -0.8 * math.pi)
        ctx.stroke()
    elif expr == "think":
        ctx.move_to(mx - 10 * s, my + 2 * s)
        ctx.line_to(mx + 12 * s, my - 2 * s)
        ctx.stroke()
    else:
        ctx.move_to(mx - 12 * s, my)
        ctx.curve_to(mx - 4 * s, my + 5 * s, mx + 4 * s, my + 5 * s, mx + 12 * s, my)
        ctx.stroke()
