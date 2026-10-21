"""Décors procéduraux vectoriels avec parallaxe, accessoires et effets."""
import math
import random
import cairocffi as cairo

W, H = 1080, 1920
GROUND = 1450


def _grad(ctx, y0, y1, stops):
    g = cairo.LinearGradient(0, y0, 0, y1)
    for o, c in stops:
        g.add_color_stop_rgb(o, *c)
    return g


def layer(ctx, cam, depth):
    """Applique la transformation caméra pour un plan de profondeur donnée (1 = plan des personnages)."""
    cx, cy, zoom, rot = cam
    z = 1 + (zoom - 1) * depth
    lx = W / 2 + (cx - W / 2) * depth
    ly = H / 2 + (cy - H / 2) * depth
    ctx.translate(W / 2, H / 2)
    ctx.rotate(rot * depth)
    ctx.scale(z, z)
    ctx.translate(-lx, -ly)


def _rng(seed):
    return random.Random(seed)


# ---------------------------------------------------------------- city night
def bg_city_night(ctx, cam, t):
    ctx.set_source(_grad(ctx, 0, H, [(0, (0.04, 0.05, 0.16)), (0.55, (0.16, 0.10, 0.30)), (1, (0.38, 0.16, 0.30))]))
    ctx.paint()
    ctx.save(); layer(ctx, cam, 0.05)
    r = _rng(3)
    for i in range(90):
        x, y = r.uniform(-1500, 2600), r.uniform(0, 1000)
        tw = 0.5 + 0.5 * math.sin(t * r.uniform(1, 4) + i)
        ctx.set_source_rgba(1, 1, 1, 0.25 + 0.6 * tw)
        ctx.arc(x, y, r.uniform(1.5, 3.5), 0, 2 * math.pi); ctx.fill()
    g = cairo.RadialGradient(820, 330, 10, 820, 330, 260)
    g.add_color_stop_rgba(0, 1, 0.95, 0.85, 0.55); g.add_color_stop_rgba(1, 1, 0.9, 0.8, 0)
    ctx.set_source(g); ctx.arc(820, 330, 260, 0, 2 * math.pi); ctx.fill()
    ctx.set_source_rgb(1, 0.96, 0.88); ctx.arc(820, 330, 85, 0, 2 * math.pi); ctx.fill()
    ctx.restore()
    for depth, col, seed, hmin, hmax, win in ((0.3, (0.10, 0.08, 0.22), 11, 450, 900, 0.15),
                                               (0.6, (0.07, 0.06, 0.15), 12, 350, 750, 0.35),
                                               (0.85, (0.03, 0.03, 0.08), 13, 250, 600, 0.6)):
        ctx.save(); layer(ctx, cam, depth)
        r = _rng(seed)
        x = -2500
        while x < 4500:
            bw = r.uniform(140, 300); bh = r.uniform(hmin, hmax)
            ctx.set_source_rgb(*col); ctx.rectangle(x, GROUND - bh, bw, bh + 600); ctx.fill()
            if r.random() < 0.3:
                ctx.rectangle(x + bw * 0.45, GROUND - bh - 60, 8, 60); ctx.fill()
            for wy in range(int(GROUND - bh + 30), GROUND - 40, 46):
                for wx in range(int(x + 22), int(x + bw - 30), 38):
                    if r.random() < win * 0.5:
                        flick = 0.75 + 0.25 * math.sin(t * 3 + wx * 0.1 + wy)
                        ctx.set_source_rgba(1, 0.82, 0.45, 0.85 * flick * (depth + 0.2))
                        ctx.rectangle(wx, wy, 16, 22); ctx.fill()
            x += bw + r.uniform(4, 30)
        ctx.restore()
    ctx.save(); layer(ctx, cam, 1.0)
    ctx.set_source_rgb(0.06, 0.06, 0.10); ctx.rectangle(-3000, GROUND, 9000, 900); ctx.fill()
    ctx.set_source_rgb(0.12, 0.12, 0.18); ctx.rectangle(-3000, GROUND, 9000, 18); ctx.fill()
    # lampadaires avec halo
    for lx in range(-2400, 5000, 700):
        ctx.set_source_rgb(0.02, 0.02, 0.05); ctx.rectangle(lx, GROUND - 620, 14, 620); ctx.fill()
        ctx.rectangle(lx, GROUND - 620, 80, 12); ctx.fill()
        g = cairo.RadialGradient(lx + 75, GROUND - 600, 5, lx + 75, GROUND - 300, 420)
        g.add_color_stop_rgba(0, 1, 0.85, 0.5, 0.35); g.add_color_stop_rgba(1, 1, 0.8, 0.4, 0)
        ctx.set_source(g); ctx.move_to(lx + 60, GROUND - 600); ctx.line_to(lx - 160, GROUND)
        ctx.line_to(lx + 320, GROUND); ctx.close_path(); ctx.fill()
    ctx.restore()


