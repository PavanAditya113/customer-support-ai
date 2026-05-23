#!/bin/bash
set -e

echo "=== Customer Support AI — Startup ==="

# Initialize DB and load tickets if empty
python -c "
import sys, os
sys.path.insert(0, '.')
from database import SessionLocal, engine
from models import Base, TicketRaw

print('Creating database tables...')
Base.metadata.create_all(bind=engine)

db = SessionLocal()
count = db.query(TicketRaw).count()
db.close()
print(f'Tickets in database: {count}')

if count == 0:
    print('Database empty — loading tickets from CSV...')
    from pipeline import run_full_pipeline
    run_full_pipeline('/app/data/tickets_clean.csv', enrich=False)
    print('Tickets loaded successfully.')
else:
    print('Database already populated — skipping load.')
"

echo "Starting FastAPI on port 8001..."
exec uvicorn main:app --host 0.0.0.0 --port 8001
