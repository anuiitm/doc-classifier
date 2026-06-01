import sys, os, glob, chromadb
from sentence_transformers import SentenceTransformer
from engine.extractor import text_candidates
from engine import classify_file
from rag_chunk import chunk_text
from engine.model import init_db, get_session, DocumentChunk, DetailedDocumentType

MODEL = SentenceTransformer("all-MiniLM-L6-v2")
KEEP = {"BANK_STATEMENT", "INVOICE", "ROAD_TAX", "INSURANCE"}

def best_text(p):
    best = ""
    for t, m in text_candidates(p):
        if m == "text-layer": return t
        if len(t) > len(best): best = t
    return best

def main(folder, customer_id="CUST-0001"):
    init_db(); db = get_session()
    col = chromadb.PersistentClient(path="rag_store").get_or_create_collection(
        "ltf_docs", metadata={"hnsw:space": "cosine"})

    for path in sorted(glob.glob(os.path.join(folder, "*"))):
        name = os.path.basename(path)
        dtype = classify_file(path).get("decision", "UNKNOWN")
        if dtype not in KEEP:
            print(f"  skip {name} [{dtype}]"); continue
        chunks = chunk_text(best_text(path))
        if not chunks: continue
        embs = MODEL.encode(chunks).tolist()
        ids = [f"{name}::chunk{i}" for i in range(len(chunks))]
        col.upsert(ids=ids, embeddings=embs, documents=chunks,
                   metadatas=[{"source": name, "doc_type": dtype, "chunk": i}
                              for i in range(len(chunks))])
        for cid, txt in zip(ids, chunks):
            db.merge(DocumentChunk(chunk_id=cid, customer_id=customer_id,
                     document_type=DetailedDocumentType(dtype),
                     source_file=name, chunk_text=txt))
        db.commit()
        print(f"  indexed {name} [{dtype}] {len(chunks)} chunks")
    db.close()

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "mydocs")