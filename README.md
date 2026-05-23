# AI-Powered Customer Support Insight Platform

> Built for: AI/ML Enabled Software Dev Assignment
> Stack: FastAPI · SQLite · Streamlit · OpenRouter (GPT-4o-mini)
> Dataset: 10,000 customer support tickets (200K available)

---

## What It Does

A mid-sized e-commerce company receives thousands of support tickets daily.
This system automatically:

- **Categorizes** tickets into 10 problem categories
- **Detects** sentiment and frustration level (1-10)
- **Extracts** top recurring issues for leadership
- **Generates** suggested responses for support agents
- **Visualizes** trends, SLA breaches, escalation rates on a live dashboard

### Bonus Features (All Implemented)
- **RAG Knowledge Assistant** — answers grounded in past resolved tickets
- **Anomaly Detection** — Z-score spike detection per category
- **Multilingual Handling** — detect, translate, classify, respond in customer language
- **Cost Optimization** — caching + smart routing, $0.000045/ticket
- **Automated Weekly Report** — terminal report with leadership insights

---

## Architecture

```
                        +─────────────────────+
  Raw CSV / New Ticket  |                     |
  ──────────────────►  |   Data Pipeline      |
                        |   (pipeline.py)      |
                        |                     |
                        |  1. Clean (PII hash)|
                        |  2. Enrich metadata |
                        |  3. AI Analysis     |
                        +────────+────────────+
                                 |
                    +────────────v────────────+
                    |      SQLite Database     |
                    |  tickets_raw            |
                    |  tickets_enriched       |
                    +────────────+────────────+
                                 |
                  +──────────────v──────────────+
                  |        FastAPI Backend        |
                  |     (localhost:8001)          |
                  |                              |
                  |  Core Endpoints:             |
                  |  POST /tickets/upload        |
                  |  POST /tickets/analyze       |
                  |  GET  /insights/top-issues   |
                  |  GET  /insights/sentiment    |
                  |  GET  /insights/sla-stats    |
                  |  GET  /insights/revenue      |
                  |                              |
                  |  Bonus Endpoints:            |
                  |  POST /tickets/rag-analyze   |
                  |  POST /tickets/multilingual  |
                  |  POST /tickets/optimized     |
                  |  GET  /insights/anomalies    |
                  |  GET  /insights/trends       |
                  |  GET  /insights/cost-stats   |
                  |  GET  /insights/language-dist|
                  +──────────────+──────────────+
                                 |
                  +──────────────v──────────────+
                  |     Streamlit Dashboard       |
                  |     (localhost:8501)          |
                  |                              |
                  |  KPI Cards (5 metrics)       |
                  |  Top Issues Bar Chart        |
                  |  Sentiment Trend Line Chart  |
                  |  SLA + Escalation Gauges     |
                  |  Revenue at Risk Chart       |
                  |  Channel Breakdown           |
                  |  Ticket Explorer             |
                  +─────────────────────────────+

                  +─────────────────────────────+
                  |     OpenRouter API            |
                  |     Model: gpt-4o-mini        |
                  |                              |
                  |  Input:  issue_description   |
                  |  Output: sentiment           |
                  |          frustration_level   |
                  |          issue_summary       |
                  |          suggested_response  |
                  +─────────────────────────────+
```

---

## Project Structure

```
customer-support-ai/
├── backend/
│   ├── main.py              # FastAPI — 13 endpoints
│   ├── pipeline.py          # ETL pipeline (clean → enrich → store)
│   ├── llm.py               # OpenRouter LLM integration
│   ├── models.py            # SQLAlchemy DB models
│   ├── database.py          # DB connection (SQLite)
│   ├── rag.py               # BONUS: RAG knowledge assistant
│   ├── anomaly.py           # BONUS: Anomaly detection
│   ├── multilingual.py      # BONUS: Multilingual ticket handling
│   ├── cost_optimizer.py    # BONUS: Cost optimization + caching
│   ├── weekly_report.py     # BONUS: Automated weekly report
│   ├── audit.py             # Terminal audit system (8 checks)
│   └── test_accuracy.py     # 7-test accuracy suite
├── frontend/
│   └── dashboard.py         # Streamlit dashboard
├── data/
│   └── tickets_clean.csv    # Cleaned dataset sample
├── docs/
│   ├── README.md
│   ├── design_document.md
│   ├── business_report.md
│   ├── implementation_guide.md
│   └── architecture.png
├── .github/workflows/ci.yml # GitHub Actions CI/CD
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
├── requirements.txt
└── .env
```

---

## Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/yourusername/customer-support-ai
cd customer-support-ai
pip install -r requirements.txt
```

### 2. Configure
```bash
# Edit .env
OPENROUTER_API_KEY=your_key_here
DATABASE_URL=sqlite:///./support.db
```

### 3. Run Pipeline (loads 10K tickets + LLM enrichment)
```bash
cd backend
python pipeline.py
```

### 4. Start API
```bash
cd backend
uvicorn main:app --reload --port 8001
```

### 5. Start Dashboard
```bash
cd frontend
streamlit run dashboard.py
```

### 6. Run Terminal Audit (verify everything)
```bash
cd backend
python -X utf8 audit.py
```

### 7. Open Browser
- Dashboard → http://localhost:8501
- API Docs  → http://localhost:8001/docs

---

## API Reference

### Core Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tickets/upload` | Upload CSV of tickets |
| POST | `/tickets/analyze` | Analyze single ticket with LLM |
| POST | `/pipeline/enrich` | Trigger background LLM enrichment |
| GET  | `/tickets` | List tickets (filterable by category/sentiment) |
| GET  | `/tickets/{id}/response` | Get AI suggested response |
| GET  | `/insights/top-issues` | Category frequency + revenue impact |
| GET  | `/insights/sentiment-trend` | Sentiment over time |
| GET  | `/insights/sla-stats` | SLA + escalation rates |
| GET  | `/insights/by-channel` | Breakdown by channel |
| GET  | `/insights/revenue-at-risk` | Negative sentiment x order value |

### Bonus Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tickets/rag-analyze` | RAG-grounded response using past resolutions |
| POST | `/tickets/multilingual-analyze` | Auto-detect language + classify + respond |
| POST | `/tickets/optimized-analyze` | Cached + smart-routed LLM call |
| GET  | `/insights/anomalies` | Z-score spike detection per category |
| GET  | `/insights/trends` | Week-over-week category trends |
| GET  | `/insights/cost-stats` | LLM usage + cost tracking |
| GET  | `/insights/language-dist` | Ticket distribution by language |

---

## Audit Results (Latest Run)

```
Audit                      Result   Detail
────────────────────────────────────────────────────────
API Health Check           PASS     10/10 endpoints healthy
Database Integrity         PASS     10K tickets, 0 nulls
LLM Integration            PASS     6/6 test cases, 2.7s avg
RAG Knowledge Assistant    PASS     2000 tickets indexed
Anomaly Detection          PASS     505 spikes detected
Multilingual Handling      PASS     4/4 languages (EN/FR/ES/DE)
Cost Optimization          PASS     50% cache hit rate, $0.0135 total
Weekly Report Generation   PASS     Full report generated

Overall: 8/8 (100%) — EXCELLENT
```

Run audit:
```bash
cd backend
python -X utf8 audit.py
```

---

## Accuracy Test Results

```
Test                        Score     Status
────────────────────────────────────────────
LLM Success Rate            100%      PASS
Edge Case Handling          100%      PASS
Avg Latency                 2.27s     PASS
Regression Consistency      100%      PASS
Frustration Sanity          100%      PASS
Overall                     5/7       GOOD
```

Run tests:
```bash
cd backend
python -X utf8 test_accuracy.py
```

---

## Dataset

- Source: Kaggle — Customer Support Tickets (200K rows)
- Used: Top 10,000 rows
- Cleaned: PII hashed, synthetic order_value added ($10-$500)
- Enriched: 300 tickets processed with LLM (sentiment + response)

| Column | Description | Used For |
|--------|-------------|----------|
| issue_description | Raw ticket text | LLM input |
| category | 10 categories (ground truth) | Charts + validation |
| priority | Urgent/High/Medium/Low | Routing |
| sla_breached | Boolean | SLA gauge |
| escalated | Boolean | Escalation gauge |
| order_value | Revenue impact (synthetic) | Revenue at risk |
| customer_satisfaction_score | 1-5 rating | Satisfaction KPI |
| channel | Email/Chat/Web/Phone/Social | Channel breakdown |
| ticket_created_date | Timestamp | Trend charts |
| resolution_time_hours | Hours to resolve | Resolution KPI |

---

## Bonus Features

### RAG Knowledge Assistant
```bash
curl -X POST http://localhost:8001/tickets/rag-analyze \
  -H "Content-Type: application/json" \
  -d '{"issue_description": "I was charged twice this month"}'
```

### Anomaly Detection
```bash
curl http://localhost:8001/insights/anomalies?threshold=2.0
```

### Multilingual
```bash
curl -X POST http://localhost:8001/tickets/multilingual-analyze \
  -H "Content-Type: application/json" \
  -d '{"issue_description": "Mon paiement a echoue"}'
```

### Weekly Report
```bash
cd backend && python -X utf8 weekly_report.py
```

---

## Cost Analysis

| Scale | Tickets | Estimated Cost |
|-------|---------|----------------|
| Demo | 300 | $0.0135 |
| Small | 10,000 | $0.45 |
| Medium | 100,000 | $4.50 |
| Large | 1,000,000 | $45.00 |

Model: GPT-4o-mini @ $0.15 per 1M tokens, ~300 tokens/ticket

---

## Docker Deployment

```bash
# Set your API key in .env first
docker-compose up --build
```

Services:
- `db`       → PostgreSQL on port 5432
- `backend`  → FastAPI on port 8001
- `frontend` → Streamlit on port 8501
