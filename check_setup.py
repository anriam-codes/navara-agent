from fastembed import TextEmbedding
from qdrant_client import QdrantClient

import config

client = QdrantClient(url=config.QDRANT_URL)
names = [c.name for c in client.get_collections().collections]
print(f"Qdrant OK. Collections: {names}")

model = TextEmbedding(config.EMBED_MODEL)
vector = next(iter(model.embed(["Kafka connection refused"])))
print(f"Embeddings OK. Vector dimension: {len(vector)}")