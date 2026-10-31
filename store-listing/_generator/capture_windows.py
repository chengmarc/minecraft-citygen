"""The app's window for each screenshot in each language, into build/store-listing/windows/<code>/<shot>.png.

The real page, in headless Edge, on a stand-in for the bridge: it's told the runs are done, with the pictures
replay_scenes.py makes, and shot. No window opens, and nothing but the words changes between languages. The one thing
drawn is the Windows title bar, which a page doesn't have.

render.py runs this before it lays out the screenshots.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
import wsgiref.simple_server
from pathlib import Path
from urllib.parse import parse_qs

import replay_scenes
from replay_scenes import PICTURES, regions, SCENES

from citygen.gui import form, server

BUILD = Path(__file__).resolve().parents[2] / "build"
WINDOWS = BUILD / "store-listing" / "windows"
EDGE_PROFILE = BUILD / "edge-capture"

# Each screenshot: the scene its pictures come from, the tab showing, and the window's height. The width is the app's.
WIDTH = 1266
SHOTS = {
    "promo": ("promo", "build", 946),
    "size": ("size", "build", 946),
    "styles": ("styles", "build", 946),
    "extract": ("promo", "extract", 846),
    "preview": ("promo", "preview", 846),
}
TITLE_BAR = 32
# Stands in for the user's own path, which has no place on a screenshot.
WORLD_PATH = "C:\\MC\\saves\\CityGen"


def extraction(scene):
    """The Extract tab as the bridge would describe it."""
    road_box, build_types = regions(scene)
    boxes = {"road": road_box, "house": build_types[0].bounds, "landmark": build_types[1].bounds}
    return {
        "worldPath": WORLD_PATH,
        "worldReady": True,
        "sourceVersion": "26.1.2",
        "versions": ["auto", "26.1.2"],
        "targetVersion": "auto",
        "areas": {key: {"chunks": list(box.chunk_span())} for key, box in boxes.items()},
    }


def boot(name, language):
    scene = json.loads(SCENES.read_text(encoding="utf-8"))[name]
    return {
        "algo": {"seed": scene["seed"], "algo": form.form_values(scene.get("algo"))},
        "form": form.form_spec(),
        "language": language,
        "extraction": extraction(scene),
        "gates": {"extract": True, "preview": True, "build": True},
    }


# Injected at the end of the page: the bridge's stand-in, then every run reported finished.
STAND_IN = """
<style>
  body { padding-top: %(bar)dpx; }
  .title-bar { position: fixed; top: 0; right: 0; display: flex; z-index: 9; color: var(--sky-text); }
  .title-bar svg { width: 46px; height: %(bar)dpx; }
  /* A finished window, not one on its way there. The clouds hold still, each where its own delay puts it, so the same
     words make the same picture, and git sees no change in en/'s. */
  .page > * { animation: none !important; }
  .cloud { animation-play-state: paused !important; }
  * { transition: none !important; }
</style>
<!-- In the page, so its load waits for them, and the viewers have them at once. -->
<img hidden src="/scene/%(scene)s/roads.png"><img hidden src="/scene/%(scene)s/builds.png">
<img hidden src="/scene/%(scene)s/grid.png"><img hidden src="/scene/%(scene)s/city-preview.png">
<img hidden src="/scene/%(scene)s/city-render.png">
<div class="title-bar">
  <svg viewBox="0 0 46 32"><path d="M18 16h10" stroke="currentColor"/></svg>
  <svg viewBox="0 0 46 32"><rect x="18.500" y="11.500" width="9" height="9" rx="1" fill="none" stroke="currentColor"/></svg>
  <svg viewBox="0 0 46 32"><path d="M18 11l10 10M28 11L18 21" stroke="currentColor"/></svg>
