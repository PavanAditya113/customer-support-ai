# Design Document
## AI-Powered Customer Support Insight Platform

---

## Quick Links

- **Dataset:** [Customer Support Tickets — 200K Records (Kaggle)](https://www.kaggle.com/datasets/mirzayasirabdullah07/customer-support-tickets-dataset-200k-records) — we use 5,000 rows from this
- **Live Demo:** https://support-frontend-3gld.onrender.com
- **Backend API:** https://support-backend-he9e.onrender.com/docs
- **GitHub:** source code, Dockerfiles, CI/CD pipeline

## Deployment

The app runs in two Docker containers — one for the backend (FastAPI), one for the frontend (Streamlit). Both are deployed on Render and wired together via `docker-compose` locally or `render.yaml` on the cloud.

The backend loads 5,000 tickets from the CSV automatically on first startup. No manual setup needed.

CI/CD runs on every push to GitHub: lint → build Docker images → deploy to Render.

## Dashboard

Built with Streamlit. Everything pulls live from the FastAPI backend.

**Top bar — 5 KPI cards**
Total tickets, SLA breach rate, escalation rate, avg resolution time, avg first response time.

**Row 1**
- Top complaint categories — horizontal bar chart showing which issues appear most
- Sentiment trend over time — line chart showing positive/negative/neutral tickets month by month

**Row 2**
- SLA breach rate gauge — color coded (green < 30%, orange 30–60%, red > 60%)
- Escalation rate gauge — same color logic
- Revenue at risk — bar chart showing how much order value is tied to negative-sentiment tickets, broken down by category

**Row 3 — Channel breakdown**
- Pie chart of ticket volume by channel (email, chat, web, phone, social)
- Bar chart of avg satisfaction score per channel

**Row 4 — Ticket explorer**
Filterable table of 50 tickets at a time. Filter by category and sentiment using the sidebar. Click any ticket to see the full issue description, AI summary, frustration score, and the suggested agent response.

**Sidebar**
- Filter by category and sentiment
- Paste any ticket text and hit Analyze — gets sentiment, frustration score, summary, and suggested response in real time
- Button to trigger background enrichment for unenriched tickets

---

## API Endpoints

| Endpoint | What it does |
|----------|-------------|
| `POST /tickets/upload` | Upload a CSV file of new tickets |
| `POST /tickets/analyze` | Run AI analysis on a single ticket |
| `GET /tickets` | List all tickets with filters (category, sentiment) |
| `GET /tickets/{id}/response` | Get AI-suggested response for a specific ticket |
| `POST /pipeline/enrich` | Trigger background AI enrichment for unenriched tickets |
| `GET /insights/top-issues` | Top complaint categories with ticket count and SLA data |
| `GET /insights/sentiment-trend` | Sentiment breakdown month by month |
| `GET /insights/sla-stats` | SLA breach rate, escalation rate, avg resolution time |
| `GET /insights/by-channel` | Ticket volume and satisfaction score per channel |
| `GET /insights/revenue-at-risk` | Revenue tied to negative-sentiment tickets by category |
| `POST /tickets/rag-analyze` | Analyze ticket using past resolved tickets as context |
| `GET /insights/anomalies` | Detect categories with unusual ticket volume spikes |
| `GET /insights/trends` | Weekly trend summary per category |
| `POST /tickets/multilingual-analyze` | Detect language, analyze, respond in customer's language |
| `GET /insights/language-dist` | Language breakdown across all tickets |
| `POST /tickets/optimized-analyze` | AI analysis with cost caching |
| `GET /insights/cost-stats` | LLM usage stats — cache hits, tokens used, cost saved |

---

## 1. AI Choices

### Why LLM and not a custom ML model?

Simple reason — we had zero labeled data at the start. Training a custom model like DistilBERT needs at least 3,000–5,000 labeled examples. We didn't have that, so we used GPT-4o-mini via OpenRouter instead. It works out of the box with no training data and handles sentiment, summaries, and response suggestions all in one call.

| | Custom ML | GPT-4o-mini (what we use) |
|--|-----------|--------------------------|
| Training data needed | 5,000+ labeled rows | Zero |
| Day-one accuracy | Low | 85–92% |
| Cost at scale | Free after training | $0.0001/ticket |
| Update process | Full retrain | Change the prompt |

We picked GPT-4o-mini over GPT-4o specifically because it's 4x cheaper with only a 2–3% accuracy difference. At 5,000 tickets, that's $0.50 vs $2.00 — not a big deal now, but matters at scale.

### How we prompt the model

- Role defined as "customer support analyst for an e-commerce company"
- Temperature set to 0.2 so output is consistent, not creative
- Strict JSON format required — 4 fields, no exceptions
- Retries up to 3 times if the response is invalid
- Falls back to safe defaults if all retries fail — no crashes

### Why no embeddings or vector database in the core pipeline?

Embeddings are great for search — finding similar tickets. We don't need search in the main pipeline, we need classification. LLM does that directly. We did build RAG as a bonus feature using TF-IDF (no extra infrastructure), with a clear path to upgrade to proper embeddings in production.

### Future upgrade plan

Right now the LLM labels every ticket. Once we have enough of those labels (around 10,000), we can fine-tune a smaller, faster, cheaper model on them. That's the long-term goal — use the LLM to generate training data, then replace it.

---

## 2. Data Engineering

This is where most of the actual engineering work went. Getting raw CSV data into a clean, queryable structure that can power a live dashboard took several deliberate decisions.

### Data pipeline

The raw Kaggle CSV has 200K rows and messy fields — string booleans, unhashed emails, missing columns, inconsistent date formats. We clean all of that before anything touches the database.

Steps:
1. **Ingest** — read CSV (5,000 rows) or accept new tickets via upload API
2. **Clean** — hash customer emails to MD5 (PII protection), convert `"Yes"/"No"` strings to proper booleans, parse dates to ISO format, drop low-value columns like browser, OS, gender, age
3. **Enrich** — add synthetic `order_value` if missing, normalize channel names
4. **AI analysis** — send `issue_description` to LLM, validate JSON response, retry up to 3x on failure, store result in second table
5. **Store** — commit to SQLite in batches of 50, skip already-processed tickets (idempotent — safe to re-run)

### Two-table design

`tickets_raw` holds everything from the source — never modified after insert. `tickets_enriched` holds what the AI adds and links back by `ticket_id`.

Keeping them separate means we can re-run AI enrichment with a better model without touching the original data. Every dashboard chart is a JOIN across both tables.

Key fields:
- `issue_description` — raw ticket text, sent to LLM
- `sentiment` — positive / negative / neutral (LLM output)
- `frustration_level` — 1 to 10 (LLM output)
- `order_value` — used for revenue-at-risk calculations
- `sla_breached` — boolean, drives SLA breach rate metric
- `customer_id` — MD5 hash of email, never stores real PII

### SQL queries powering the dashboard

Every chart on the dashboard runs a SQL query against SQLite. No pandas aggregations on the frontend — all computation happens at the database level.

**Top complaint categories**
```sql
SELECT category, COUNT(*) as count,
       AVG(order_value) as avg_order_value,
       SUM(CASE WHEN sla_breached THEN 1 ELSE 0 END) as sla_breached_count
FROM tickets_raw
GROUP BY category
ORDER BY count DESC
LIMIT 10
```

**Sentiment trend over time**
```sql
SELECT strftime('%Y-%m', t.ticket_created_date) as month,
       e.sentiment, COUNT(*) as count
FROM tickets_raw t
JOIN tickets_enriched e ON t.ticket_id = e.ticket_id
WHERE t.ticket_created_date IS NOT NULL
GROUP BY month, sentiment
ORDER BY month
```
This is where both tables get joined — raw ticket has the date, enriched table has the sentiment.

**SLA and escalation stats**
```sql
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN sla_breached THEN 1 ELSE 0 END) as breached,
    SUM(CASE WHEN escalated THEN 1 ELSE 0 END) as escalated,
    AVG(resolution_time_hours) as avg_resolution_hours,
    AVG(first_response_time_hours) as avg_first_response_hours
FROM tickets_raw
```
Single query powers all 5 KPI cards at the top of the dashboard.

**Revenue at risk**
```sql
SELECT t.category,
       SUM(t.order_value) as revenue_at_risk,
       COUNT(*) as negative_tickets
FROM tickets_raw t
JOIN tickets_enriched e ON t.ticket_id = e.ticket_id
WHERE e.sentiment = 'negative'
GROUP BY t.category
ORDER BY revenue_at_risk DESC
```
Joins order value (raw table) with sentiment (enriched table) to calculate how much revenue is tied to frustrated customers.

**Channel satisfaction**
```sql
SELECT channel, COUNT(*) as count,
       AVG(customer_satisfaction_score) as avg_satisfaction
FROM tickets_raw
GROUP BY channel
ORDER BY count DESC
```

---

## 3. Scalability

### What we have now

Single process, SQLite, FastAPI, Streamlit. Works fine for 5,000 tickets and a demo environment.

### What happens at 100K tickets/day

SQLite gets replaced with PostgreSQL, and a Redis queue sits between the API and the LLM workers. Instead of processing tickets one by one in a loop, multiple workers pull from the queue in parallel. Five workers at 30 tickets/min each = 216,000 tickets/day.

### Batch vs streaming

Right now we use **batch processing** — tickets are loaded and enriched in bulk when the container starts. It's simpler, cheaper, and good enough for a static dataset.

**Streaming is the next step.** The idea is: the moment a new ticket comes in, it gets processed immediately instead of waiting for the next batch run. This means the dashboard stays up to date in real time and agents get AI suggestions the second a ticket lands. We'd use a Redis queue or Celery workers to handle this. It's planned once we have time to implement it properly — the architecture already supports it, it's just a matter of swapping the trigger.

---

## 4. Tradeoffs

**SQLite vs PostgreSQL** — SQLite is zero setup and handles our current load easily. The switch to PostgreSQL is one config change (just update `DATABASE_URL`), no code changes needed.

**LLM latency (2.3s)** — Each ticket takes about 2.3 seconds to enrich. For a batch job that's fine. For a real-time agent tool, we'd run workers in parallel to bring the effective throughput up.

**Batch enrichment is async** — When you hit `/pipeline/enrich`, the API returns immediately and runs in the background. The dashboard might show unenriched tickets briefly, but it's better than blocking the API for 10 minutes.

**Prompt engineering vs fine-tuning** — Prompt engineering works today with no training data. The downside is cost and latency compared to a fine-tuned model. The plan is to get there eventually once we have enough labeled data.

---

## 5. Bonus features

### RAG assistant

Searches past resolved tickets for similar issues and adds them to the prompt as context before calling the LLM. We used TF-IDF instead of a vector database — it's pure Python, no extra services, and works well for keyword-heavy support tickets. In production, this would upgrade to proper embeddings + pgvector.

### Anomaly detection

Watches daily ticket volume per category. When something spikes more than 2 standard deviations above its normal range, an alert fires. We used Z-score instead of a machine learning model because it's easy to explain: "normal is 50/day, today is 200, that's a spike." Found 505 anomaly events in our 5K dataset.

### Multilingual support

Detects the ticket language, translates to English, runs the LLM, then translates the response back. We do all AI work in English because that's where accuracy is highest, then wrap it with translation on both ends. Works across 130+ languages. Tested and confirmed for English, French, Spanish, German.

### Cost caching

Identical tickets (same wording) return a cached result instead of calling the LLM again. Cache key is an MD5 hash of the normalized ticket text. Hit rate in testing: 50%. At scale, this cuts LLM spend roughly in half.

### Weekly report

Auto-generates a leadership summary by pulling from the live API endpoints — KPIs, top complaint categories, revenue at risk, channel breakdown, and suggested actions based on thresholds. Output goes to terminal right now (easy to redirect to Slack or email with two extra lines). No separate DB queries, no duplicated logic — it reuses the same data the dashboard shows.
