import re

def chunk_text(text, target_chars=800, overlap_chars=150):
    """Split text into overlapping, sentence-aware chunks for embedding."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    chunks, cur = [], ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(cur) + len(p) + 1 <= target_chars:
            cur = (cur + " " + p).strip()
        else:
            if cur:
                chunks.append(cur)
            tail = cur[-overlap_chars:] if cur else ""
            cur = (tail + " " + p).strip()
    if cur:
        chunks.append(cur)
    return chunks