# ---------------------------------------------------------------- room
def bg_room(ctx, cam, t):
    ctx.save(); layer(ctx, cam, 0.9)
    ctx.set_source(_grad(ctx, 0, GROUND, [(0, (0.12, 0.13, 0.20)), (1, (0.20, 0.20, 0.28))]))
    ctx.rectangle(-2000, -500, 5000, GROUND + 500); ctx.fill()
    # fenêtre nocturne
    ctx.set_source_rgb(0.05, 0.07, 0.18); ctx.rectangle(80, 380, 360, 480); ctx.fill()
    ctx.set_source_rgba(1, 1, 1, 0.8)
    for sx, sy in ((140, 450), (300, 520), (380, 420), (200, 700), (330, 760)):
        ctx.arc(sx, sy, 3, 0, 2 * math.pi); ctx.fill()
    ctx.set_source_rgb(0.30, 0.28, 0.36); ctx.set_line_width(18)
    ctx.rectangle(80, 380, 360, 480); ctx.stroke()
    ctx.move_to(260, 380); ctx.line_to(260, 860); ctx.stroke()
    # étagère + cadres
    ctx.set_source_rgb(0.30, 0.22, 0.18); ctx.rectangle(620, 520, 380, 16); ctx.fill()
    for i, c in enumerate(((0.8, 0.3, 0.3), (0.3, 0.5, 0.8), (0.9, 0.7, 0.3))):
        ctx.set_source_rgb(*c); ctx.rectangle(650 + i * 60, 420, 40, 100); ctx.fill()
    ctx.restore()
    ctx.save(); layer(ctx, cam, 1.0)
    ctx.set_source(_grad(ctx, GROUND, H, [(0, (0.28, 0.20, 0.17)), (1, (0.16, 0.11, 0.10))]))
    ctx.rectangle(-3000, GROUND, 9000, 900); ctx.fill()
    ctx.set_source_rgb(0.1, 0.08, 0.1); ctx.rectangle(-3000, GROUND - 14, 9000, 14); ctx.fill()
    ctx.restore()


def fg_room(ctx, cam, t):
    """Bureau + ordinateur au premier plan (devant le personnage)."""
    ctx.save(); layer(ctx, cam, 1.0)
    dx = 700
    glow = 0.75 + 0.25 * math.sin(t * 7) * math.sin(t * 3.1)
    g = cairo.RadialGradient(dx + 70, GROUND - 330, 10, dx + 70, GROUND - 330, 420)
    g.add_color_stop_rgba(0, 0.4, 0.8, 1, 0.35 * glow); g.add_color_stop_rgba(1, 0.4, 0.8, 1, 0)
    ctx.set_source(g); ctx.arc(dx + 70, GROUND - 330, 420, 0, 2 * math.pi); ctx.fill()
    ctx.set_source_rgb(0.22, 0.15, 0.12); ctx.rectangle(dx - 160, GROUND - 270, 420, 26); ctx.fill()
    ctx.rectangle(dx + 210, GROUND - 250, 22, 250); ctx.fill()
    ctx.rectangle(dx - 140, GROUND - 250, 22, 250); ctx.fill()
    # écran (vers le personnage)
    ctx.set_source_rgb(0.08, 0.08, 0.1)
    ctx.rectangle(dx - 20, GROUND - 470, 200, 140); ctx.fill()
    ctx.set_source_rgb(0.25 * glow, 0.7 * glow, 1.0 * glow)
    ctx.rectangle(dx - 10, GROUND - 460, 180, 120); ctx.fill()
    ctx.set_source_rgba(1, 1, 1, 0.8)
    n = int(t * 14)
    for i in range(6):
        w = 40 + ((n + i * 7) * 37) % 120
        ctx.rectangle(dx, GROUND - 450 + i * 18, w, 7); ctx.fill()
    ctx.set_source_rgb(0.08, 0.08, 0.1); ctx.rectangle(dx + 70, GROUND - 330, 16, 60); ctx.fill()
    ctx.rectangle(dx - 120, GROUND - 285, 170, 14); ctx.fill()
    ctx.restore()


