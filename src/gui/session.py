"""What the tabs share: the saved settings, and background runs that report to the page.

A run sends the page four kinds of event, each naming its tab, with facts, not wording (the page's text.js
words them):

- ``progress``: ``value`` and ``softTarget`` in percent; the bar jumps to the value,
  then creeps toward the soft target every ``tickMs`` until the next event. ``detail``
  is the pipeline's own name for the step under way, when it has one;
- ``done``: the images the run made;
- ``failed``: the error's text, if it had any;
- ``finished``: after either, with every tab's gate.

On the way, a run can show what it has so far: ``partial`` swaps in images that are
ready early (Preview's road layout, Build's blueprint), and ``piece`` adds one
rendered piece to a viewer's growing gallery (Extract).
"""

from __future__ import annotations

import threading

from gui import files, progress


class Settings:
    """``citygen.json``, one section per tab, written through on every change."""

    def __init__(self):
        self._config = files.load_saved_gui_config()

    def get(self, section):
        value = self._config.get(section)
        return value if isinstance(value, dict) else None

    def set(self, section, value):
        self._config[section] = value
        files.save_saved_gui_config(self._config)


class Runner:
    """Runs one job per tab at a time on a daemon thread."""

    def __init__(self, emit, gates, *, thread_factory=threading.Thread):
        self._emit = emit
        self._gates = gates
        self._thread_factory = thread_factory
        self._running = set()

    def is_running(self, tab):
        return tab in self._running

    def show(self, tab, images):
        """Images a run has ready before it's done: ``{viewer: image}``, an image marked ``blueprint`` as a stand-in."""
        self._emit("partial", {"tab": tab, "images": images})

    def piece(self, tab, viewer, index, image):
        """The ``index``-th (from 1) piece a run has rendered, for ``viewer``'s gallery; the first starts it afresh."""
        self._emit("piece", {"tab": tab, "viewer": viewer, "index": index, **image})

    def start(self, tab, job, *, on_success):
        """Run ``job(report)``; ``report(value, soft_target, detail=None)`` takes PROGRESS_BAR_SCALE units.

        ``on_success(result)`` returns the ``done`` event's payload.
        """
        self._running.add(tab)
        self._emit("progress", {"tab": tab, "value": 0, "softTarget": None})

        def report(value, soft_target, detail=None):
            scale = progress.PROGRESS_BAR_SCALE
            self._emit("progress", {
                "tab": tab,
                "value": value * 100 / scale,
                "softTarget": None if soft_target is None else soft_target * 100 / scale,
                "tickMs": progress.tick_ms(tab),
                "creepRate": progress.CREEP_RATE,
                "detail": detail,
            })

        def worker():
            try:
                result = job(report)
                payload = on_success(result)
            except Exception as exc:  # boundary: report background failures to the page
                self._emit("failed", {"tab": tab, "detail": str(exc).strip() or None})
            else:
                self._emit("done", {"tab": tab, **payload})
            finally:
                self._running.discard(tab)
                self._emit("finished", {"tab": tab, "gates": self._gates()})

        self._thread_factory(target=worker, daemon=True).start()
