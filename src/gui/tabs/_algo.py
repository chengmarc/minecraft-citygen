"""Shared state and prerequisite helpers for the preview/generation tabs."""

from __future__ import annotations

from gui.core import common


class AlgoTabMixin:
    blocked_tooltip = "Complete Extract Assets first."
    ready_tooltip = ""
    prerequisite_owner_method = None
    owner_change_hook = "note_preview_inputs_changed"
    legacy_state_sections = ()

    def _init_algo_tab(self, owner):
        self.owner = owner
        self._peer = None

    def _load_algo_state(self):
        for section in ("algo", *self.legacy_state_sections):
            state = self.owner.get_saved_config_section(section)
            if state:
                return state
        return common.default_algo_tab_config()

    def set_peer(self, peer):
        self._peer = peer

    def refresh_prerequisite_state(self):
        ready = True
        method_name = self.prerequisite_owner_method
        if method_name and hasattr(self.owner, method_name):
            ready = bool(getattr(self.owner, method_name)())
        self.controls.action_button.setEnabled(ready)
        self.controls.action_button.setToolTip(
            self.ready_tooltip if ready else self.blocked_tooltip
        )

    def _save_algo_state(self):
        state = self.controls.current_state()
        self.owner.set_saved_config_section("algo", state)
        if self._peer is not None:
            self._peer.controls.set_state(state)
        hook_name = self.owner_change_hook
        if hook_name and hasattr(self.owner, hook_name):
            getattr(self.owner, hook_name)()
        return state
