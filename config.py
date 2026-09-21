import os
from dotenv import load_dotenv

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = "tech_docs"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384
KNOWLEDGE_DIR = "knowledge"