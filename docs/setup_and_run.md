# Setup and run

Developer and teammate guide — Windows PowerShell from repository root.

---

## Prerequisites

- Python **3.11+** (tested on 3.13)  
- Git  
- ~2 GB disk for embeddings / Chroma (first run downloads SentenceTransformers model)  

---

## 1. Virtual environment

```powershell
cd norrin-ai-act-compliance-assistant
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 2. Environment variables

```powershell
copy .env.example .env
```

Edit `.env` locally — **never commit it**.

Example (placeholders only):

```env
EMBEDDING_PROVIDER=local
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat
MOCK_LLM=true
DEEPSEEK_API_KEY=your_key_here
```

| Variable | Notes |
|----------|-------|
| `MOCK_LLM=true` | Offline fixtures — **recommended for first run and demos** |
| `MOCK_LLM=false` | Live API — requires key for chosen `LLM_PROVIDER` |
| `EMBEDDING_PROVIDER=local` | No API key; uses SentenceTransformers |
| `EMBEDDING_PROVIDER=openai` | Requires `OPENAI_API_KEY` |
| `LLM_PROVIDER` | `deepseek` (default), `openai`, `anthropic` |

**Shell override:** If `$env:MOCK_LLM` is already set in PowerShell, it **wins over** `.env`:

```powershell
$env:MOCK_LLM = "false"
$env:DEEPSEEK_API_KEY = "your_key_here"
```

DeepSeek uses OpenAI-compatible API; default base URL is automatic.

---

## 3. Load the legal corpus (once)

```powershell
python -m scripts.load_corpus
```

This will:

1. Read files from `corpus/`  
2. Convert via MarkItDown (cache under `data/converted_markdown/_corpus/`)  
3. Chunk and enrich metadata  
4. Embed and store in Chroma `ai_act_corpus_collection`  

Expect **~1,874 chunks** when successful.

Force reload after corpus changes:

```powershell
python -m scripts.load_corpus --force
```

---

## 4. Run the Streamlit app

```powershell
streamlit run app.py
```

Recommended local dev:

```powershell
streamlit run app.py --server.port 8521 --server.fileWatcherType none
```

Open the URL printed in the terminal (e.g. http://localhost:8521).

---

## 5. Run trigger tests (optional)

```powershell
python -m scripts.run_trigger_tests
python -m scripts.run_trigger_tests --case hr_screening --verbose
python -m scripts.run_trigger_tests --real-llm
```

Requires corpus loaded. Mock mode: target **5/5 pass**.

Details: [`evaluation_and_trigger_tests.md`](evaluation_and_trigger_tests.md)

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Empty corpus / no legal citations | Run `python -m scripts.load_corpus` |
| Still in mock mode with key set | Check `$env:MOCK_LLM`; set `false` explicitly |
| Slow first embedding | SentenceTransformers model download on first query |
| Port in use | `streamlit run app.py --server.port 8522` |
| Chroma stale after code change | New session via **New case** or delete `data/vector_store/` and reload corpus |

---

## Project commands reference

| Task | Command |
|------|---------|
| Install deps | `pip install -r requirements.txt` |
| Load corpus | `python -m scripts.load_corpus` |
| Run UI | `streamlit run app.py` |
| Trigger tests | `python -m scripts.run_trigger_tests` |

---

## Related docs

- Architecture: [`architecture.md`](architecture.md)  
- Demo script: [`demo_guide.md`](demo_guide.md)  
- README: [`../README.md`](../README.md)  
