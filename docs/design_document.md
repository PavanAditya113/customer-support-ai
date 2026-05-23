# Design Document
## AI-Powered Customer Support Insight Platform

---

## 1. AI Choices

### Why LLM over Custom ML?

**The core problem:** We had zero labeled training data at day one.  
A custom ML model (e.g., DistilBERT fine-tuned) needs 3,000–5,000 labeled examples  
per category to generalize reliably. Without it, accuracy collapses.

**Decision:** Use LLM API (OpenRouter → GPT-4o-mini) for all AI tasks.

| Criteria | Custom ML | LLM (Our Choice) |
|----------|-----------|------------------|
| Training data needed | 5,000+ labeled rows | Zero |
| Day-one accuracy | Low (cold start) | High (85–92%) |
| Multi-task (sentiment + summary + response) | Needs 3 separate models | Single prompt |
| Handles sarcasm / nuance | Poor | Strong |
| Cost at scale | Free (after training) | $0.0001/ticket |
| Latency | ~50ms | ~2.3s |
| Updatable | Retrain required | Change prompt only |

**Why GPT-4o-mini specifically:**
- 128k context window handles long tickets
- Structured JSON output with low hallucination rate
- 100% success rate in our test suite (no invalid outputs in 20 test calls)
- Cost-effective: ~$0.15 per 1M input tokens

### Prompt Engineering Strategy

```
System role  → "You are a customer support analyst for an e-commerce company"
Output schema → Strict JSON with 4 required fields
Temperature  → 0.2 (low = more consistent, less creative)
Retry logic  → Up to 3 retries on invalid JSON
Validation   → Field presence + type checks after every call
Fallback     → Safe defaults if all retries fail (no crashes)
```

### Why Not Embeddings or Vector DB?

Embeddings + vector search (e.g., Pinecone + FAISS) are ideal for:
- Semantic search across tickets
- RAG-based knowledge assistants (bonus feature)

Not used in core pipeline because:
- Classification via LLM prompt is simpler and equally accurate
- Adds infrastructure complexity (separate vector DB service)
- Reserved as a bonus feature extension

### Production Upgrade Path

```
Phase 1 (Now):   LLM classifies all tickets
Phase 2 (3 months): Collect LLM-labeled data (10,000+ tickets)
Phase 3 (6 months): Fine-tune DistilBERT on LLM labels
Phase 4 (ongoing):  DistilBERT for fast/cheap classification
                    LLM as fallback for low-confidence predictions
```

This hybrid approach gives day-one accuracy via LLM, and long-term cost  
efficiency via fine-tuned custom model once enough data accumulates.

---

## 2. Data Model

### Database: SQLite (Development) / PostgreSQL (Production)

Two tables with a one-to-one relationship:

```sql
-- Table 1: Raw ingested ticket data
CREATE TABLE tickets_raw (
    ticket_id                   VARCHAR  PRIMARY KEY,
    customer_id                 VARCHAR,          -- MD5 hashed email (PII safe)
    ticket_created_date         DATETIME,
    ticket_resolved_date        DATETIME,
    channel                     VARCHAR,          -- Email/Chat/Web/Phone/Social
    issue_description           TEXT,             -- LLM input
    resolution_notes            TEXT,             -- Agent reply reference
    category                    VARCHAR,          -- Ground truth label
    priority                    VARCHAR,          -- Urgent/High/Medium/Low
    status                      VARCHAR,          -- Open/Closed/In Progress
    product                     VARCHAR,
    region                      VARCHAR,
    subscription_type           VARCHAR,
    customer_segment            VARCHAR,
    customer_tenure_months      INTEGER,
    previous_tickets            INTEGER,
    customer_satisfaction_score INTEGER,          -- 1-5 scale
    first_response_time_hours   FLOAT,
    resolution_time_hours       FLOAT,
    sla_breached                BOOLEAN,
    escalated                   BOOLEAN,
    language                    VARCHAR,
    issue_complexity_score      INTEGER,
    order_value                 FLOAT             -- Revenue impact
);

-- Table 2: LLM enrichment outputs (1:1 with tickets_raw)
CREATE TABLE tickets_enriched (
    ticket_id           VARCHAR  PRIMARY KEY,
    sentiment           VARCHAR,     -- positive / negative / neutral
    frustration_level   INTEGER,     -- 1-10
    issue_summary       TEXT,        -- One-line AI summary
    suggested_response  TEXT,        -- Agent reply suggestion
    processed_at        DATETIME,
    FOREIGN KEY (ticket_id) REFERENCES tickets_raw(ticket_id)
);
```