</div>
<script>
  const BOOT = %(boot)s;
  const PICTURE = (name) => ({ src: `/scene/%(scene)s/${name}.png` });
  window.pywebview = { api: { bootstrap: async () => BOOT, save_algo: async () => {} } };
  // The run bars at once, without their glide.
  const set = ProgressBar.prototype.set;
  ProgressBar.prototype.set = function (value) {
    set.call(this, value);
    if (this.segments.length) { this.shown = this.target; this.render(); }
  };
  window.addEventListener("load", () => {
    window.dispatchEvent(new Event("pywebviewready"));
    const started = setInterval(() => {
      if (!document.body.classList.contains("ready")) return;
      clearInterval(started);
      const runs = {
        extract: { roads: PICTURE("roads"), builds: PICTURE("builds") },
        preview: { grid: PICTURE("grid"), city: PICTURE("city-preview") },
        build: { city: PICTURE("city-render") },
      };
      for (const [tab, images] of Object.entries(runs)) {
        citygen.receive("progress", { tab });
        citygen.receive("done", { tab, images });
        citygen.receive("finished", { tab, gates: BOOT.gates });
      }
      document.querySelector('.step[data-tab="%(tab)s"]').click();
      settle();
    }, 20);
  });
  // Edge's clock for the shot skips ahead of a picture being decoded, but stops for a request. So ask, again and again,
  // until all five viewers hold their pictures, and a few times more for them to fit and paint.
  async function settle() {
    const shown = () => document.querySelectorAll(".viewer.has-image").length === 5
      && !document.querySelector(".viewer-layer.loading");
    while (!shown()) await fetch("/tick");
    for (let n = 0; n < 5; n += 1) await fetch("/tick");
  }
</script>
"""


def app(environ, start_response):
    """The page with the stand-in, for ``?shot=&language=``; the scenes' pictures; and the rest as the app serves it."""
    path = environ.get("PATH_INFO", "/")
    if path == "/tick":
        time.sleep(0.05)
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b""]
    if path.startswith("/scene/"):
        picture = PICTURES.joinpath(*path.split("/")[2:])
        start_response("200 OK", [("Content-Type", "image/png")])
        return [picture.read_bytes()]
    if path != "/":
        return server.app(environ, start_response)
    query = parse_qs(environ.get("QUERY_STRING", ""))
    shot, language = query["shot"][0], query["language"][0]
    name, tab, _height = SHOTS[shot]
    inject = STAND_IN % {"bar": TITLE_BAR, "boot": json.dumps(boot(name, language)), "scene": name, "tab": tab}
    page = (server.STATIC / "index.html").read_text(encoding="utf-8").replace("</body>", inject + "</body>")
    body = page.encode("utf-8")
    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(body)))])
    return [body]


class _Quiet(wsgiref.simple_server.WSGIRequestHandler):
    def log_message(self, *_args):
        pass


def capture(edge, languages):
    names = json.loads(SCENES.read_text(encoding="utf-8"))
    missing = [name for name in names if not (PICTURES / name / "city-render.png").is_file()]
    if missing:
        replay_scenes.main(missing)

    httpd = wsgiref.simple_server.make_server("127.0.0.1", 0, app, handler_class=_Quiet)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    shutil.rmtree(WINDOWS, ignore_errors=True)
    try:
        for language in languages:
            (WINDOWS / language).mkdir(parents=True)
            for shot, (_name, _tab, height) in SHOTS.items():
                file = WINDOWS / language / f"{shot}.png"
                # --virtual-time-budget lets the pictures load and the page settle, without waiting in real time.
                subprocess.run([
                    edge, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={EDGE_PROFILE}",
                    "--force-device-scale-factor=2", f"--window-size={WIDTH},{height}", "--virtual-time-budget=20000",
                    "--run-all-compositor-stages-before-draw",
                    f"--screenshot={file}", f"http://127.0.0.1:{httpd.server_port}/?shot={shot}&language={language}",
                ], check=False, capture_output=True)
                if not file.is_file():
                    raise SystemExit(f"Edge didn't write {file}.")
            print(f"windows/{language}", flush=True)
    finally:
        httpd.shutdown()
