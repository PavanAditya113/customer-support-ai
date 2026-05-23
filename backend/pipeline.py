import pandas as pd
import numpy as np
import hashlib
import sys
import os
from datetime import datetime
from sqlalchemy.orm import Session

sys.path.append(os.path.dirname(__file__))
from database import SessionLocal, engine
from models import Base, TicketRaw, TicketEnriched
from llm import analyze_ticket


def init_db():
    Base.metadata.create_all(bind=engine)
    print("Database tables created.")


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    # Hash PII if raw email present
    if 'customer_email' in df.columns:
        df['customer_id'] = df['customer_email'].apply(
            lambda x: hashlib.md5(str(x).encode()).hexdigest()[:12]
        )
        df.drop(columns=['customer_name', 'customer_email'], inplace=True, errors='ignore')

    # Synthetic order_value if missing
    if 'order_value' not in df.columns:
        np.random.seed(42)
        df['order_value'] = np.round(np.random.uniform(10, 500, size=len(df)), 2)

    # Boolean conversion
    for col in ['sla_breached', 'escalated']:
        if df[col].dtype == object:
            df[col] = df[col].map({'Yes': True, 'No': False})

    # Date parsing
    for col in ['ticket_created_date', 'ticket_resolved_date']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    # Drop low-value columns
    drop_cols = ['browser', 'preferred_contact_time', 'customer_age',
                 'customer_gender', 'operating_system', 'payment_method']
    df.drop(columns=drop_cols, inplace=True, errors='ignore')

    # Ensure ticket_id is string
    df['ticket_id'] = df['ticket_id'].astype(str)

    return df


def load_to_db(df: pd.DataFrame, db: Session) -> int:
    loaded = 0
    for _, row in df.iterrows():
        existing = db.query(TicketRaw).filter_by(ticket_id=str(row['ticket_id'])).first()
        if existing:
            continue

        ticket = TicketRaw(
            ticket_id                   = str(row['ticket_id']),
            customer_id                 = str(row.get('customer_id', '')),
            ticket_created_date         = row.get('ticket_created_date'),
            ticket_resolved_date        = row.get('ticket_resolved_date'),
            channel                     = str(row.get('channel', '')),
            issue_description           = str(row.get('issue_description', '')),
            resolution_notes            = str(row.get('resolution_notes', '')),
            category                    = str(row.get('category', '')),
            priority                    = str(row.get('priority', '')),
            status                      = str(row.get('status', '')),
            product                     = str(row.get('product', '')),
            region                      = str(row.get('region', '')),
            subscription_type           = str(row.get('subscription_type', '')),
            customer_segment            = str(row.get('customer_segment', '')),
            customer_tenure_months      = int(row.get('customer_tenure_months', 0)),
            previous_tickets            = int(row.get('previous_tickets', 0)),
            customer_satisfaction_score = int(row.get('customer_satisfaction_score', 0)),
            first_response_time_hours   = float(row.get('first_response_time_hours', 0)),
            resolution_time_hours       = float(row.get('resolution_time_hours', 0)),
            sla_breached                = bool(row.get('sla_breached', False)),
            escalated                   = bool(row.get('escalated', False)),
            language                    = str(row.get('language', 'English')),
            issue_complexity_score      = int(row.get('issue_complexity_score', 0)),
            order_value                 = float(row.get('order_value', 0)),
        )
        db.add(ticket)
        loaded += 1

    db.commit()
    return loaded


def enrich_tickets(db: Session, batch_size: int = 50, limit: int = None):
    query = (
        db.query(TicketRaw)
        .outerjoin(TicketEnriched)
        .filter(TicketEnriched.ticket_id == None)
    )
    if limit:
        query = query.limit(limit)

    tickets = query.all()
    total = len(tickets)
    print(f"Enriching {total} tickets with LLM...")

    for i, ticket in enumerate(tickets):
        result = analyze_ticket(ticket.issue_description)
        enriched = TicketEnriched(
            ticket_id          = ticket.ticket_id,
            sentiment          = result.get("sentiment", "neutral"),
            frustration_level  = result.get("frustration_level", 5),
            issue_summary      = result.get("issue_summary", ""),
            suggested_response = result.get("suggested_response", ""),
            processed_at       = datetime.utcnow()
        )
        db.add(enriched)

        if (i + 1) % batch_size == 0:
            db.commit()
            print(f"  Processed {i+1}/{total}")

    db.commit()
    print(f"Enrichment complete: {total} tickets processed.")


def run_full_pipeline(csv_path: str, enrich: bool = True, enrich_limit: int = 200):
    print("=== PIPELINE START ===")
    init_db()

    print("Step 1: Loading and cleaning CSV...")
    df = pd.read_csv(csv_path, nrows=10000)
    df = clean_dataframe(df)

    print("Step 2: Loading to database...")
    db = SessionLocal()
    loaded = load_to_db(df, db)
    print(f"  Loaded {loaded} new tickets.")

    if enrich:
        print("Step 3: LLM enrichment...")
        enrich_tickets(db, limit=enrich_limit)

    db.close()
    print("=== PIPELINE COMPLETE ===")


if __name__ == "__main__":
    csv_path = r"C:\Users\venka\Downloads\archive\customer_support_tickets_200k.csv"
    run_full_pipeline(csv_path, enrich=True, enrich_limit=200)
