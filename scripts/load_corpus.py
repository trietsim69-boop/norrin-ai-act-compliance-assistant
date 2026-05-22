"""
One-shot script to load the EU AI Act corpus into Chroma.

Run from the project root:
    python -m scripts.load_corpus

Reads every supported file in corpus/, converts to Markdown via MarkItDown,
chunks it, embeds it (locally if EMBEDDING_PROVIDER=local), and stores it
in the ai_act_corpus_collection.

Safe to re-run — it skips if the collection is already populated.
Pass --force to wipe and reload:
    python -m scripts.load_corpus --force
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.vector_store import load_corpus_to_chroma, get_corpus_collection


def main() -> int:
    force = "--force" in sys.argv

    print(f"Loading corpus (force_reload={force})...")
    count = load_corpus_to_chroma(force_reload=force, verbose=True)

    total = get_corpus_collection().count()
    print(f"\nDone. Corpus collection now contains {total} chunk(s).")
    print(f"({count} chunk(s) processed in this run.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
