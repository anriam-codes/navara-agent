import hashlib
import uuid
from collections import Counter
from pathlib import Path

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

import config


def load_documents():
    root = Path(config.KNOWLEDGE_DIR)
    for path in sorted(root.rglob("*.md")):
        yield {
            "source": path.relative_to(root).as_posix(),  # e.g. kafka/trouble.md
            "tech": path.parent.name,                      # e.g. kafka
            "text": path.read_text(encoding="utf-8"),
        }


def chunk_document(doc):
    """One chunk per '## ' section. Lines inside ``` fences are never treated as headings."""
    sections, title, body, in_code = [], None, [], False
    for line in doc["text"].splitlines():
        if line.startswith("```"):
            in_code = not in_code
        if line.startswith("## ") and not in_code:
            if title:
                sections.append((title, body))
            title, body = line[3:].strip(), []
        elif title:
            body.append(line)
    if title:
        sections.append((title, body))

    return [
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc['source']}#{title}")),
            "text": f"[{doc['tech']}] {title}\n\n" + "\n".join(body).strip(),
            "tech": doc["tech"],
            "source": doc["source"],
            "section": title,
        }
        for title, body in sections
    ]


def check_duplicates(chunks):
    """Data-quality guard: same section title in one file, or identical content."""
    ids = Counter(c["id"] for c in chunks)
    bodies = Counter(hashlib.md5(c["text"].split("\n\n", 1)[1].encode()).hexdigest() for c in chunks)
    dup_titles = [c["section"] for c in chunks if ids[c["id"]] > 1]
    if dup_titles or any(n > 1 for n in bodies.values()):
        raise ValueError(f"Duplicate sections found: {sorted(set(dup_titles))}")


def main():
    chunks = [c for doc in load_documents() for c in chunk_document(doc)]
    check_duplicates(chunks)

    model = TextEmbedding(config.EMBED_MODEL)
    vectors = list(model.embed([c["text"] for c in chunks]))

    client = QdrantClient(url=config.QDRANT_URL)
    if client.collection_exists(config.COLLECTION):
        client.delete_collection(config.COLLECTION)
    client.create_collection(
        config.COLLECTION,
        vectors_config=VectorParams(size=config.EMBED_DIM, distance=Distance.COSINE),
    )
    client.upsert(
        config.COLLECTION,
        points=[
            PointStruct(
                id=c["id"],
                vector=v.tolist(),
                payload={k: c[k] for k in ("text", "tech", "source", "section")},
            )
            for c, v in zip(chunks, vectors)
        ],
    )

    for source, n in Counter(c["source"] for c in chunks).items():
        print(f"{source:<25} {n} chunks")
    print(f"Indexed {client.count(config.COLLECTION).count} chunks into '{config.COLLECTION}'")


if __name__ == "__main__":
    main()