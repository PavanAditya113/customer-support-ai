import os
import sys
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
import io

sys.path.append(os.path.dirname(__file__))
from database import get_db, engine
from models import Base, TicketRaw, TicketEnriched
from llm import analyze_ticket
from pipeline import clean_dataframe, load_to_db, enrich_tickets
from rag import build_knowledge_base, rag_answer
from anomaly import detect_spikes, get_trend_summary
from multilingual import handle_multilingual_ticket, get_language_distribution
from cost_optimizer import optimized_analyze, get_cost_stats

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Customer Support Insight Platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request Models ──────────────────────────────────────────
class SingleTicket(BaseModel):
    issue_description: str
    channel: str = "Web Form"
    product: str = "Unknown"


# ── Upload CSV ──────────────────────────────────────────────
@app.post("/tickets/upload")
async def upload_tickets(file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    df = pd.read_csv(io.BytesIO(contents))
    df = clean_dataframe(df)
    loaded = load_to_db(df, db)
    return {"message": f"Uploaded {loaded} new tickets", "total_rows": len(df)}


# ── Analyze Single Ticket ───────────────────────────────────
@app.post("/tickets/analyze")
def analyze_single(ticket: SingleTicket, db: Session = Depends(get_db)):
    result = analyze_ticket(ticket.issue_description)
    return {
        "issue_description": ticket.issue_description,
        "sentiment":          result.get("sentiment"),
        "frustration_level":  result.get("frustration_level"),
        "issue_summary":      result.get("issue_summary"),
        "suggested_response": result.get("suggested_response"),
    }


# ── Run Enrichment in Background ────────────────────────────
@app.post("/pipeline/enrich")
def trigger_enrichment(background_tasks: BackgroundTasks, limit: int = 100, db: Session = Depends(get_db)):
    background_tasks.add_task(enrich_tickets, db, limit=limit)
    return {"message": f"Enrichment started for up to {limit} tickets"}


# ── Top Issues ──────────────────────────────────────────────
@app.get("/insights/top-issues")
def top_issues(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT category, COUNT(*) as count,
               AVG(order_value) as avg_order_value,
               SUM(CASE WHEN sla_breached THEN 1 ELSE 0 END) as sla_breached_count
        FROM tickets_raw
        GROUP BY category
        ORDER BY count DESC
        LIMIT 10
    """)).fetchall()
    return [{"category": r[0], "count": r[1],
             "avg_order_value": round(r[2], 2),
             "sla_breached_count": r[3]} for r in rows]


# ── Sentiment Trend ─────────────────────────────────────────
@app.get("/insights/sentiment-trend")
def sentiment_trend(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT strftime('%Y-%m', t.ticket_created_date) as month,
               e.sentiment, COUNT(*) as count
        FROM tickets_raw t
        JOIN tickets_enriched e ON t.ticket_id = e.ticket_id
        WHERE t.ticket_created_date IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 1
    """)).fetchall()
    return [{"month": str(r[0]), "sentiment": r[1], "count": r[2]} for r in rows]


