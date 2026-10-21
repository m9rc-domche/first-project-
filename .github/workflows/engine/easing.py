import math

def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))

def lerp(a, b, t):
    return a + (b - a) * t

def ease_in_out(t):
    t = clamp(t)
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2

def ease_out(t):
    t = clamp(t)
    return 1 - pow(1 - t, 3)

def ease_in(t):
    t = clamp(t)
    return t * t * t

def ease_out_back(t, s=1.70158):
    t = clamp(t)
    t -= 1
    return t * t * ((s + 1) * t + s) + 1

def spring(t, freq=4.0, decay=5.0):
    """0 -> 1 avec rebond amorti."""
    if t <= 0:
        return 0.0
    return 1 - math.exp(-decay * t) * math.cos(freq * 2 * math.pi * t)

def lerp_pose(a, b, t):
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, (int, float)) and isinstance(a.get(k), (int, float)):
            out[k] = lerp(a[k], v, t)
        else:
            out[k] = v if t >= 0.5 else a.get(k, v)
    return out
