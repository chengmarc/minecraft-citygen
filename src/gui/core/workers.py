"""Background-worker signals and progress-bar mixins for the Qt tabs."""

from __future__ import annotations

import threading

from PySide6 import QtCore, QtWidgets

from gui.core import common


class WorkerSignals(QtCore.QObject):
    status = QtCore.Signal(str)
    begin_progress = QtCore.Signal(float, float, str)
    set_progress = QtCore.Signal(float)
    pipeline_progress = QtCore.Signal(str, float, float, str)
    success = QtCore.Signal(object)
    failed = QtCore.Signal(str, str, str)
    finished = QtCore.Signal()


class RegionPreviewSignals(QtCore.QObject):
    loaded = QtCore.Signal(object, object)
    failed = QtCore.Signal(str)
    progress = QtCore.Signal(int, int)  # (completed, total)


class ProgressMixin:
    def _init_progress_mixin(self):
        self._progress_timer = QtCore.QTimer(self)
        self._progress_timer.timeout.connect(self._progress_tick)
        self._progress_soft_target = 0.0

    def set_status(self, status):
        self.status_label.setText(status)

    def _show_failure(self, title, message, status):
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

    def _begin_script_progress(self, start_value, end_value, status):
        self._cancel_progress_animation()
        self.progress_bar.setValue(int(start_value))
        segment = max(float(end_value) - float(start_value), 0.0)
        self._progress_soft_target = float(start_value) + segment * common.SCRIPT_PROGRESS_HEADROOM
        self.set_status(status)
        self._progress_timer.start(common.SCRIPT_PROGRESS_TICK_MS)

    def _complete_script_progress(self, value):
        self._cancel_progress_animation()
        self.progress_bar.setValue(int(round(value)))

    def _progress_tick(self):
        current = float(self.progress_bar.value())
        if current >= self._progress_soft_target:
            self._cancel_progress_animation()
            return
        remaining = self._progress_soft_target - current
        step = max(0.2, remaining * common.SCRIPT_PROGRESS_RATE)
        self.progress_bar.setValue(int(round(min(current + step, self._progress_soft_target))))

    def _cancel_progress_animation(self):
        if self._progress_timer.isActive():
            self._progress_timer.stop()


class WeightedTaskMixin(ProgressMixin):
    def _run_weighted_tasks(self, *, button, tasks, start_status, fail_title, fail_status, complete_status, on_success, success_payload):
        self._start_progress()
        button.setEnabled(False)
        signals = WorkerSignals(self)
        signals.status.connect(self.set_status)
        signals.begin_progress.connect(self._begin_script_progress)
        signals.set_progress.connect(self._complete_script_progress)
        signals.success.connect(lambda payload: (on_success(payload), self._finish_progress(), self.set_status(complete_status)))
        signals.failed.connect(self._show_failure)
        signals.finished.connect(lambda: (self._stop_progress(), button.setEnabled(True)))

        def worker():
            try:
                completed_weight = 0.0
                total_tasks = len(tasks)
                signals.status.emit(start_status)
                for index, (module, annotation, weight, func) in enumerate(tasks, start=1):
                    signals.begin_progress.emit(
                        completed_weight,
                        completed_weight + weight,
                        common.format_stage_status(index, total_tasks, module, annotation),
                    )
                    func()
                    completed_weight += weight
                    signals.set_progress.emit(completed_weight)
            except Exception as exc:  # boundary: surface any background failure to the UI
                signals.failed.emit(fail_title, str(exc).strip() or fail_status, fail_status)
            else:
                signals.success.emit(success_payload)
            finally:
                signals.finished.emit()

        threading.Thread(target=worker, daemon=True).start()
