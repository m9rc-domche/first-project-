#!/usr/bin/env python3
"""Interface web AutoMotion AI (mobile-first, sans dépendance externe).

  python server.py            -> http://localhost:8000
Dans GitHub Codespaces : onglet "Ports" -> port 8000 -> ouvrir dans le navigateur (Safari iPhone OK).
"""
import html, json, os, threading, traceback, uuid, queue, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from engine.director import direct, apply_instructions
from engine.render import render

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "output")
JOBS = {}
Q = queue.Queue()
os.makedirs(OUT, exist_ok=True)


def worker():
    while True:
        jid = Q.get()
        job = JOBS[jid]
        job["status"] = "rendu"
        try:
            raw = job["script"].strip()
            spec = json.loads(raw) if raw.startswith("{") else direct(raw, job.get("title") or None)
            if job.get("fix"):
                spec, lg = apply_instructions(spec, job["fix"]); job["log"] += lg
            mp4 = os.path.join(OUT, f"{jid}.mp4")
            def prog(p): job["progress"] = round(p * 100)
            rep = render(spec, mp4, os.path.join(ROOT, "work", jid), job.get("tts", "auto"),
                         log=lambda m: job["log"].append(m), progress=prog)
            job.update(status="terminé", progress=100, report=rep, file=f"{jid}.mp4")
        except Exception as e:
            job.update(status="erreur", error=str(e)); job["log"].append(traceback.format_exc())


# plusieurs vidéos en parallèle : 1 worker par cœur (max 3)
for _ in range(min(3, max(1, (os.cpu_count() or 2) // 2))):
    threading.Thread(target=worker, daemon=True).start()

PAGE = """<!doctype html><html lang=fr><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>AutoMotion AI</title>
<style>body{font-family:-apple-system,system-ui,sans-serif;background:#0d0e17;color:#eee;margin:0;padding:16px;max-width:640px;margin:auto}
h1{font-size:22px}textarea,input,select{width:100%;box-sizing:border-box;background:#1b1d2b;color:#fff;border:1px solid #333;border-radius:10px;padding:12px;font-size:16px;margin:6px 0 12px}
button{width:100%;padding:14px;font-size:17px;border:0;border-radius:12px;background:#ffd21a;color:#000;font-weight:700}
.job{background:#1b1d2b;border-radius:12px;padding:12px;margin:10px 0}a{color:#ffd21a}video{width:100%;border-radius:10px;margin-top:8px}
small{color:#999}</style></head><body>
<h1>🎬 AutoMotion AI</h1>
<form method=post action=/generate>
<label>Script (une phrase = une scène) ou plan JSON</label>
<textarea name=script rows=9 required>{demo}</textarea>
<label>Titre (optionnel)</label><input name=title>
<label>Corrections (optionnel, ex. <i>scene 3: camera=track</i>)</label><textarea name=fix rows=2></textarea>
<label>Voix</label><select name=tts><option value=auto>Auto (meilleure dispo)</option><option value=piper>Piper (naturelle)</option><option value=espeak>eSpeak (FR/EN)</option><option value=flite>Flite (EN)</option></select>
<button>Générer la vidéo</button></form>
<h2 style="font-size:18px">Vidéos</h2>{jobs}
<script>if(document.querySelector('[data-run]'))setTimeout(()=>location.reload(),4000)</script>
</body></html>"""


def jobs_html():
    out = []
    for jid, j in sorted(JOBS.items(), key=lambda x: -x[1]["created"]):
        s = html.escape(j["script"][:80])
        body = f"<b>{j['status']}</b> {j.get('progress', 0)}%<br><small>{s}…</small>"
        if j.get("file"):
            rep = j["report"]
            body += (f"<video controls playsinline src='/video/{j['file']}'></video>"
                     f"<a href='/video/{j['file']}' download>⬇️ Télécharger MP4</a> "
                     f"<small>{rep['duration']}s · voix {', '.join(rep['tts'])} · corrections auto: {len(rep['auto_fixes'])}</small>")
        if j.get("error"):
            body += f"<pre style='white-space:pre-wrap'>{html.escape(j['error'])}</pre>"
        run = " data-run" if j["status"] in ("en attente", "rendu") else ""
        out.append(f"<div class=job{run}>{body}</div>")
    return "".join(out) or "<small>Aucune vidéo pour l'instant.</small>"


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
        self.send_response(code); self.send_header("Content-Type", ctype)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/":
            demo = html.escape(open(os.path.join(ROOT, "scripts", "demo_500iq.txt")).read())
            return self._send(200, PAGE.replace("{demo}", demo).replace("{jobs}", jobs_html()).encode())
        if p == "/api/jobs":
            data = {k: {kk: vv for kk, vv in v.items() if kk != "log"} for k, v in JOBS.items()}
            return self._send(200, json.dumps(data, ensure_ascii=False).encode(), "application/json")
        if p.startswith("/video/"):
            f = os.path.join(OUT, os.path.basename(p))
            if os.path.exists(f):
                return self._send(200, open(f, "rb").read(), "video/mp4",
                                  {"Content-Disposition": f"inline; filename={os.path.basename(f)}"})
        self._send(404, b"not found")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        ctype = self.headers.get("Content-Type", "")
        raw = self.rfile.read(n).decode("utf-8")
        form = json.loads(raw) if "json" in ctype else {k: v[0] for k, v in parse_qs(raw).items()}
        jid = uuid.uuid4().hex[:8]
        JOBS[jid] = dict(script=form.get("script", ""), title=form.get("title", ""), fix=form.get("fix", ""),
                         tts=form.get("tts", "auto"), status="en attente", progress=0, log=[], created=time.time())
        Q.put(jid)
        if "json" in ctype:
            return self._send(200, json.dumps({"job": jid}).encode(), "application/json")
        self.send_response(303); self.send_header("Location", "/"); self.end_headers()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"AutoMotion AI -> http://0.0.0.0:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
