"""Errors of the eval kit."""


class CaseError(ValueError):
    """A case file or check is malformed. Raised at load, before any model call."""
