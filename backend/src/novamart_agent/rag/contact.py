"""Escalation contact lookup (D13 case C; ARCH-CFG-2: policy facts are not hard-coded).

Read from the `escalation_contact` front-matter field of the store operations document at
load time. A missing or blank field fails loudly rather than producing a reply with no contact.
"""

from novamart_agent.errors import EscalationContactError
from novamart_agent.models import Document

STORE_OPERATIONS_DOC_ID = "store-operations"
CONTACT_FIELD = "escalation_contact"


def escalation_contact(documents: tuple[Document, ...]) -> str:
    """Return the escalation contact text, or raise `EscalationContactError`."""
    for document in documents:
        if document.doc_id == STORE_OPERATIONS_DOC_ID:
            value = document.metadata.get(CONTACT_FIELD)
            if isinstance(value, str) and value.strip():
                return value.strip()
            raise EscalationContactError(
                f"{STORE_OPERATIONS_DOC_ID}: field '{CONTACT_FIELD}' must be a non-empty string"
            )
    raise EscalationContactError(f"document '{STORE_OPERATIONS_DOC_ID}' is not loaded")