# ── SLA Stats ───────────────────────────────────────────────
@app.get("/insights/sla-stats")
def sla_stats(db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN sla_breached THEN 1 ELSE 0 END) as breached,
            SUM(CASE WHEN escalated THEN 1 ELSE 0 END) as escalated,
            AVG(resolution_time_hours) as avg_resolution_hours,
            AVG(first_response_time_hours) as avg_first_response_hours
        FROM tickets_raw
    """)).fetchone()
    total = row[0] or 1
    return {
        "total_tickets":          row[0],
        "sla_breached":           row[1],
        "sla_breach_rate":        round(row[1] / total * 100, 1),
        "escalated":              row[2],
        "escalation_rate":        round(row[2] / total * 100, 1),
        "avg_resolution_hours":   round(row[3], 1),
        "avg_first_response_hours": round(row[4], 1),
    }


# ── Ticket with Suggested Response ─────────────────────────
@app.get("/tickets/{ticket_id}/response")
def get_ticket_response(ticket_id: str, db: Session = Depends(get_db)):
    ticket = db.query(TicketRaw).filter_by(ticket_id=ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    enriched = db.query(TicketEnriched).filter_by(ticket_id=ticket_id).first()
    return {
        "ticket_id":          ticket.ticket_id,
        "issue_description":  ticket.issue_description,
        "category":           ticket.category,
        "priority":           ticket.priority,
        "sentiment":          enriched.sentiment if enriched else None,
        "frustration_level":  enriched.frustration_level if enriched else None,
        "issue_summary":      enriched.issue_summary if enriched else None,
        "suggested_response": enriched.suggested_response if enriched else None,
    }


# ── All Tickets (paginated) ─────────────────────────────────
@app.get("/tickets")
def list_tickets(skip: int = 0, limit: int = 50,
                 category: str = None, sentiment: str = None,
                 db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT t.ticket_id, t.category, t.priority, t.channel,
               t.status, t.order_value, t.ticket_created_date,
               t.sla_breached, t.escalated,
               e.sentiment, e.frustration_level, e.issue_summary, e.suggested_response,
               t.issue_description
        FROM tickets_raw t
        LEFT JOIN tickets_enriched e ON t.ticket_id = e.ticket_id
        WHERE (:category IS NULL OR t.category = :category)
          AND (:sentiment IS NULL OR e.sentiment = :sentiment)
        ORDER BY t.ticket_created_date DESC
        LIMIT :limit OFFSET :skip
    """), {"category": category, "sentiment": sentiment,
           "limit": limit, "skip": skip}).fetchall()

    return [{
        "ticket_id": r[0], "category": r[1], "priority": r[2],
        "channel": r[3], "status": r[4], "order_value": r[5],
        "created_at": str(r[6]), "sla_breached": r[7], "escalated": r[8],
        "sentiment": r[9], "frustration_level": r[10],
        "issue_summary": r[11], "suggested_response": r[12],
        "issue_description": r[13]
    } for r in rows]


# ── Channel Breakdown ───────────────────────────────────────
@app.get("/insights/by-channel")
def by_channel(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT channel, COUNT(*) as count,
               AVG(customer_satisfaction_score) as avg_satisfaction
        FROM tickets_raw
        GROUP BY channel ORDER BY count DESC
    """)).fetchall()
    return [{"channel": r[0], "count": r[1],
             "avg_satisfaction": round(r[2], 2)} for r in rows]


# ── Revenue at Risk ─────────────────────────────────────────
@app.get("/insights/revenue-at-risk")
def revenue_at_risk(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT t.category,
               SUM(t.order_value) as total_order_value,
               COUNT(*) as ticket_count
        FROM tickets_raw t
        JOIN tickets_enriched e ON t.ticket_id = e.ticket_id
        WHERE e.sentiment = 'negative'
        GROUP BY t.category
        ORDER BY total_order_value DESC
    """)).fetchall()
    return [{"category": r[0],
             "revenue_at_risk": round(r[1], 2),
             "negative_tickets": r[2]} for r in rows]


@app.get("/")
def root():
    return {"status": "ok", "message": "Customer Support Insight Platform API"}


# ── BONUS 1: RAG Knowledge Assistant ───────────────────────
@app.post("/tickets/rag-analyze")
def rag_analyze(ticket: SingleTicket, db: Session = Depends(get_db)):
    build_knowledge_base(db)
    result = rag_answer(ticket.issue_description)
    return result


# ── BONUS 2: Anomaly Detection ──────────────────────────────
@app.get("/insights/anomalies")
def anomalies(threshold: float = 1.5, db: Session = Depends(get_db)):
    return detect_spikes(db, z_threshold=threshold)


@app.get("/insights/trends")
def trends(db: Session = Depends(get_db)):
    return get_trend_summary(db)


# ── BONUS 3: Multilingual ───────────────────────────────────
@app.post("/tickets/multilingual-analyze")
def multilingual_analyze(ticket: SingleTicket):
    return handle_multilingual_ticket(ticket.issue_description)


@app.get("/insights/language-dist")
def language_distribution(db: Session = Depends(get_db)):
    return get_language_distribution(db)


# ── BONUS 4: Cost Optimization ──────────────────────────────
@app.post("/tickets/optimized-analyze")
def optimized_analyze_endpoint(ticket: SingleTicket):
    return optimized_analyze(ticket.issue_description)


@app.get("/insights/cost-stats")
def cost_statistics(db: Session = Depends(get_db)):
    return get_cost_stats(db)
