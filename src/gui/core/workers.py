"""Background-worker signals and progress-bar mixins for the Qt tabs."""

from __future__ import annotations

import threading

from PySide6 import QtCore, QtWidgets

from gui.core import progress


class WorkerSignals(QtCore.QObject):
    status = QtCore.Signal(str)
    pipeline_progress = QtCore.Signal(str, float, float, str)
    success = QtCore.Signal(object)
    failed = QtCore.Signal(str, str, str)
    finished = QtCore.Signal()


class RegionPreviewSignals(QtCore.QObject):
    loaded = QtCore.Signal(object, object)
    failed = QtCore.Signal(str)
    progress = QtCore.Signal(int, int)  # (completed, total)


# Running jobs' (signals, thread) pairs, held so neither is collected mid-run.
_active_jobs = []


def start_background_job(
    parent,
    job,
    *,
    on_progress=None,
    on_success=None,
    on_failed=None,
    on_finished=None,
    failure_title="Job failed",
    failure_status=None,
    thread_factory=threading.Thread,
):
    """Run ``job(progress)`` on a daemon thread and relay results over Qt signals."""
    signals = WorkerSignals(parent)
    failure_status = failure_status or failure_title

    if on_progress is not None:
        signals.pipeline_progress.connect(on_progress)
    if on_success is not None:
        signals.success.connect(on_success)
    if on_failed is not None:
        signals.failed.connect(on_failed)
    if on_finished is not None:
        signals.finished.connect(on_finished)

    def emit_progress(stage, completed, total, label):
        signals.pipeline_progress.emit(stage, float(completed), float(total), label or "")

    def worker():
        try:
            result = job(emit_progress)
        except Exception as exc:  # boundary: report background failures to the UI thread
            message = str(exc).strip() or failure_status
            signals.failed.emit(failure_title, message, failure_status)
        else:
            signals.success.emit(result)
        finally:
            signals.finished.emit()

    thread = thread_factory(target=worker, daemon=True)
    job_ref = (signals, thread)
    _active_jobs.append(job_ref)

    def forget_job():
        try:
            _active_jobs.remove(job_ref)
        except ValueError:
            pass

    signals.finished.connect(forget_job)
    thread.start()
    return thread


class ProgressMixin:
    def _init_progress_mixin(self):
        self._progress_timer = QtCore.QTimer(self)
        self._progress_timer.timeout.connect(self._progress_tick)
        self._progress_soft_target = 0.0

    def set_status(self, status):
        self.status_label.setText(status)

    def show_failure(self, title, message, status):
        self.set_status(status)
        QtWidgets.QMessageBox.critical(self, title, message)

    def _start_progress(self):
        self._cancel_progress_animation()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._progress_soft_target = 0.0

    def _finish_progress(self):
        self._cancel_progress_animation()
        maximum = self.progress_bar.maximum() or 100
        self.progress_bar.setValue(maximum)

    def _stop_progress(self):
        self._cancel_progress_animation()

    def _progress_tick(self):
        current = float(self.progress_bar.value())
        if current >= self._progress_soft_target:
            self._cancel_progress_animation()
            return
        remaining = self._progress_soft_target - current
        step = max(0.2, remaining * progress.PROGRESS_CREEP_RATE)
        self.progress_bar.setValue(int(round(min(current + step, self._progress_soft_target))))

    def _cancel_progress_animation(self):
        if self._progress_timer.isActive():
            self._progress_timer.stop()