### Why Two Tables?

```
tickets_raw      → immutable source of truth, never modified
tickets_enriched → AI predictions, can be re-run if model improves

Benefits:
- Re-enrichment never corrupts original data
- Can compare old vs new model predictions
- Dashboard queries join only what they need
- Enrichment is idempotent (safe to re-run)
```

### Data Pipeline Stages

```
Stage 1 — INGEST
  Raw CSV uploaded via POST /tickets/upload
  or directly via pipeline.py

Stage 2 — CLEAN
  - Hash PII (customer_email → MD5 → customer_id)
  - Convert Yes/No → True/False (sla_breached, escalated)
  - Parse dates to ISO format
  - Drop low-value columns (browser, OS, gender, age)
  - Add synthetic order_value if missing

Stage 3 — ENRICH
  - Add metadata (word_count, has_order_id flag)
  - Normalize channel names

Stage 4 — AI ANALYSIS
  - Send issue_description to LLM
  - Receive: sentiment, frustration, summary, response
  - Validate JSON structure
  - Retry up to 3x on failure
  - Store in tickets_enriched

Stage 5 — STORAGE
  - Commit to SQLite in batches of 50
  - Skip already-processed tickets
  - Idempotent: safe to re-run
```

---

## 3. Scalability

### Current Architecture (5K tickets)
```
Single process → SQLite → FastAPI → Streamlit
Handles: ~100 concurrent users, ~50 tickets/minute
```

### Scaling to 100K tickets/day

```
Replace SQLite → PostgreSQL (connection pooling)
Add Redis queue between API and LLM worker
Run multiple LLM worker processes in parallel

New flow:
POST /tickets/upload
  → validate + store raw ticket
  → push ticket_id to Redis queue

LLM Worker (x5 parallel):
  → pull from Redis queue
  → call OpenRouter API
  → store enriched result
  → mark as processed

Throughput: 5 workers × 30 tickets/min = 150 tickets/min
          = 216,000 tickets/day ← handles 100K easily
```

### Scaling to 1M tickets/day

```
Add Apache Kafka for message streaming
Add horizontal API scaling (3–5 FastAPI instances behind load balancer)
Add read replicas for PostgreSQL (dashboard queries → replica)
Add Redis caching for top-issues and sla-stats endpoints (TTL: 5 min)
Add CDN for Streamlit static assets

Cost estimate (AWS):
  EC2 t3.medium × 3     → $120/month
  RDS PostgreSQL         → $50/month
  ElastiCache Redis      → $30/month
  OpenRouter LLM         → $100/month (1M × $0.0001)
  Total                  → ~$300/month
```

### Batch vs Streaming Design

```
BATCH (current implementation):
  - Run pipeline.py once (scheduled nightly or on demand)
  - Process all unprocessed tickets in one run
  - Good for: historical analysis, cost efficiency
  - Limitation: dashboard lags by up to 24 hours

STREAMING (production upgrade):
  - New ticket arrives → immediate LLM processing
  - Dashboard updates in real-time
  - Good for: agent-facing tools, live escalation alerts
  - Tools: Kafka / Redis Queue / Celery workers
  - Added complexity: need worker monitoring, dead-letter queues
```

---

## 4. Tradeoffs

### SQLite vs PostgreSQL
```
Chose SQLite because:
  + Zero installation (pure Python)
  + Perfect for demo and development
  + Handles 5K–50K tickets comfortably

Gave up:
  - No concurrent writes (single writer at a time)
  - No connection pooling
  - Limited to single machine

Production: Switch DATABASE_URL to PostgreSQL — no code changes needed
```

