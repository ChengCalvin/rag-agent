"""Shared error types (LAYER-4, ARCH-ERR-1)."""


class DataLoadError(ValueError):
    """A synthetic data file is missing a field or has a value of the wrong shape.

    Messages name the file and the field, never a field value, so a malformed
    customer record cannot leak personal data into logs (ERR-2).
    """


class EscalationContactError(DataLoadError):
    """The store operations document has no usable `escalation_contact` field (D13 case C)."""


class EligibilityError(ValueError):
    """Return eligibility cannot be determined (D13 case F). Messages never carry values."""


class PolicyParametersError(EligibilityError):
    """The returns document front-matter lacks a usable return parameter; names the field."""


class OrderDataError(EligibilityError):
    """An order cannot be evaluated: no usable delivery date (missing, or after the reference
    date) or no items."""


class EmbeddingError(RuntimeError):
    """The embedding call failed (network, quota or a malformed reply).

    Messages never carry the text that was being embedded (ERR-2).
    """


class CostRecordError(ValueError):
    """A usage record stored in session state is malformed (a code bug). Never carries values."""


class ToolResultError(ValueError):
    """A model-facing tool result dict does not have the documented shape (a code bug, not user
    input). Messages name the field, never a value."""


class StateDataError(ValueError):
    """A value kept in session state by the pipeline is malformed (a code bug, not user input).
    Messages name the key, never a value."""