# ---------------------------------------------------------------- forest
def bg_forest(ctx, cam, t):
    ctx.set_source(_grad(ctx, 0, H, [(0, (0.05, 0.10, 0.16)), (0.6, (0.12, 0.25, 0.28)), (1, (0.25, 0.35, 0.30))]))
    ctx.paint()
    ctx.save(); layer(ctx, cam, 0.05)
    g = cairo.RadialGradient(300, 500, 10, 300, 500, 300)
    g.add_color_stop_rgba(0, 0.9, 1, 0.9, 0.4); g.add_color_stop_rgba(1, 0.9, 1, 0.9, 0)
    ctx.set_source(g); ctx.paint()
    ctx.restore()
    for depth, col, seed, sz in ((0.25, (0.09, 0.19, 0.20), 21, 0.8), (0.55, (0.06, 0.14, 0.14), 22, 1.0),
                                 (0.85, (0.03, 0.08, 0.08), 23, 1.3)):
        ctx.save(); layer(ctx, cam, depth)
        r = _rng(seed)
        x = -3000
        ctx.set_source_rgb(*col)
        while x < 6000:
            h = r.uniform(500, 900) * sz; w = h * 0.38
            sway = math.sin(t * 1.2 + x * 0.01) * 6 * depth
            for k in range(4):
                yy = GROUND - h + k * h * 0.2
                ww = w * (0.45 + k * 0.2)
                ctx.move_to(x + sway, yy); ctx.line_to(x - ww, yy + h * 0.32); ctx.line_to(x + ww, yy + h * 0.32)
                ctx.close_path(); ctx.fill()
            ctx.rectangle(x - 12 * sz, GROUND - h * 0.2, 24 * sz, h * 0.2 + 10); ctx.fill()
            x += r.uniform(120, 260) * sz
        ctx.restore()
    ctx.save(); layer(ctx, cam, 1.0)
    ctx.set_source_rgb(0.04, 0.07, 0.06); ctx.rectangle(-3000, GROUND, 9000, 900); ctx.fill()
    # lucioles
    r = _rng(5)
    for i in range(40):
        bx, by = r.uniform(-1500, 5000), r.uniform(GROUND - 900, GROUND - 50)
        fx = bx + math.sin(t * 0.8 + i) * 40; fy = by + math.cos(t * 1.1 + i * 2) * 30
        a = 0.5 + 0.5 * math.sin(t * 3 + i)
        ctx.set_source_rgba(0.9, 1, 0.5, 0.7 * a); ctx.arc(fx, fy, 4, 0, 2 * math.pi); ctx.fill()
    ctx.restore()


# ---------------------------------------------------------------- sunset road
def bg_sunset(ctx, cam, t):
    ctx.set_source(_grad(ctx, 0, GROUND, [(0, (0.18, 0.10, 0.30)), (0.5, (0.85, 0.40, 0.35)), (1, (1.0, 0.75, 0.45))]))
    ctx.paint()
    ctx.save(); layer(ctx, cam, 0.05)
    g = cairo.RadialGradient(540, GROUND - 120, 20, 540, GROUND - 120, 700)
    g.add_color_stop_rgba(0, 1, 0.95, 0.7, 0.9); g.add_color_stop_rgba(1, 1, 0.7, 0.4, 0)
    ctx.set_source(g); ctx.paint()
    ctx.set_source_rgb(1, 0.92, 0.7); ctx.arc(540, GROUND - 120, 150, 0, 2 * math.pi); ctx.fill()
    ctx.restore()
    for depth, col, seed, amp in ((0.3, (0.45, 0.20, 0.32), 31, 180), (0.6, (0.28, 0.12, 0.25), 32, 120)):
        ctx.save(); layer(ctx, cam, depth)
        r = _rng(seed)
        ctx.set_source_rgb(*col); ctx.move_to(-3000, GROUND + 50)
        x = -3000
        while x < 6000:
            ctx.line_to(x, GROUND - r.uniform(0.3, 1) * amp); x += r.uniform(150, 300)
        ctx.line_to(6000, GROUND + 50); ctx.close_path(); ctx.fill()
        ctx.restore()
    ctx.save(); layer(ctx, cam, 1.0)
    ctx.set_source_rgb(0.15, 0.07, 0.15); ctx.rectangle(-3000, GROUND, 9000, 900); ctx.fill()
    # route en perspective
    ctx.set_source_rgb(0.22, 0.12, 0.20)
    ctx.move_to(500, GROUND); ctx.line_to(580, GROUND); ctx.line_to(1100, H); ctx.line_to(-20, H); ctx.close_path(); ctx.fill()
    ctx.set_source_rgb(1, 0.85, 0.5)
    for i in range(8):
        k = ((i + t * 1.5) % 8) / 8
        y0 = GROUND + (H - GROUND) * k * k; y1 = y0 + 8 + 50 * k
        ctx.rectangle(540 - 3 - 8 * k, y0, 6 + 16 * k, y1 - y0); ctx.fill()
    ctx.restore()


