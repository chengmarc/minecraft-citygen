"""What the tabs share: the saved settings, and background runs that report to the page.

A run sends the page four kinds of event, each naming its tab:

- ``progress``: ``value`` and ``softTarget`` in percent; the bar jumps to the value,
  then creeps toward the soft target every ``tickMs`` until the next event;
- ``done``: what the tab shows when the run succeeds;
- ``failed``: the error dialog's title and message, and the status line;
- ``finished``: after either, with every tab's gate.
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

    def start(self, tab, job, *, failure_title, status, on_success):
        """Run ``job(report)``; ``report(value, soft_target, status, creep)`` takes PROGRESS_BAR_SCALE units.

        ``on_success(result)`` returns the ``done`` event's payload.
        """
        self._running.add(tab)
        self._emit("progress", {"tab": tab, "value": 0, "softTarget": None, "status": status})

        def report(value, soft_target, status, creep="default"):
            scale = progress.PROGRESS_BAR_SCALE
            self._emit("progress", {
                "tab": tab,
                "value": value * 100 / scale,
                "softTarget": None if soft_target is None else soft_target * 100 / scale,
                "tickMs": progress.creep_tick_ms(creep),
                "creepRate": progress.PROGRESS_CREEP_RATE,
                "status": status,
            })

        def worker():
            try:
                result = job(report)
                payload = on_success(result)
            except Exception as exc:  # boundary: report background failures to the page
                self._emit("failed", {
                    "tab": tab,
                    "title": failure_title,
                    "message": str(exc).strip() or failure_title,
                    "status": failure_title,
                })
            else:
                self._emit("done", {"tab": tab, **payload})
            finally:
                self._running.discard(tab)
                self._emit("finished", {"tab": tab, "gates": self._gates()})

        self._thread_factory(target=worker, daemon=True).start()
