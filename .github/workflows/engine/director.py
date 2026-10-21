"""Réalisateur automatique : transforme un script texte en plan de scènes (JSON).

Mode 1 (gratuit, hors-ligne) : règles par mots-clés FR/EN -> décor, actions, caméra, émotes.
Mode 2 : coller un JSON de scènes produit par ChatGPT (même schéma, voir docs/SCENE_SCHEMA.md).
"""
import json
import re

BG_RULES = [
    ("forest", r"\b(forest|woods|trees|jungle|for[êe]t|bois|arbres)\b"),
    ("sunset", r"\b(morning|sunrise|road|exist|vanish|gone|forever|matin|aube|route|n'existe|existes|dispara[iî]s|toujours)\b"),
    ("room", r"\b(computer|laptop|online|digital|internet|home|room|bedroom|delete|wipe|ordinateur|num[ée]rique|chambre|maison|supprim|efface)\w*"),
    ("city_night", r"\b(street|city|outside|walk|cameras?|cash|police|night|3 ?am|rue|ville|dehors|marches?|nuit|cam[ée]ras?)\b"),
]

ACTION_RULES = [
    ("vanish", r"\b(don't exist|no longer exist|vanish|disappear(ed)? forever|n'existes? plus|dispara[iî]s pour toujours)\b"),
    ("shocked", r"\b(but|suddenly|watching|caught|found you|police|cop|mais|soudain|surveill|attrap|repér)\w*"),
    ("run", r"\b(run|runs|running|escape|flee|sprint|chase|cours|courir|fuis|fuir|[ée]chapp)\w*"),
    ("throw", r"\b(smash|smashed|throw|thrown|destroy|break|jette|jet[ée]|d[ée]trui|cass|[ée]cras)\w*"),
    ("type", r"\b(wipe|delete|hack|type|computer|laptop|online|efface|supprim|pirat|tape|ordinateur)\w*"),
    ("walk", r"\b(walk|leave|step out|go out|head|marche|sors|pars|quittes?)\w*"),
    ("think", r"\b(what if|imagine|plan|iq|smart|genius|think|idea|et si|qi|g[ée]nie|id[ée]e|r[ée]fl[ée]chi)\w*"),
]

CAMERA_FOR = {"think": "push_in", "type": "push_in", "shocked": "punch", "run": "track",
              "walk": "track", "throw": "static", "vanish": "pull_out", "idle": "push_in"}
EMOTE_FOR = {"think": "idea", "shocked": "!", "run": "sweat", "type": None, "vanish": None}


def split_scenes(script):
    script = script.strip()
    parts = [p.strip() for p in re.split(r"\n\s*\n|\n", script) if p.strip()]
    if len(parts) <= 1:
        parts = [p.strip() for p in re.split(r"(?<=[.!?…])\s+", script) if p.strip()]
    return parts


def detect_lang(text):
    fr = len(re.findall(r"\b(le|la|les|et|tu|un|une|des|est|pas|que|qui|dans|avec|pour|ton|ta|tes)\b", text.lower()))
    en = len(re.findall(r"\b(the|and|you|a|is|not|that|who|in|with|for|your|of)\b", text.lower()))
    return "fr" if fr > en else "en"


def direct(script, title=None):
    lines = split_scenes(script)
    scenes = []
    bg = "room"
    cop_seen = False
    for i, line in enumerate(lines):
        low = line.lower()
        for name, rx in BG_RULES:
            if re.search(rx, low):
                bg = name
                break
        action = "idle"
        for name, rx in ACTION_RULES:
            if re.search(rx, low):
                action = name
                break
        if i == 0 and action == "idle":
            action = "think"
        if action == "type":
            bg = "room"
        if action == "vanish" and bg not in ("sunset", "forest"):
            bg = "sunset"
        has_phone = bool(re.search(r"\b(phone|smartphone|t[ée]l[ée]phone|portable)\b", low))
        actors = _actors_for(action, bg, has_phone, cop_seen)
        if action == "shocked":
            cop_seen = True
        emote = EMOTE_FOR.get(action)
        if re.search(r"\b(money|cash|bank|argent|banque|billets?)\b", low) and action not in ("shocked",):
            emote = "money"
        if line.rstrip().endswith("?") and action not in ("think", "shocked"):
            emote = emote or "?"
        scenes.append(dict(text=line, bg=bg, camera=CAMERA_FOR.get(action, "static"),
                           emote=emote, actors=actors))
    return dict(title=title or _auto_title(lines), lang=detect_lang(script), scenes=scenes)


