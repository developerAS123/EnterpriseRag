"""
Ingest sample IT support documentation into Pinecone.

Usage:
    python ingest_sample_kb.py
"""

import sys
from pathlib import Path
from app.core.config import get_settings
from app.services.ingestion import load_file, chunk_documents
from app.rag.vectorstore import add_documents


def main():
    settings = get_settings()
    folder = Path(settings.sample_kb_dir)
    if not folder.exists():
        print(f"Sample KB directory '{folder}' not found.")
        sys.exit(1)

    files = sorted([p for p in folder.iterdir() if p.is_file()])
    if not files:
        print(f"No files found in '{folder}'.")
        return

    print(f"Found {len(files)} files to index from {folder}:")
    for f in files:
        print(f"  - {f.name}")

    all_docs = []
    for path in files:
        docs = load_file(path)
        for doc in docs:
            doc.metadata["source"] = path.name
            doc.metadata["file_type"] = path.suffix.lstrip(".")
        all_docs.extend(docs)

    chunks = chunk_documents(all_docs)
    print(f"Generated {len(chunks)} chunks across {len(files)} documents.")

    print(f"Connecting to Pinecone index '{settings.pinecone_index_name}' (namespace: '{settings.pinecone_namespace}')...")
    ids = add_documents(chunks)
    print(f"Successfully indexed {len(files)} files -> {len(chunks)} chunks -> {len(ids)} Pinecone vectors.")


if __name__ == "__main__":
    main()
