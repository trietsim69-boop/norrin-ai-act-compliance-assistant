import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Root paths ---
ROOT_DIR = Path(__file__).parent.parent

# --- LLM ---
# Provider used by the agents: "deepseek" | "openai" | "anthropic"
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "deepseek")
LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")

# API keys
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")

# Optional override for OpenAI-compatible endpoints (e.g. DeepSeek, Together, OpenRouter).
# When empty, the default provider URL is used.
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")

# When MOCK_LLM=true, src.llm.call_llm() returns fixture responses instead of
# calling the real API. Useful for offline development and demo fallback.
MOCK_LLM: bool = os.getenv("MOCK_LLM", "true").lower() in ("1", "true", "yes", "on")

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
MAX_UPLOADED_CONTEXT_CHUNKS: int = int(os.getenv("MAX_UPLOADED_CONTEXT_CHUNKS", "40"))
MAX_CORPUS_CONTEXT_CHUNKS: int = int(os.getenv("MAX_CORPUS_CONTEXT_CHUNKS", "48"))

# --- Ensure directories exist at import time ---
for _dir in (UPLOAD_DIR, CONVERTED_MD_DIR, VECTOR_STORE_DIR, OUTPUTS_DIR, CORPUS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
