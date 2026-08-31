"""Domain errors mapped to stable CLI exit codes."""

from __future__ import annotations


class TrelloAxiError(Exception):
    """Base actionable error."""

    exit_code = 1


class AuthenticationError(TrelloAxiError):
    exit_code = 3


class NotFoundError(TrelloAxiError):
    exit_code = 4


class AmbiguousMatchError(TrelloAxiError):
    exit_code = 5


class ApiError(TrelloAxiError):
    exit_code = 6

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
