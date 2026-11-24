"""Document id to title and file name, for the order-route Sources entry (task 6.4, D15).

Built from the loaded documents, so the mapping is data-driven (ARCH-CFG-2), not a hard-coded
table. It carries title and file name only: no section heading, no document text.
"""

from novamart_agent.models import Document, DocumentRef


def build_catalog(documents: tuple[Document, ...]) -> dict[str, DocumentRef]:
    """Map every document id to its `DocumentRef`. Ids are unique (checked by the loader)."""
    return {d.doc_id: DocumentRef(d.title, d.path.name) for d in documents}
