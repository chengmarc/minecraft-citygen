"""Background-worker signals and progress-bar mixins for the Qt tabs."""

from __future__ import annotations

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
