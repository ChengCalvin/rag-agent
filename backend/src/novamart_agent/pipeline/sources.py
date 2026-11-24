"""Sources list, built by code from chunk metadata and the document catalog (task 6.4, D15).

The model never writes a citation (AGENT-3): an entry exists only for a document id present in
the catalog, so a fabricated or unknown id yields no entry and no crash. The catalog maps a
document id to its title and file name; it is built by a loader in `rag/` from the documents.
"""

from collections.abc import Mapping, Sequence

from novamart_agent.models import DocumentRef, RetrievedChunk, SourceEntry

DocumentCatalog = Mapping[str, DocumentRef]


def _path(ref: DocumentRef, docs_path_label: str) -> str:
    return f"{docs_path_label}/{ref.file_name}"


def policy_sources(
    chunks: Sequence[RetrievedChunk], catalog: DocumentCatalog, docs_path_label: str
) -> tuple[SourceEntry, ...]:
    """One entry per distinct (document, section) of the chunks, in retrieval order, with the
    title and path from the catalog (path shown under `docs_path_label`, from configuration,
    D15) and the section heading from the chunk."""
    entries: list[SourceEntry] = []
    for chunk in chunks:
        ref = catalog.get(chunk.document_id)
        if ref is None:
            continue
        entry = SourceEntry(ref.title, _path(ref, docs_path_label), chunk.heading or None)
        if entry not in entries:
            entries.append(entry)
    return tuple(entries)


def order_sources(
    policy_document_id: object, catalog: DocumentCatalog, docs_path_label: str
) -> tuple[SourceEntry, ...]:
    """The order-route entry: title and path only, no section heading (D15). No id, a
    non-string id or an id the catalog does not know gives no entry."""
    if not isinstance(policy_document_id, str):
        return ()
    ref = catalog.get(policy_document_id)
    if ref is None:
        return ()
    return (SourceEntry(ref.title, _path(ref, docs_path_label)),)
