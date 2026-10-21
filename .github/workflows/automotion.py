#!/usr/bin/env python3
"""AutoMotion AI - ligne de commande.

  python automotion.py script.txt -o video.mp4
  python automotion.py scenes.json -o video.mp4          (plan produit par ChatGPT)
  python automotion.py script.txt --fix "scene 3: camera=track"
"""
import argparse, json, os, sys
from engine.director import direct, apply_instructions
from engine.render import render


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="script .txt ou plan .json")
    ap.add_argument("-o", "--output", default="output/video.mp4")
    ap.add_argument("--title")
    ap.add_argument("--tts", default="auto", choices=["auto", "piper", "espeak", "flite"])
    ap.add_argument("--fix", default="", help="instructions de correction (une par ligne)")
    ap.add_argument("--work", default="work")
    ap.add_argument("--previews", type=int, default=0)
    a = ap.parse_args()
    raw = open(a.input, encoding="utf-8").read()
    spec = json.loads(raw) if a.input.endswith(".json") else direct(raw, a.title)
    if a.fix:
        spec, log = apply_instructions(spec, a.fix.replace("\\n", "\n"))
        print("\n".join(log))
    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    os.makedirs(a.work, exist_ok=True)
    json.dump({k: v for k, v in spec.items()}, open(os.path.join(a.work, "plan.json"), "w"), indent=2, ensure_ascii=False)
    rep = render(spec, a.output, a.work, a.tts, preview_every=a.previews or None)
    json.dump(rep, open(os.path.splitext(a.output)[0] + "_report.json", "w"), indent=2, ensure_ascii=False)
    print(json.dumps(rep, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
