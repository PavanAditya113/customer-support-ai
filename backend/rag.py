"""
BONUS 1 — RAG-Based Knowledge Assistant
Retrieves similar past resolutions and uses them to generate grounded answers.
"""

import os
import sys
sys.path.append(os.path.dirname(__file__))

from database import SessionLocal
from models import TicketRaw, TicketEnriched
from llm import analyze_ticket
import httpx

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
API_URL = "https://openrouter.ai/api/v1/chat/completions"

# ── In-memory vector store (no external DB needed) ───────────
# Uses simple TF-IDF similarity for demo (no GPU required)
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import json

_vectorizer = None
_matrix     = None
_documents  = []
_built      = False


def build_knowledge_base(db=None):
    """Build TF-IDF index from all resolved tickets in DB."""
    global _vectorizer, _matrix, _documents, _built

    if db is None:
        db = SessionLocal()
        close_after = True
    else:
        close_after = False

    try:
        tickets = (
            db.query(TicketRaw)
            .filter(TicketRaw.status.in_(["Closed", "Resolved"]))
            .limit(2000)
            .all()
        )

        if not tickets:
            print("  No resolved tickets found for RAG knowledge base.")
            return False

        _documents = []
        for t in tickets:
            _documents.append({
                "ticket_id":        t.ticket_id,
                "issue_description": t.issue_description,
                "resolution_notes":  t.resolution_notes,
                "category":          t.category,
                "priority":          t.priority,
            })

        texts = [d["issue_description"] for d in _documents]
        _vectorizer = TfidfVectorizer(max_features=5000, stop_words="english")
        _matrix     = _vectorizer.fit_transform(texts)
        _built      = True

        print(f"  RAG knowledge base built: {len(_documents)} resolved tickets indexed.")
        return True

    finally:
        if close_after:
            db.close()


def find_similar_tickets(query: str, top_k: int = 3) -> list:
    """Find top-k most similar past tickets to the query."""
    global _vectorizer, _matrix, _documents, _built

    if not _built:
        build_knowledge_base()

    if not _built or _vectorizer is None:
        return []

    query_vec    = _vectorizer.transform([query])
    similarities = cosine_similarity(query_vec, _matrix).flatten()
    top_indices  = similarities.argsort()[-top_k:][::-1]

    results = []
    for idx in top_indices:
        if similarities[idx] > 0.1:  # minimum similarity threshold
            doc = _documents[idx].copy()
            doc["similarity_score"] = round(float(similarities[idx]), 3)
            results.append(doc)

    return results


def rag_answer(query: str) -> dict:
    """Generate a grounded answer using RAG."""
    similar = find_similar_tickets(query, top_k=3)

    if not similar:
        # Fallback to standard LLM
        result = analyze_ticket(query)
        result["rag_used"]    = False
        result["similar_tickets"] = []
        return result

    # Build context from past resolutions
    context_parts = []
    for i, s in enumerate(similar, 1):
        context_parts.append(
            f"Past Case {i} (similarity: {s['similarity_score']}):\n"
            f"  Issue: {s['issue_description'][:100]}\n"
            f"  Resolution: {s['resolution_notes'][:150]}\n"
            f"  Category: {s['category']}"
        )
    context = "\n\n".join(context_parts)

    prompt = f"""You are a customer support agent assistant.

Based on these similar past resolved cases from our knowledge base:

{context}

Now handle this new ticket:
"{query}"

Return ONLY valid JSON:
{{
  "sentiment": "positive" or "negative" or "neutral",
  "frustration_level": integer 1-10,
  "issue_summary": "one sentence describing the core problem",
  "suggested_response": "professional agent reply under 80 words, informed by past resolutions"
}}"""

    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        response = httpx.post(API_URL, json=payload, headers=headers, timeout=30)
        content  = response.json()["choices"][0]["message"]["content"].strip()

        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        import json
        result = json.loads(content)
        result["rag_used"]        = True
        result["similar_tickets"] = similar
        return result

    except Exception as e:
        result = analyze_ticket(query)
        result["rag_used"]        = False
        result["similar_tickets"] = similar
        return result
