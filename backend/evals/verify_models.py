"""Task 1.2 live check (OWNER-RUN ONLY, needs GOOGLE_API_KEY; ARCH-TEST-3).

Makes exactly one generate call and one embedding call through google-genai and prints the
usage fields. Not run by agents. Usage, from the repo root with backend/.env filled in:

    python backend/evals/verify_models.py [chat-model-id]
"""

import sys

from dotenv import load_dotenv
from google import genai
from google.genai import types

from novamart_agent.config import load_settings


def main() -> int:
    # standards-exception(CONV-1): owner-run eval scripts load backend/.env before config
    load_dotenv("backend/.env")
    settings = load_settings()
    chat_model = sys.argv[1] if len(sys.argv) > 1 else settings.model
    client = genai.Client()  # reads GOOGLE_API_KEY; backend switch from env (design D6)

    reply = client.models.generate_content(model=chat_model, contents="Reply with the word: ok")
    print("chat model:", chat_model)
    print("chat text:", reply.text)
    print("chat usage:", reply.usage_metadata)

    emb = client.models.embed_content(
        model=settings.embedding_model,
        contents="return window for opened items",
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    vectors = emb.embeddings or []
    print("embedding model:", settings.embedding_model)
    print("embedding dims:", len(vectors[0].values or []) if vectors else 0)
    print("embedding token fields (task 1.4):", emb.metadata, [v.statistics for v in vectors])
    return 0


if __name__ == "__main__":
    sys.exit(main())
