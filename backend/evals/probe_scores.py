"""Task 8.5/8.7 helper (OWNER-RUN ONLY, needs GOOGLE_API_KEY; embedding calls only, no chat model).

Prints the best cosine score each question gets against the documents a persona may see, so a
refusal case C question can be chosen with evidence. From the repo root:

    python backend/evals/probe_scores.py [audience ...] -- "question one" "question two"
Default audience: all_staff. Without questions, a built-in candidate list is used.
"""

import sys

from dotenv import load_dotenv

from novamart_agent.config import load_settings
from novamart_agent.rag import Embedder, GenaiEmbeddingClient
from novamart_agent.rag.chunker import chunk_documents
from novamart_agent.rag.documents import load_documents
from novamart_agent.rag.index import CosineIndex

CANDIDATES = (
    "What is the return window for electronics?",
    "A customer wants to return a tablet delivered 20 days ago. Is it inside the window?",
    "How many days does price matching cover?",
    "How much clearance does the NovaCool fridge need behind it?",
    "What is NovaMart's policy on bulk corporate orders?",
    "What is the dress code for staff working on the shop floor?",
    "How do I request vacation days?",
    "What is the parking policy at the store?",
    "What is the staff discount on personal purchases?",
    "How do I reset my email password?",
    "What time does the cafeteria open?",
    "What is the capital of France?",
)


def main() -> int:
    # standards-exception(CONV-1): owner-run eval scripts load backend/.env before config
    load_dotenv("backend/.env")
    settings = load_settings()
    args = sys.argv[1:]
    questions = tuple(args[args.index("--") + 1 :]) if "--" in args else CANDIDATES
    audiences = frozenset(args[: args.index("--")] if "--" in args else ["all_staff"])
    docs = load_documents(settings.data_dir / "docs")
    embedder = Embedder(
        GenaiEmbeddingClient(), settings.embedding_model, settings.data_dir / ".cache"
    )
    chunks = chunk_documents(docs)
    index = CosineIndex(chunks, [embedder.embed_document(f"{c.title}: {c.text}") for c in chunks])
    print(f"threshold {settings.similarity_threshold}, audiences {sorted(audiences)}")
    for q in questions:
        ranked = index.rank(embedder.embed_query(q).vector, audiences)
        top = ranked[0].score if ranked else 0.0
        print(f"{top:8.3f}  {q}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