def _auto_title(lines):
    words = re.sub(r"[^\w\s'?]", "", lines[0]).split()[:6] if lines else ["AutoMotion"]
    return " ".join(words).upper()


def _actors_for(action, bg, has_phone, cop_seen):
    hero = dict(id="hero", x=540, facing=1)
    if action == "type":
        hero.update(x=470, action="type")
    elif action == "think":
        hero.update(x=540, actions=[dict(action="idle", dur=0.35), dict(action="think")])
        if bg == "room":
            hero["x"] = 420
    elif action == "walk":
        hero.update(x=200, actions=[dict(action="walk", to=1150)], holds="phone" if has_phone else None)
    elif action == "run":
        hero.update(x=380, actions=[dict(action="run", to=3200)])
        if cop_seen:
            return [hero, dict(id="cop", hat="cap", x=-250, actions=[dict(action="run", to=2700, speed=870)])]
    elif action == "throw":
        hero.update(x=380, holds="phone", actions=[dict(action="look_phone", dur=0.6), dict(action="throw", release=0.55)])
    elif action == "shocked":
        hero.update(x=700, facing=-1, actions=[dict(action="idle", dur=0.45, facing=-1), dict(action="shocked", at=0.12, facing=-1)])
        cop = dict(id="cop", hat="cap", x=-260, enter=0.0,
                   actions=[dict(action="walk", to=230, speed=520), dict(action="point", expr="angry")])
        return [hero, cop]
    elif action == "vanish":
        hero.update(x=540, actions=[dict(action="wave", dur=1.0, expr="smirk"), dict(action="vanish")])
    else:
        hero.update(action="idle", holds="phone" if has_phone else None)
        if has_phone:
            hero["action"] = "look_phone"
    return [hero]


def apply_instructions(spec, instructions):
    """Corrections par instructions textuelles simples, une par ligne :
    'scene 3: camera=track' | 'scene 2: bg=forest' | 'scene 4: action=run'
    'scene 1: expr=happy' | 'scene 5: emote=?' | 'scene 2: text=Nouveau texte'
    'all: camera=static' | 'title=MON TITRE'
    """
    log = []
    for raw in instructions.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"(?i)title\s*=\s*(.+)", line)
        if m:
            spec["title"] = m.group(1).strip(); log.append(f"titre -> {spec['title']}"); continue
        m = re.match(r"(?i)(?:sc[eè]ne\s*(\d+)|all|toutes?)\s*:\s*(\w+)\s*=\s*(.+)", line)
        if not m:
            log.append(f"ignoré (format non reconnu): {line}"); continue
        idx = [int(m.group(1)) - 1] if m.group(1) else list(range(len(spec["scenes"])))
        key, val = m.group(2).lower(), m.group(3).strip()
        for i in idx:
            if not 0 <= i < len(spec["scenes"]):
                log.append(f"scène {i+1} inexistante"); continue
            sc = spec["scenes"][i]
            if key in ("camera", "bg", "emote", "text"):
                sc[key] = None if val.lower() == "none" else val
            elif key == "action":
                sc["actors"] = _actors_for(val, sc["bg"], False, any(a["id"] == "cop" for s in spec["scenes"][:i] for a in s["actors"]))
                sc["camera"] = CAMERA_FOR.get(val, sc.get("camera", "static"))
            elif key == "expr":
                for a in sc["actors"]:
                    if a["id"] == "hero":
                        a["expr"] = val
                        for sg in a.get("actions", []):
                            sg["expr"] = val
            else:
                log.append(f"clé inconnue: {key}"); continue
            log.append(f"scène {i+1}: {key} -> {val}")
    return spec, log


if __name__ == "__main__":
    import sys
    print(json.dumps(direct(open(sys.argv[1]).read()), indent=2, ensure_ascii=False))
