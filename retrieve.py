import argparse

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchText, MatchValue

import config

model = TextEmbedding(config.EMBED_MODEL)
client = QdrantClient(url=config.QDRANT_URL)


def search(question, top_k=4, tech=None, doc_type=None):
    """Return the top_k most similar chunks as dicts (score + payload).

    tech: filter to one technology ("kafka", "docker", "postgresql", "fastapi").
    doc_type: filter to chunks whose source file ends with this ("basics.md" or "trouble.md").
    Both filters are applied INSIDE the Qdrant query, so top_k is computed within
    the filtered subset — not globally, then trimmed. That distinction matters:
    filtering after retrieval can silently drop the correct chunk if it wasn't in the
    unfiltered top_k window.
    """
    vector = next(iter(model.query_embed(question))).tolist()

    conditions = []
    if tech:
        conditions.append(FieldCondition(key="tech", match=MatchValue(value=tech)))
    if doc_type:
        conditions.append(FieldCondition(key="source", match=MatchText(text=doc_type)))
    query_filter = Filter(must=conditions) if conditions else None

    result = client.query_points(
        config.COLLECTION, query=vector, limit=top_k, query_filter=query_filter
    )
    return [{"score": p.score, **p.payload} for p in result.points]


def show(question, hits):
    print(f"\nQuestion: {question}\n")
    for i, h in enumerate(hits, 1):
        body = h["text"].split("\n\n", 1)[1].replace("\n", " ")
        print(f"{i}. score={h['score']:.3f}  {h['source']}  >  {h['section']}")
        print(f"   {body[:180]}...\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("question", nargs="*", help="leave empty for interactive mode")
    parser.add_argument("--tech", help="filter: kafka | docker | postgresql | fastapi")
    parser.add_argument("--k", type=int, default=4, help="number of chunks to return")
    args = parser.parse_args()

    if args.question:
        q = " ".join(args.question)
        show(q, search(q, args.k, args.tech))
    else:
        while q := input("Question (empty to quit)> ").strip():
            show(q, search(q, args.k, args.tech))