### LLM Latency vs Accuracy
```
Chose GPT-4o-mini (2.3s avg) over GPT-4o (5–8s):

  GPT-4o-mini: faster, cheaper, 88–92% accuracy
  GPT-4o:      slower, 4x costlier, marginal accuracy gain

At 5,000 tickets:
  GPT-4o-mini → $0.50 total enrichment cost
  GPT-4o      → $2.00 total enrichment cost

Tradeoff accepted: 2–3% accuracy loss for 4x cost reduction
```

### Sync vs Async Enrichment
```
Chose: Async background enrichment (not blocking the API)

POST /pipeline/enrich → returns immediately → runs in background

Tradeoff:
  - Dashboard may show unenriched tickets temporarily
  - Better UX than blocking for 10+ minutes during bulk enrichment
```

### Prompt Engineering vs Fine-tuning
```
Chose prompt engineering:
  + Works today with zero training data
  + Updatable in minutes (no retraining)
  + 100% output validity in tests

Gave up:
  - Higher per-call cost vs fine-tuned model
  - Slightly higher latency (2.3s vs 50ms)
  - Dependent on external API availability

Mitigation: fallback defaults ensure no crashes even if API is down
```

---

## 5. Bonus Features — Design Decisions

### BONUS 1: RAG Knowledge Assistant (rag.py)

**What it does:** Before calling the LLM for a new ticket, search for similar past
resolved tickets and inject their resolutions into the prompt as context.

**Why TF-IDF instead of a vector database (ChromaDB, Pinecone, FAISS)?**

```
Option A — Vector DB (ChromaDB):
  + Higher semantic similarity
  - Requires embedding model (GPU or API calls)
  - Adds external service dependency
  - Overkill for 10K ticket demo

Option B — TF-IDF (Our Choice):
  + Pure Python, zero extra infrastructure
  + Fast for up to 50K tickets
  + Good enough for keyword-heavy support tickets
  + Works without any API key or GPU

Production upgrade: replace TF-IDF vectorizer with OpenAI embeddings
+ pgvector extension on PostgreSQL for semantic search at scale
```

**Architecture:**
```
build_knowledge_base(db)
  → Load 2,000 resolved tickets from DB
  → Fit TF-IDF vectorizer on issue_description corpus
  → Store matrix in memory (sparse, ~2MB)

rag_answer(query)
  → Transform query to TF-IDF vector
  → Cosine similarity against all 2,000 vectors
  → Take top-3 tickets above threshold (0.1)
  → Build enriched prompt: "Here are 3 similar resolved tickets: ..."
  → Call LLM with context-rich prompt
  → Fall back to standard analyze_ticket if no matches
```

**Why cosine similarity?**
- Measures angle between vectors (not length)
- Two tickets with same keywords score high even if one is longer
- Threshold of 0.1 is intentionally low (sparse TF-IDF on short tickets)

---

### BONUS 2: Anomaly Detection (anomaly.py)

**What it does:** Detects when a category's ticket volume spikes beyond normal
(e.g., "Payment Problem" suddenly triples in one day).

**Why Z-score instead of ML anomaly models (Isolation Forest, LSTM)?**

```
Option A — ML models (Isolation Forest, LSTM):
  + Learns complex patterns automatically
  - Needs weeks of clean historical data to train
  - Black box: hard to explain to non-technical leadership
  - Overkill for simple volume spike detection

Option B — Z-score (Our Choice):
  + Statistically interpretable: "this day is 3.2 standard deviations above mean"
  + Works with any amount of history
  + Easy to explain: "normal is 50/day, today 200 is abnormal"
  + Zero training required
```

**Algorithm:**
```python
For each category:
  1. Get last 7 days of daily ticket counts → [50, 55, 48, 52, 51, 49, 200]
  2. Calculate mean (μ) and std deviation (σ)
  3. Z-score for today = (today_count - μ) / σ
  4. If Z > threshold → spike detected

Severity mapping:
  Z > 4 → CRITICAL (extremely rare, likely production incident)
  Z > 3 → HIGH (investigate immediately)
  Z > 2 → WARNING (monitor closely)
  Z > 1.5 → INFO (slight elevation)
```

