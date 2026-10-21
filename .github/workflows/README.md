# AutoMotion AI : générateur de Shorts animés 2D (prototype v0.1)

Script texte -> réalisateur auto (scènes, décors, actions, caméra) -> voix off -> animation stickman riggée
-> effets sonores synchronisés -> QA + auto-corrections -> MP4 1080x1920 30 fps.

## Testé et fonctionnel
- Personnages vectoriels riggés (squelette 2D) : marche, course, pas furtifs, réflexion, clavier, choc, lancer, salut, pointer, disparition. Clignements, respiration, 7 expressions.
- 4 décors procéduraux avec parallaxe (chambre, ville de nuit, forêt, coucher de soleil), téléphone balistique + éclats, émotes animées.
- Caméra : push-in, pull-out, suivi lissé, punch-zoom + tremblement sur impact. Transitions iris / flash.
- Sous-titres mot à mot style Shorts, titre accroche.
- Audio : TTS en cascade (Piper > eSpeak-ng > Flite), pas calés sur le cycle de marche, clics clavier, whoosh, impact, fracas, ding, musique originale générée avec ducking.
- QA : personnage hors cadre -> correction auto caméra/position ; vérif finale durée, flux, images noires, silences.
- Corrections par instructions texte : `--fix "scene 3: camera=track"`.
- Interface web mobile (file d'attente, rendus parallèles, lecture + téléchargement MP4).

## Lancer
    sudo apt-get install -y ffmpeg libcairo2 espeak-ng
    pip install -r requirements.txt        # + pip install piper-tts pour une voix naturelle
    python automotion.py scripts/demo_500iq.txt -o output/demo.mp4
    python server.py                       # interface web, port 8000

## Depuis un iPhone, 0 FCFA
1. GitHub Actions : crée un repo, uploade ce dossier, puis Actions > "Render video" > Run workflow > colle ton script > télécharge l'artefact "videos".
2. Codespaces (quota gratuit mensuel) : Code > Codespaces > Create, puis `python server.py`, ouvre le port 8000 dans Safari.

## Voix
- Piper (piper-tts) : FR fr_FR-siwis-medium, EN en_US-ryan-high, téléchargées par le workflow (vérifier la licence de chaque voix avant usage commercial). Variable PIPER_MODEL=/chemin/voix.onnx.
- eSpeak-ng : FR/EN, robotique mais fiable. Flite : anglais seulement (repli).

## Architecture
engine/director.py (script -> plan) · engine/motion.py (actions) · engine/rig.py (personnage) ·
engine/world.py (décors) · engine/audio.py (TTS, SFX, mix) · engine/render.py (pipeline, caméra, QA).
Le plan JSON (docs/SCENE_SCHEMA.md) est l'interface stable : un futur moteur 3D n'aura qu'à rendre le même plan.
ChatGPT peut écrire ce JSON pour toi : colle-le dans l'interface à la place du script.
