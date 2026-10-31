"""The failures of a run that the user can do something about."""

from __future__ import annotations


class RunFailure(RuntimeError):
    """A failure the page words by its ``code``, in the user's language. The message is the same thing in English."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