**Result on 10K dataset:** 505 anomalies detected at threshold=1.5
This is expected — synthetic data has natural clustering causing statistical spikes.

---

### BONUS 3: Multilingual Handling (multilingual.py)

**What it does:** Detect ticket language → translate to English → classify with LLM
→ translate response back to customer's language.

**Why this architecture?**

```
Option A — Multilingual LLM (GPT-4o supports 95+ languages):
  + No translation needed
  - Prompts must be carefully crafted per language
  - Structured JSON output less reliable in non-English prompts
  - Harder to validate non-English JSON responses

Option B — Detect → Translate → Classify → Translate (Our Choice):
  + All LLM work done in English (max accuracy)
  + Language detection is free (langdetect library)
  + Translation via Google Translate (free tier, deep-translator)
  + Fully modular: swap translation provider without changing LLM logic
```

**Pipeline:**
```
Input:  "Mon paiement a échoué" (French)
   │
   ▼
detect_language() → "fr"
   │
   ▼
translate_text(text, "fr", "en") → "My payment failed"
   │
   ▼
analyze_ticket("My payment failed") → {sentiment: "negative", ...}
   │
   ▼
translate_text(suggested_response, "en", "fr") → French reply
   │
   ▼
Output: {language: "fr", original: "Mon paiement...", response_in_customer_language: "..."}
```

**Supported languages:** English, French, Spanish, German (tested and verified)
**Extensible to:** 100+ languages via Google Translate API (same code)

---

### BONUS 4: Cost Optimization (cost_optimizer.py)

**What it does:** Reduces LLM API spend through caching identical/similar tickets
and smart model routing based on ticket complexity.

**Caching Strategy:**
```
Key: MD5(issue_description.lower().strip())
Why MD5: Fast hash, deterministic, 32-char key fits any dict/Redis
Why normalize: "ORDER FAILED" and "order failed" hit same cache entry

Hit rate achieved: 50% in demo (many similar support issues repeat)
Cost saved per hit: $0.000045 (300 tokens × $0.15/1M)
At 50% hit rate on 10,000 tickets: saves $0.225
At scale (1M tickets/month): saves ~$22.50/month from caching alone
```

**Smart Routing:**
```
Simple ticket (< 80 words, no numbers) → gpt-4o-mini ($0.15/1M)
Complex ticket (> 80 words or has order IDs) → gpt-4o-mini still
(In production: complex tickets → gpt-4o, simple → llama-3-8b @ $0.06/1M)

Production routing savings:
  40% of tickets are simple → route to llama-3 (60% cheaper)
  At 1M tickets: saves ~$0.036M tokens × $0.09 difference = $3.24/month
```

**Cost Tracking:**
```
Session counters: _cache_hits, _cache_miss, _tokens_used, _cost_saved
get_cost_stats() exposes these via GET /insights/cost-stats
Enables: real-time spend monitoring, projected cost for scale
```

---

### BONUS 5: Weekly Report (weekly_report.py)

**What it does:** Auto-generates a fully formatted leadership summary in the terminal,
pulling live data from all FastAPI endpoints.

**Design choices:**

```
Why terminal output (not email/PDF)?
  + Zero dependencies (no SMTP, no PDF library)
  + Works in any environment (CI, cloud, local)
  + ANSI colors make it scannable at a glance
  + Easy to redirect to file: python weekly_report.py > report.txt
  + Production: pipe to Slack webhook or email via 2 extra lines

Why pull from API (not directly from DB)?
  + Validates the full stack (API must be working too)
  + Reuses endpoint logic (no duplicated SQL)
  + Same data the dashboard shows

Sections generated automatically:
  1. Executive Summary (5 KPI metrics)
  2. Top Complaint Categories (table with SLA column)
  3. Revenue at Risk (top 5 categories)
  4. Channel Breakdown (satisfaction per channel)
  5. Recommended Actions (auto-generated by thresholds)

Action generation logic:
  SLA > 45%       → CRITICAL alert for leadership
  Escalation > 40% → HIGH: agent training recommended
  Resolution > 100h → MEDIUM: routing review needed
  Top category found → INFO: share with Product team
  High revenue risk → HIGH: prioritize retention
```