BACKGROUNDS = {"city_night": bg_city_night, "room": bg_room, "forest": bg_forest, "sunset": bg_sunset}
FOREGROUNDS = {"room": fg_room}


# ---------------------------------------------------------------- accessoires
def draw_phone(ctx, x, y, rot=0.0, s=1.0, glow=True):
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.scale(s, s)
    ctx.set_source_rgb(0.1, 0.1, 0.12); _rrect(ctx, -22, -38, 44, 76, 8); ctx.fill()
    if glow:
        ctx.set_source_rgb(0.4, 0.8, 1.0); _rrect(ctx, -17, -31, 34, 60, 4); ctx.fill()
    ctx.restore()


def draw_shards(ctx, x, y, k):
    r = _rng(9)
    for i in range(10):
        a = r.uniform(-math.pi, 0); v = r.uniform(80, 260)
        px = x + math.cos(a) * v * k; py = y + math.sin(a) * v * k + 400 * k * k
        ctx.set_source_rgba(0.5, 0.85, 1, max(0, 1 - k))
        ctx.save(); ctx.translate(px, py); ctx.rotate(i + k * 8)
        ctx.rectangle(-6, -6, 12, 12); ctx.fill(); ctx.restore()


def _rrect(ctx, x, y, w, h, r):
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()


def draw_emote(ctx, kind, x, y, k, t):
    """Icône au-dessus de la tête (k = progression d'apparition 0..1+)."""
    from .easing import ease_out_back
    s = ease_out_back(min(k, 1))
    if s <= 0:
        return
    ctx.save(); ctx.translate(x, y + math.sin(t * 4) * 6); ctx.scale(s, s)
    if kind == "idea":
        for i in range(8):
            a = i * math.pi / 4 + t * 0.5
            ctx.set_source_rgba(1, 0.9, 0.3, 0.9); ctx.set_line_width(7); ctx.set_line_cap(1)
            ctx.move_to(math.cos(a) * 62, math.sin(a) * 62); ctx.line_to(math.cos(a) * 86, math.sin(a) * 86); ctx.stroke()
        ctx.set_source_rgb(1, 0.88, 0.25); ctx.arc(0, -6, 40, 0, 2 * math.pi); ctx.fill()
        ctx.set_source_rgb(0.5, 0.5, 0.55); ctx.rectangle(-18, 30, 36, 24); ctx.fill()
    elif kind in ("!", "?"):
        ctx.set_source_rgb(1, 1, 1); ctx.arc(0, 0, 58, 0, 2 * math.pi); ctx.fill()
        ctx.set_source_rgb(0.9, 0.15, 0.2) if kind == "!" else ctx.set_source_rgb(0.2, 0.4, 0.9)
        ctx.select_font_face("DejaVu Sans", 0, 1); ctx.set_font_size(90)
        e = ctx.text_extents(kind)
        ctx.move_to(-e[2] / 2 - e[0], e[3] / 2 - 4); ctx.show_text(kind)
    elif kind == "sweat":
        for i, (dx, dy) in enumerate(((-70, 30), (60, 0))):
            yy = dy + ((t * 60 + i * 30) % 60)
            ctx.set_source_rgb(0.5, 0.8, 1)
            ctx.move_to(dx, yy - 30); ctx.curve_to(dx + 18, yy, dx + 14, yy + 18, dx, yy + 18)
            ctx.curve_to(dx - 14, yy + 18, dx - 18, yy, dx, yy - 30); ctx.fill()
    elif kind == "money":
        ctx.set_source_rgb(0.3, 0.75, 0.35); _rrect(ctx, -60, -32, 120, 64, 8); ctx.fill()
        ctx.set_source_rgb(0.9, 1, 0.9); ctx.select_font_face("DejaVu Sans", 0, 1); ctx.set_font_size(52)
        ctx.move_to(-16, 18); ctx.show_text("$")
    ctx.restore()


def vignette(ctx, strength=0.55):
    g = cairo.RadialGradient(W / 2, H / 2, H * 0.25, W / 2, H / 2, H * 0.75)
    g.add_color_stop_rgba(0, 0, 0, 0, 0); g.add_color_stop_rgba(1, 0, 0, 0, strength)
    ctx.set_source(g); ctx.paint()
