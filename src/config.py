import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Root paths ---
ROOT_DIR = Path(__file__).parent.parent

# --- LLM ---
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")  # "openai" or "anthropic"
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# --- Embeddings ---
# "local" uses all-MiniLM-L6-v2 via SentenceTransformers (no API key needed) — default
# "openai" uses text-embedding-3-small via OpenAI API
EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "local")
OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
LOCAL_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

# --- Data directories ---
DATA_DIR: Path = ROOT_DIR / "data"
UPLOAD_DIR: Path = DATA_DIR / "uploaded"
CONVERTED_MD_DIR: Path = DATA_DIR / "converted_markdown"
VECTOR_STORE_DIR: Path = DATA_DIR / "vector_store"
OUTPUTS_DIR: Path = DATA_DIR / "outputs"

# --- Corpus ---
CORPUS_DIR: Path = ROOT_DIR / "corpus"

# --- Chroma collection names ---
UPLOADED_DOCS_COLLECTION: str = "uploaded_docs_collection"
AI_ACT_CORPUS_COLLECTION: str = "ai_act_corpus_collection"

# --- Chunking ---
CHUNK_SIZE: int = 800
CHUNK_OVERLAP: int = 150

# --- Retrieval ---
TOP_K: int = 6

# --- Ensure directories exist at import time ---
for _dir in (UPLOAD_DIR, CONVERTED_MD_DIR, VECTOR_STORE_DIR, OUTPUTS_DIR, CORPUS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
