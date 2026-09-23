import os
from dotenv import load_dotenv

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = "tech_docs"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384
KNOWLEDGE_DIR = "knowledge"

TOP_K = 4
MIN_SCORE = 0.68  # below this, retrieval counts as "not in the knowledge base"
LLM_BASE_URL = os.environ["LLM_BASE_URL"]
LLM_API_KEY = os.environ["LLM_API_KEY"]
LLM_MODEL = os.environ["LLM_MODEL"]