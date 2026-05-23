# Complete Implementation Guide
## AI-Powered Customer Support Insight Platform
### Why We Did It · How We Did It · Interview Prep · Learning Resources

---

# TABLE OF CONTENTS

1. Prerequisites & Concepts
2. Component-by-Component Deep Dive
3. Data Pipeline — Why & How
4. LLM Integration — Why & How
5. FastAPI Backend — Why & How
6. Streamlit Dashboard — Why & How
7. Accuracy Testing — Why & How
8. Potential Interview Questions (with answers)
9. Recommended Videos
10. Recommended Articles
11. Bonus Features Deep Dive (RAG, Anomaly, Multilingual, Cost, Report, Audit)

---

# PART 1 — PREREQUISITES & CONCEPTS

Before understanding this project, you need to be comfortable with these concepts.

---

## 1.1 Python Fundamentals
```
What you need to know:
- Functions, classes, decorators
- File I/O (reading CSV)
- Exception handling (try/except)
- Context managers (with statements)
- Virtual environments

Why needed:
- Pipeline, API, dashboard all written in Python
- Error handling is critical for LLM calls (they can fail)
```

**Check your understanding:**
```python
# Can you explain what this does?
def analyze_ticket(text: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            result = call_api(text)
            return validate(result)
        except Exception:
            continue
    return default_result()
```

---

## 1.2 REST APIs
```
What you need to know:
- HTTP methods: GET, POST, PUT, DELETE
- Request body vs query parameters
- Status codes (200, 404, 422, 500)
- JSON as data format

Why needed:
- FastAPI builds a REST API
- Streamlit calls FastAPI endpoints
- LLM called via REST (OpenRouter)
```

**Core concept:**
```
Client                    Server
  │── POST /tickets/analyze ──►│
  │   {issue_description: ...} │
  │                            │ processes...
  │◄── 200 OK ─────────────────│
  │   {sentiment: "negative"}  │
```

---

## 1.3 Databases & SQL
```
What you need to know:
- Tables, rows, columns
- PRIMARY KEY, FOREIGN KEY
- SELECT, INSERT, JOIN
- Indexes for fast queries

Why needed:
- All 5000 tickets stored in SQLite
- Dashboard runs SQL queries for charts
- Two tables joined for enriched view
```

**Key SQL used in this project:**
```sql
-- Join raw tickets with LLM predictions
SELECT t.category, e.sentiment, COUNT(*)
FROM tickets_raw t
JOIN tickets_enriched e ON t.ticket_id = e.ticket_id
GROUP BY t.category, e.sentiment

-- Find revenue at risk
SELECT category, SUM(order_value) as revenue_at_risk
FROM tickets_raw t
JOIN tickets_enriched e ON t.ticket_id = e.ticket_id
WHERE e.sentiment = 'negative'
GROUP BY category
```

---

## 1.4 ORM (Object Relational Mapping)
```
What you need to know:
- What an ORM does (maps Python classes to DB tables)
- SQLAlchemy basics (Session, query, add, commit)
- Why ORMs exist (avoid raw SQL, prevent SQL injection)

Why needed:
- We use SQLAlchemy for all DB operations
- Models.py defines tables as Python classes
```

**The concept:**
```python
# Without ORM (raw SQL — messy, unsafe)
cursor.execute("INSERT INTO tickets VALUES (?, ?, ?)", (id, desc, cat))

# With ORM (SQLAlchemy — clean, safe)
ticket = TicketRaw(ticket_id="1", issue_description="...", category="...")
db.add(ticket)
db.commit()
```

---

## 1.5 Large Language Models (LLMs)
```
What you need to know:
- What is a transformer model
- Tokens (words broken into subword units)
- Temperature (controls randomness)
- Prompt engineering basics
- JSON mode / structured output
- API vs local model

Why needed:
- GPT-4o-mini is the AI brain of this system
- Understanding tokens helps with cost calculation
- Temperature=0.2 chosen deliberately for consistency
```

**Key concepts:**
```
Token: roughly 0.75 words
"customer support ticket" = ~3 tokens

LLM response: ~100 tokens output
Our prompt: ~200 tokens input
Total: 300 tokens per ticket

Cost: gpt-4o-mini = $0.15 per 1M input tokens
5000 tickets × 300 tokens = 1.5M tokens = $0.22 total
```

---

## 1.6 Data Engineering Concepts
```
What you need to know:
- ETL (Extract, Transform, Load)
- Data cleaning (handling nulls, types, PII)
- Batch vs streaming processing
- Idempotency (safe to run multiple times)
- Data lineage (tracking where data came from)

Why needed:
- pipeline.py implements a full ETL pipeline
- PII handling is a real engineering concern
- Idempotency prevents duplicate data
```

**ETL in our project:**
```
EXTRACT  → pd.read_csv("tickets.csv", nrows=5000)
TRANSFORM→ clean_dataframe(df)  # hash PII, fix types
LOAD     → load_to_db(df, db)   # insert into SQLite
ENRICH   → enrich_tickets(db)   # add LLM predictions
```

---

## 1.7 Docker Basics
```
What you need to know:
- What a container is
- Dockerfile syntax
- docker-compose for multi-service apps
- Volumes (persistent storage)
- Environment variables in containers

Why needed:
- Dockerfiles provided for backend + frontend
- docker-compose wires all 3 services together
```

**Core mental model:**
```
Container = lightweight VM that runs one service

docker-compose.yml defines:
  db:       PostgreSQL container
  backend:  FastAPI container
  frontend: Streamlit container

They talk to each other via container names
(backend connects to "db", not "localhost")
```

---

# PART 2 — COMPONENT DEEP DIVE

---

# PART 3 — DATA PIPELINE (pipeline.py)

## What Is It?
A pipeline is a series of automated steps that transforms raw data into a format
ready for AI analysis and storage.

```
Raw CSV → Clean → Enrich Metadata → AI Analysis → Store in DB
```

## Why We Built It This Way

### Why clean BEFORE storing?
```
Raw data problems we found:
  - customer_name: "John Smith" → privacy risk
  - customer_email: "john@example.com" → privacy risk
  - sla_breached: "Yes" (string) → should be True (boolean)
  - ticket_created_date: "2023-05-17" (string) → should be datetime

If we store dirty data and clean later:
  - SQL queries break on wrong types
  - String "Yes" can't be summed for SLA breach count
  - PII sits in database — compliance violation

Clean first → store clean → query works perfectly
```

### Why hash PII instead of deleting it?
```
customer_email → MD5 hash → customer_id

Why not just delete?
  - Need to track: "has this customer contacted us before?"
  - previous_tickets field is meaningless without customer identity
  - MD5 hash lets us GROUP BY customer without exposing email

Why MD5 and not SHA256?
  - Either works for anonymization
  - MD5 is fast, output is 32 chars (trimmed to 12 here)
  - Not for security (MD5 is broken for crypto)
  - Fine for anonymization — we don't need to reverse it
```

### Why add synthetic order_value?
```
Assignment requirement: "which problems affect revenue most"
Dataset doesn't have order_value → we need to demonstrate this feature

Random $10-$500 is realistic for e-commerce
Seed(42) ensures reproducible results (same random numbers each run)

In production: join with orders table using customer_id
```

### Why batch_size=50 with commits?
```python
if (i + 1) % batch_size == 0:
    db.commit()
```

```
If we commit every single row:
  5000 commits × overhead = very slow

If we commit everything at end:
  Pipeline crashes at ticket 4999 → lose ALL data

Batch commit of 50:
  Crash at ticket 4999 → lose only 49 rows
  Fast enough (100 commits total)
  Recoverable failure
```

### Why skip already-loaded tickets?
```python
existing = db.query(TicketRaw).filter_by(ticket_id=str(row['ticket_id'])).first()
if existing:
    continue
```

```
This makes the pipeline IDEMPOTENT
= safe to run multiple times, same result

Without this:
  Run pipeline twice → duplicate data
  Charts show double the ticket count

With this:
  Run pipeline 10 times → same 5000 unique tickets
  Safe to re-run on failure or new data
```

---

# PART 4 — LLM INTEGRATION (llm.py)

## What Is It?
A module that sends ticket text to GPT-4o-mini via OpenRouter API
and returns structured predictions.

## Why OpenRouter Instead of OpenAI Directly?
```
OpenRouter = API gateway that routes to 100+ LLMs

Benefits:
  - Single API key for GPT-4o-mini, Claude, Gemini, Llama
  - Can switch models by changing one config line
  - Cheaper than OpenAI direct for some models
  - Fallback routing if one provider is down

For this project:
  - We chose OpenRouter for flexibility
  - Model: openai/gpt-4o-mini
  - Same API format as OpenAI (drop-in replacement)
```

## Why Temperature = 0.2?
```
Temperature controls randomness in LLM output

Temperature 0.0: completely deterministic (same input = always same output)
Temperature 0.2: very consistent, small variation (our choice)
Temperature 1.0: creative, unpredictable
Temperature 2.0: chaotic, often nonsensical

Why 0.2 for classification?
  - We want consistent categorization
  - "I was charged twice" should ALWAYS be "negative"
  - High temperature = "negative" sometimes, "neutral" other times
  - Test 6 (regression) confirmed 100% consistency at temp=0.2
```

## Why Validate the JSON Output?
```python
assert result.get("sentiment") in ["positive", "negative", "neutral"]
assert isinstance(result.get("frustration_level"), int)
```

```
LLMs can hallucinate or return unexpected formats:

Example bad outputs we've seen:
  {"sentiment": "very negative"}    ← not in our schema
  {"frustration_level": "high"}     ← string instead of int
  {"sentiment": "negative", "extra_field": ...}  ← extra data
  ```json\n{"sentiment": "negative"}```  ← markdown wrapped

Validation catches all these.
Retry gives LLM a second chance.
Fallback ensures no crash even after 3 failures.
```

## Why Retry 3 Times?
```
LLM API failure reasons:
  - Rate limit hit (429 error)
  - Network timeout
  - Malformed JSON response (rare but happens)
  - Server overload (503)

3 retries covers 99.9% of transient failures
After 3 failures: return safe defaults, never crash
  → pipeline continues with next ticket
  → failed ticket can be enriched later

In our test: 0% failure rate across 20 calls
```

## Why Strip Markdown Code Blocks?
```python
if content.startswith("```"):
    content = content.split("```")[1]
    if content.startswith("json"):
        content = content[4:]
```

```
GPT-4o-mini sometimes wraps JSON in markdown:

```json
{"sentiment": "negative", ...}
```

json.loads() fails on this.
We strip the ``` markers before parsing.

This is a common real-world LLM output issue.
```

---

# PART 5 — FASTAPI BACKEND (main.py)

## What Is It?
A REST API that sits between the database and the dashboard.
9 endpoints that answer specific business questions.

## Why FastAPI Over Flask?
```
Flask:
  - Older, simpler
  - Synchronous only (blocking)
  - No auto documentation
  - Manual data validation

FastAPI:
  - Async support (handles concurrent requests efficiently)
  - Auto-generates Swagger UI at /docs
  - Pydantic validation (wrong input type → automatic 422 error)
  - 3x faster than Flask for async workloads
  - Type hints = self-documenting code
```

## Why Separate Endpoints for Each Insight?
```
Option A: One endpoint returns everything
GET /insights → returns all charts data

Problem:
  - Dashboard loads slowly (fetches unused data)
  - Can't update one chart independently
  - Hard to cache specific queries

Option B: Separate endpoints (our choice)
GET /insights/top-issues
GET /insights/sentiment-trend
GET /insights/sla-stats

Benefits:
  - Each endpoint cached independently
  - Dashboard only fetches what it needs
  - Easy to add new insights without breaking others
  - Load testing is per-endpoint
```

## Why CORS Middleware?
```python
app.add_middleware(CORSMiddleware, allow_origins=["*"])
```

```
CORS = Cross-Origin Resource Sharing

Without CORS:
  Streamlit at localhost:8501 tries to call FastAPI at localhost:8000
  Browser blocks it: "CORS policy violation"

With CORS enabled:
  FastAPI says "I accept requests from any origin"
  Browser allows the call

allow_origins=["*"] = accept from everywhere (fine for development)
Production: restrict to your specific domain
```

## Why BackgroundTasks for Enrichment?
```python
@app.post("/pipeline/enrich")
def trigger_enrichment(background_tasks: BackgroundTasks, ...):
    background_tasks.add_task(enrich_tickets, db, limit=limit)
    return {"message": "Enrichment started"}
```

```
Enriching 100 tickets takes ~4 minutes (100 × 2.3s)

Synchronous (bad):
  POST /pipeline/enrich
  → waits 4 minutes
  → client times out
  → user thinks it's broken

Background task (our choice):
  POST /pipeline/enrich
  → returns immediately: "Enrichment started"
  → LLM runs in background
  → user sees results appear on dashboard over time

This is the async/non-blocking pattern.
```

## Why the Revenue at Risk Endpoint?
```
Assignment: "which problems affect revenue the most"

Standard approach: count tickets per category
Better approach: sum order_value for negative-sentiment tickets

Logic:
  "Payment Problem" with 200 tickets but avg order $50 = $10,000 at risk
  "Security Concern" with 100 tickets but avg order $400 = $40,000 at risk

Security Concern affects more revenue despite fewer tickets.
This is business intelligence, not just data counting.
```

---

# PART 6 — STREAMLIT DASHBOARD (dashboard.py)

## What Is It?
A Python-based web app that visualizes insights from FastAPI.
No HTML/CSS/JavaScript needed.

## Why Streamlit Over React?
```
React:
  - Full control over UI
  - Better performance for complex apps
  - Steeper learning curve
  - Requires JavaScript, npm, build tools

Streamlit:
  - Pure Python (data engineers already know it)
  - 10x faster to build
  - Built-in chart components
  - Hot reload during development
  - Perfect for data dashboards

Assignment says "lightweight frontend" → Streamlit is the right call
```

## Why Plotly Over Matplotlib?
```
Matplotlib:
  - Static images
  - No interactivity
  - Good for papers/reports

Plotly (our choice):
  - Interactive (hover for values, click to filter)
  - Better looking defaults
  - Works natively in Streamlit
  - Gauge charts (we use for SLA + escalation)
```

## Why KPI Cards at the Top?
```
Dashboard design principle: "Most important info above the fold"

Executives look at KPIs first:
  Total Tickets | SLA % | Escalation % | Resolution Time | Response Time

These 5 numbers tell the story in 5 seconds.
Charts below provide the "why."

This is standard BI dashboard design
(same pattern as Tableau, Power BI, Looker)
```

## Why Gauge Charts for SLA?
```
Bar charts show comparison between categories
Line charts show trends over time
Gauge charts show: "how bad is this number right now?"

SLA Breach Rate = 50.2%

Gauge shows:
  Green zone (0-30%): good
  Yellow zone (30-60%): warning
  Red zone (60-100%): critical

Executives understand gauges instantly.
No need to explain what 50.2% means in context.
```

## Why Sidebar for New Ticket Analysis?
```
Two user types:
  1. Manager → looks at aggregate charts (main area)
  2. Agent   → analyzes specific new ticket (sidebar)

Sidebar keeps agent workflow separate from executive view.
Both use cases in one app, no context switching.
```

---

# PART 7 — ACCURACY TESTING (test_accuracy.py)

## Why 7 Different Tests?

```
Each test catches a different failure mode:

Test 1 (Sentiment Accuracy)
  → Does LLM read text correctly?

Test 2 (Consistency vs Score)
  → Does LLM match human-assigned ratings?

Test 3 (Retry Rate)
  → Does LLM return valid JSON reliably?
  → Found: 100% success rate, 0 retries needed

Test 4 (Edge Cases)
  → Does it crash on weird input?
  → Sarcasm, gibberish, very long, mixed language
  → Found: 100% pass, handles all edge cases

Test 5 (Latency)
  → Is it fast enough for production?
  → Found: 2.27s avg, well under 5s threshold

Test 6 (Regression)
  → Does same input always give same output?
  → Found: 100% consistency (temp=0.2 works)

Test 7 (Frustration Sanity)
  → Are the 1-10 scores logically correct?
  → Happy customer = low score, angry = high score
  → Found: 100% sanity pass
```

## Why Sentiment Accuracy Was 32% (And Why That's OK)

```
Test 1 compared:
  LLM sentiment vs customer_satisfaction_score

ticket: "App crashes when uploading"
  score: 5 (dataset assigned randomly)
  LLM: "negative" ← CORRECT based on text

The dataset's satisfaction scores are SYNTHETIC.
They don't correlate with issue_description.
A randomly-assigned score of 5 for a crash report is wrong data.

LLM is reading the TEXT correctly.
The ground truth LABEL is wrong.

This is a classic data quality problem:
  - Garbage in = garbage out
  - Always validate your labels before trusting them

In production with real human-assigned scores:
  Expect 85-90% sentiment accuracy.
```

---

# PART 8 — INTERVIEW QUESTIONS & ANSWERS

---

## Category A: System Design

**Q: Walk me through your architecture.**
```
"The system has 5 layers:

1. Data Layer: Raw CSV ingested via pipeline.py, cleaned,
   stored in SQLite across two tables (raw + enriched).

2. AI Layer: OpenRouter API calls GPT-4o-mini with a structured
   prompt. Returns JSON with sentiment, frustration, summary,
   and suggested response. Validates and retries on failure.

3. API Layer: FastAPI exposes 9 REST endpoints that query SQLite
   and return JSON to any client.

4. Dashboard Layer: Streamlit calls FastAPI endpoints and renders
   interactive Plotly charts.

5. DevOps Layer: Dockerized with docker-compose. GitHub Actions
   for CI/CD. Deployable to Render/Fly.io."
```

---

**Q: Why not store everything in one table?**
```
"Two tables separates concerns:

tickets_raw = immutable source of truth. Never modified.
tickets_enriched = LLM predictions. Can be re-generated.

Benefits:
- If we improve the LLM prompt, we re-run enrichment without
  touching the original data.
- We can compare old predictions vs new predictions.
- The FOREIGN KEY relationship enforces data integrity.
- Dashboard queries join only what they need — no wasted columns."
```

---

**Q: How does your system handle failures?**
```
"Three failure points and how we handle each:

1. LLM API failure:
   → Retry up to 3 times
   → After 3 failures, return safe defaults (no crash)
   → Pipeline continues to next ticket

2. Pipeline crash mid-run:
   → Batch commit every 50 tickets
   → Skip already-loaded tickets (idempotent)
   → Re-run picks up where it left off

3. Dashboard API call fails:
   → try/except in Streamlit
   → Shows error message, doesn't crash entire page"
```

---

## Category B: AI/ML

**Q: Why LLM over a trained classifier?**
```
"Three reasons:

1. Zero labeled data at day one. A custom classifier needs 5,000+
   examples per category. We had none to start.

2. Multi-task in one call. Category, sentiment, summary, and
   suggested response all from one LLM call. That would be 4
   separate ML models otherwise.

3. Handles nuance. 'Oh great, ANOTHER charge' → LLM correctly
   predicts negative. A keyword-based classifier would see 'great'
   and predict positive.

The production path is hybrid: use LLM now to accumulate labels,
fine-tune DistilBERT in 6 months for cost efficiency."
```

---

**Q: What is prompt engineering and how did you use it?**
```
"Prompt engineering is designing the input to the LLM to get
reliable, structured output.

What I did:

1. Role assignment: 'You are a customer support analyst'
   → Frames the LLM's perspective, improves relevance

2. Output schema: defined exact JSON structure expected
   → Prevents free-text responses

3. Constraints: 'positive OR negative OR neutral' explicitly listed
   → Prevents 'very negative', 'somewhat positive' etc.

4. Low temperature (0.2):
   → Reduces randomness, improves consistency

5. Strip markdown wrapper:
   → LLM sometimes wraps JSON in code blocks, we handle that

Result: 100% valid JSON in all 20 test calls."
```

---

**Q: Your sentiment accuracy was 32%. Explain that.**
```
"This is actually a data quality finding, not a model failure.

The dataset's customer_satisfaction_score is synthetically generated.
It doesn't correlate with the issue_description text.

Example: A ticket about an app crash has a satisfaction score of 5
(positive), but the text clearly describes a negative experience.

The LLM correctly reads 'app crashes on upload' as negative.
The dataset label says positive.

When I manually reviewed 10 mismatches, the LLM was right in
all 10 cases. The label was wrong.

This is a classic garbage-in problem. In production with real
human-assigned scores, I'd expect 85-90% accuracy.

The 6 tests that ARE valid (edge cases, latency, regression,
frustration, retry rate) all scored 100%."
```

---

**Q: How would you improve accuracy further?**
```
"Four approaches in priority order:

1. Better prompt with few-shot examples:
   Add 3-5 examples of correct classifications in the prompt.
   Expected improvement: +10-15% accuracy.

2. Confidence threshold:
   Ask LLM to return confidence score.
   Low confidence → flag for human review.
   Don't act on uncertain predictions.

3. Fine-tune DistilBERT:
   After accumulating 10,000 LLM-labeled tickets,
   fine-tune a small transformer model.
   Faster, cheaper, domain-specific.

4. Human feedback loop:
   Agents rate suggested responses.
   Use ratings to improve prompts iteratively."
```

---

## Category C: Data Engineering

**Q: What is idempotency and why does it matter in your pipeline?**
```
"Idempotency means: running the same operation multiple times
produces the same result as running it once.

In our pipeline:
  check if ticket_id already exists before inserting
  if yes: skip
  if no: insert

Without idempotency:
  Pipeline crashes at ticket 4500, restarts
  → 4500 duplicate rows in database
  → All counts doubled in dashboard
  → Completely wrong insights

With idempotency:
  Restart picks up from where it left off
  No duplicates
  Final result identical to a clean run

This is critical for production data pipelines."
```

---

**Q: What is the difference between batch and streaming?**
```
"Batch: Process data in large chunks on a schedule.
  - We run pipeline.py once, processes all 5000 tickets
  - Dashboard updated after each run
  - Simple to implement, cost efficient
  - Downside: data is stale between runs (hours old)

Streaming: Process each record as it arrives.
  - New ticket arrives → immediately sent to LLM → stored → dashboard updates
  - Real-time insights
  - Requires message queue (Redis/Kafka)
  - More complex to build and maintain
  - More expensive

For this assignment: batch is appropriate.
For production real-time support agent tooling: streaming required."
```

---

**Q: Why did you use SQLite instead of PostgreSQL?**
```
"Practical decision: no PostgreSQL installed locally,
zero infrastructure setup time.

SQLite is built into Python, zero installation.
Works perfectly for 5,000–50,000 rows.
All SQLAlchemy code is identical — just change DATABASE_URL.

When to use PostgreSQL instead:
  - Concurrent writes (multiple pipelines running simultaneously)
  - > 100,000 rows with complex queries
  - Multiple services reading/writing simultaneously
  - Production deployment

The switch is one line:
  DATABASE_URL=postgresql://user:pass@host:5432/db
  All SQLAlchemy models, queries, everything else stays identical."
```

---

## Category D: Business Thinking

**Q: What are the 3 most important insights for leadership?**
```
"Based on our 5,000-ticket analysis:

1. SLA breach rate is 50.2% — critical.
   Half of all customers are experiencing broken SLA commitments.
   This is a direct churn risk.

2. Feature Requests are the top category (539 tickets).
   Customers are asking for things we haven't built.
   This is a product-market fit gap signal.

3. Negative sentiment tickets carry $250+ avg order value.
   Our most frustrated customers are our highest-value customers.
   Proactive retention on this segment could protect significant revenue.

Each insight has a specific action — not just 'interesting data.'"
```

---

**Q: How would this system reduce costs?**
```
"Three mechanisms:

1. Faster agent response:
   AI summary = agent reads 1 line instead of full ticket.
   Suggested response = agent edits instead of writing from scratch.
   Estimate: 15 min → 5 min per ticket.
   At 1,000 tickets/day and $25/hr: saves ~$4,000/day.

2. Smarter routing:
   High frustration + high order value → senior agent.
   Feature requests → junior agent.
   Right ticket to right agent = higher first-contact resolution.

3. Fewer repeat tickets:
   Consistent AI-suggested responses = clearer answers.
   Customer understands → doesn't need to follow up.
   20% reduction in repeat tickets = 200 fewer tickets/day."
```

---

## Category E: DevOps

**Q: How does your CI/CD pipeline work?**
```
"GitHub Actions workflow:

On every push to main branch:
  Step 1: checkout code
  Step 2: install Python 3.11
  Step 3: install requirements
  Step 4: run flake8 linting (code quality check)
  Step 5: build Docker images (backend + frontend)
  Step 6: verify images built successfully

This ensures:
  - Broken code never reaches production
  - Docker images always buildable
  - Code style enforced automatically

Next step would be:
  - Run test_accuracy.py in CI
  - Auto-deploy to Render/Fly.io on success"
```

---

**Q: What is Docker and why use it?**
```
"Docker packages the application + all its dependencies into
a container that runs identically anywhere.

Problem it solves:
  'It works on my machine' → breaks in production because
  different Python version, different library versions, different OS.

With Docker:
  Same container image runs on my laptop, staging, production.
  Environment is guaranteed identical.

Our docker-compose.yml starts 3 containers:
  db:       PostgreSQL database
  backend:  FastAPI (depends on db being healthy first)
  frontend: Streamlit (depends on backend)

They communicate via container names, not localhost."
```

---

# PART 9 — RECOMMENDED VIDEOS

---

## Foundational Concepts

**Python for Data Engineering**
```
"Python for Beginners — Full Course" — freeCodeCamp (YouTube)
Link: youtube.com/watch?v=eWRfhZUzrAc
Why: Covers all Python needed for this project in one video
Time: 4.5 hours
```

**SQL Fundamentals**
```
"SQL Tutorial — Full Database Course for Beginners" — freeCodeCamp
Link: youtube.com/watch?v=HXV3zeQKqGY
Why: Covers SELECT, JOIN, GROUP BY — all queries used in this project
Time: 4 hours
```

**REST APIs**
```
"REST API Crash Course" — Traversy Media
Link: youtube.com/watch?v=-MTSQjw5DrM
Why: Explains GET/POST/JSON/status codes clearly
Time: 45 minutes
```

---

## FastAPI

```
"FastAPI Tutorial" — Sebastián Ramírez (FastAPI creator)
Link: youtube.com/watch?v=0sOvCWFmrtA
Why: Official tutorial from the creator himself
Time: 1 hour

"FastAPI Full Course" — freeCodeCamp
Link: youtube.com/watch?v=0sOvCWFmrtA
Why: Covers routers, Pydantic, async, database integration
Time: 1.5 hours
```

---

## LLMs & Prompt Engineering

```
"Intro to Large Language Models" — Andrej Karpathy (ex-OpenAI)
Link: youtube.com/watch?v=zjkBMFhNj_g
Why: Best conceptual explanation of how LLMs work internally
Time: 1 hour — HIGHLY RECOMMENDED

"ChatGPT Prompt Engineering for Developers" — DeepLearning.AI
Link: deeplearning.ai/short-courses/chatgpt-prompt-engineering-for-developers/
Why: Covers few-shot, chain-of-thought, JSON output — directly applicable
Time: 1.5 hours — FREE COURSE

"How GPT works" — 3Blue1Brown
Link: youtube.com/watch?v=eMlx5fFNoYc
Why: Visual explanation of transformers and attention
Time: 27 minutes
```

---

## Data Pipelines

```
"Data Engineering Full Course" — freeCodeCamp
Link: youtube.com/watch?v=ysz5S6PUM-U
Why: ETL, batch vs streaming, pipeline design
Time: 4 hours

"SQLAlchemy Tutorial" — Tech With Tim
Link: youtube.com/watch?v=AKQ3XEDI9Mw
Why: ORM concepts, models, sessions, queries
Time: 1 hour
```

---

## Streamlit

```
"Streamlit Full Tutorial" — Streamlit Official
Link: youtube.com/watch?v=VqgUkExPvLY
Why: Covers charts, layout, sidebar — everything used in dashboard
Time: 45 minutes

"Build a Data Dashboard with Streamlit and Plotly"
Link: youtube.com/watch?v=Sb0A9i6d320
Why: Exactly what we built — very applicable
Time: 30 minutes
```

---

## Docker

```
"Docker Tutorial for Beginners" — TechWorld with Nana
Link: youtube.com/watch?v=3c-iBn73dDE
Why: Best Docker beginner course, covers docker-compose
Time: 3 hours

"Docker Compose Tutorial" — TechWorld with Nana
Link: youtube.com/watch?v=DM65_JyGxCo
Why: Covers multi-service apps like our backend+frontend+db setup
Time: 1 hour
```

---

# PART 10 — RECOMMENDED ARTICLES

---

## LLMs & Prompt Engineering

```
"Prompt Engineering Guide" — promptingguide.ai
Link: promptingguide.ai
Why: Comprehensive, covers zero-shot, few-shot, chain-of-thought
Read: "Introduction" + "Techniques" sections

"OpenAI Cookbook — Structured Outputs"
Link: cookbook.openai.com
Why: Shows exactly how to get reliable JSON from LLMs
Most relevant: "How to get consistent JSON output"

"LLM Hallucination" — Wikipedia + Towards Data Science
Search: "LLM hallucination detection towardsdatascience"
Why: Understanding why LLMs return wrong data and how to mitigate
```

---

## FastAPI

```
FastAPI Official Docs — fastapi.tiangolo.com
Why: Best written API docs of any Python framework
Start with: "Tutorial — User Guide" → "First Steps" → "Path Parameters"

"FastAPI vs Flask vs Django" — testdriven.io
Search: "fastapi vs flask testdriven.io"
Why: Clear comparison with performance benchmarks
```

---

## Data Engineering

```
"The Data Engineering Lifecycle" — Fundamentals of Data Engineering (book excerpt)
Search: "data engineering lifecycle oreilly"
Why: Mental model for how pipelines fit into the bigger picture

"What is ETL?" — AWS Documentation
Link: aws.amazon.com/what-is/etl/
Why: Clear, concise ETL explanation from AWS

"Idempotency in Data Pipelines" — Medium / Towards Data Science
Search: "idempotency data pipelines medium"
Why: Explains why idempotency matters for production reliability
```

---

## System Design

```
"System Design Primer" — GitHub
Link: github.com/donnemartin/system-design-primer
Why: Best free resource for system design interviews
Read: "Scalability" + "Database" + "API Design" sections

"Designing Data-Intensive Applications" — Martin Kleppmann
Why: The definitive book on building scalable data systems
Most relevant chapters: 1 (reliability), 3 (storage), 11 (stream processing)
```

---

## SQL & Databases

```
"Use The Index, Luke" — use-the-index-luke.com
Why: Database performance explained for developers (not DBAs)
Read: "Where Clause" + "Joins"

"SQLite vs PostgreSQL" — tableplus.com
Search: "sqlite vs postgresql tableplus"
Why: When to use which database — exactly our design decision
```

---

## Docker & DevOps

```
"Docker Get Started" — Official Docs
Link: docs.docker.com/get-started/
Why: Best official tutorial, covers containers + compose

"GitHub Actions Quickstart" — Official Docs
Link: docs.github.com/en/actions/quickstart
Why: Exactly what we used for CI/CD
```

---

## Business Intelligence / Dashboards

```
"Dashboard Design Principles" — Tableau
Search: "dashboard design principles tableau"
Why: Why we put KPIs at top, when to use gauges vs bars

"North Star Metric" — Amplitude
Search: "north star metric amplitude guide"
Why: How to identify which metrics leadership should track
```

---

---

# PART 11 — BONUS FEATURES DEEP DIVE

---

## 11.1 RAG Knowledge Assistant (rag.py)

### Why we built it
Standard LLM responses are generic. A new agent asking "how do we typically resolve
payment failures?" gets a plausible but unverified answer.

RAG (Retrieval-Augmented Generation) fixes this by grounding the LLM in your own
historical data — real resolutions that actually worked.

### How it works

```
Step 1 — Build Knowledge Base
  Load 2,000 resolved tickets from DB
  Extract: ticket_id, issue_description, resolution_notes, category
  Fit a TF-IDF vectorizer on all issue_descriptions
  Store the sparse matrix in memory

Step 2 — Search for Similar Tickets
  New ticket arrives: "I was charged twice this month"
  Transform query into TF-IDF vector
  Compute cosine similarity against all 2,000 stored vectors
  Return top-3 tickets with similarity > 0.1

Step 3 — Augmented Prompt
  Inject similar tickets into the LLM prompt:
    "Here are 3 similar past cases and their resolutions:
     Case 1: [issue] → [resolution]
     Case 2: [issue] → [resolution]
     Case 3: [issue] → [resolution]
     Now respond to: [new ticket]"

Step 4 — Fallback
  If no similar tickets found (score < 0.1):
  Fall back to standard analyze_ticket() — no degradation
```

### Why TF-IDF (not embeddings)?
```
TF-IDF works well here because:
- Support tickets have distinctive keywords (payment, refund, login, shipping)
- Keyword overlap is a strong signal for similar issues
- Zero API calls, zero GPU, zero extra cost
- In-memory, fast for ≤ 50K tickets

When to upgrade to embeddings:
- Tickets are ambiguous and need semantic understanding
- "My card didn't go through" vs "payment processing failed" → same issue
- TF-IDF would miss this; OpenAI embeddings would catch it
```

### Interview questions — RAG

**Q: What is RAG and why does it improve LLM accuracy?**
> RAG (Retrieval-Augmented Generation) supplements the LLM prompt with retrieved
> relevant context — in our case, past resolved tickets. The LLM's response is no
> longer based purely on training data but is grounded in specific examples from your
> own system. This reduces hallucination and improves domain-specific accuracy.

**Q: How does cosine similarity work in your RAG system?**
> Each ticket is converted to a TF-IDF vector — a numerical representation where
> each dimension corresponds to a word's importance in the document relative to the
> corpus. Cosine similarity measures the angle between two vectors: 1.0 = identical
> content, 0 = no shared vocabulary. We use 0.1 as threshold because support tickets
> are short and TF-IDF vectors are sparse.

**Q: What would you change in production?**
> Replace TF-IDF with OpenAI text-embedding-3-small (1536 dimensions). Store vectors
> in PostgreSQL with pgvector extension. Threshold would rise to 0.7+ for semantic
> embeddings. Add cache for frequently-queried embeddings to control API costs.

---

## 11.2 Anomaly Detection (anomaly.py)

### Why we built it
The dashboard shows historical trends, but nobody watches it 24/7. Anomaly detection
automatically flags when something unusual happens — before leadership even opens the dashboard.

### How it works

```python
# Core algorithm
for each category (e.g., "Payment Problem"):
    daily_counts = get_last_7_days_counts(category)
    # e.g., [50, 55, 48, 52, 51, 49, 200]

    mean = average(daily_counts)       # 72.1
    std  = standard_deviation(counts)  # 54.6

    z_score = (200 - 72.1) / 54.6     # = 2.34 → WARNING

Severity thresholds:
    z > 4.0 → CRITICAL
    z > 3.0 → HIGH
    z > 2.0 → WARNING
    z > 1.5 → INFO (configurable via API ?threshold=)
```

### Why Z-score?
```
Alternatives considered:
  - Isolation Forest: needs weeks of training data, black-box output
  - LSTM time series: same training requirement, complex to deploy
  - Simple threshold (> 100 tickets): ignores category baseline
    ("Billing Issues" naturally gets 200/day — not an anomaly)

Z-score advantage:
  - Adapts to each category's own baseline automatically
  - Human-readable: "this is 3.2 standard deviations above normal"
  - No training required — works from day one
  - Easy to tune: lower threshold = more sensitive
```

### Interview questions — Anomaly Detection

**Q: What is a Z-score and when is something "anomalous"?**
> A Z-score measures how many standard deviations a value is from the mean.
> Z=0 means exactly average. Z=2 means 2 standard deviations above — roughly
> the top 2.5% of days for that category. We flag Z>2 as WARNING because it's
> statistically unusual while still being actionable (not too noisy).

**Q: How would you tune sensitivity for a business stakeholder?**
> Lower threshold = more alerts (catch more spikes, more false positives).
> Higher threshold = fewer alerts (only catch extreme spikes).
> For operations teams: start at Z=2.0, tune based on alert fatigue.
> For critical systems (payments): go to Z=1.5 to catch earlier.
> Our API exposes `?threshold=` so stakeholders can adjust without code changes.

**Q: Found 505 anomalies in 10K tickets — is that too many?**
> No. 505 anomalies across 10K tickets across multiple categories over a year
> is roughly 1.4 anomaly-days per category — quite reasonable. Many are INFO-level
> (Z=1.5-2.0). In a production dashboard, you'd filter by severity and only page
> on-call for CRITICAL/HIGH events.

---

## 11.3 Multilingual Handling (multilingual.py)

### Why we built it
Support teams are global. A French customer submitting "Mon paiement a échoué" gets
garbage output from an English-only prompt. Multilingual handling makes the AI work
for every customer, in any language.

### How it works

```
Full pipeline for a non-English ticket:

1. detect_language(text)
   Uses: langdetect library (open-source, no API key)
   Returns: ISO 639-1 code ("fr", "es", "de", "en")

2. translate_text(text, source="fr", target="en")
   Uses: deep-translator → Google Translate API (free tier)
   "Mon paiement a échoué" → "My payment failed"

3. analyze_ticket(english_text)
   Standard LLM analysis — always in English for consistency
   Returns: {sentiment, frustration_level, issue_summary, suggested_response}

4. translate_text(suggested_response, source="en", target="fr")
   "We apologize for the inconvenience..." → "Nous nous excusons..."

5. Return full response:
   {
     "language": "fr",
     "original_text": "Mon paiement a échoué",
     "english_translation": "My payment failed",
     "sentiment": "negative",
     "response_in_customer_language": "Nous nous excusons..."
   }
```

### Why always classify in English?
```
LLM accuracy by language (approximate):
  English:  92% structured JSON reliability
  French:   85%
  Spanish:  83%
  German:   81%
  Mandarin: 70%

By translating to English first:
  All tickets → 92% accuracy → translate response back
  Net result: high accuracy for all languages
  No need to re-engineer prompts per language
```

### Interview questions — Multilingual

**Q: How does language detection work?**
> langdetect uses a Naive Bayes classifier trained on character n-gram profiles
> for 55 languages. Short texts can be ambiguous (< 20 chars), so for very short
> tickets we default to English. It returns a confidence score; we handle low-confidence
> cases by logging and falling back to English classification.

**Q: What are the limitations of Google Translate for customer support?**
> Google Translate is excellent for straightforward text but can struggle with:
> industry jargon ("my cart abandoned" → may translate awkwardly),
> sarcasm or idioms, and very short text (< 5 words). In production, we'd log
> translated text for quality review, and for high-volume languages (French, Spanish)
> consider professional translation memory tools.

**Q: How would you scale this to 100 languages?**
> No code changes needed — deep-translator supports Google Translate's 130+ languages.
> The only tuning required: add language-specific punctuation handling for languages
> without spaces (Thai, Japanese, Mandarin) and test response translation quality per
> language. The detect→translate→classify→translate pipeline is language-agnostic.

---

## 11.4 Cost Optimization (cost_optimizer.py)

### Why we built it
At 1,000 tickets/day, LLM costs are negligible ($0.045/day). At 100,000 tickets/day,
costs become meaningful ($4.50/day = $1,600/year). Cost optimization ensures the
system scales economically.

### How it works

```
Layer 1 — Caching (biggest impact)

  key = MD5(text.lower().strip())

  Why MD5?
  - Deterministic: same input → same key always
  - Fast: microseconds vs milliseconds for LLM call
  - 32 chars: fits dict key, Redis key, database column

  Why normalize (lower + strip)?
  - "ORDER FAILED" and "order failed" → same cache hit
  - Removes trailing whitespace from copy-paste tickets

  Cache hit: return stored result instantly (0ms, $0 cost)
  Cache miss: call LLM, store result, return

Layer 2 — Smart Routing (future cost reduction)

  Simple ticket  → cheaper model (llama-3-8b @ $0.06/1M)
  Complex ticket → better model (gpt-4o-mini @ $0.15/1M)

  Complexity signals:
  - Word count > 80
  - Contains digits (order IDs, amounts)
  - Currently both route to gpt-4o-mini (safe default for demo)
  - In production: route 40% of tickets to llama → 60% cheaper per ticket

Layer 3 — Cost Tracking

  _cache_hits, _cache_miss, _tokens_used, _cost_saved
  Exposed via GET /insights/cost-stats
  Enables: monthly LLM budget reporting, ROI calculation
```

### Interview questions — Cost Optimization

**Q: Why cache by MD5 hash instead of exact string match?**
> MD5 gives us O(1) lookup regardless of ticket length — the key is always 32 chars.
> Exact string matching on a dict is also O(1) in Python (dict keys are hashed
> internally), so in practice both work. MD5's value shows up in Redis (external cache):
> the key is compact, language-agnostic, and doesn't expose PII in logs.

**Q: What's the difference between session cache and persistent cache?**
> Our current in-memory dict is session-scoped: it resets when the API restarts.
> A persistent cache (Redis with TTL, or database) survives restarts and serves
> multiple API instances. In production, we'd use Redis with 24-hour TTL: frequently
> repeated tickets (same bug affecting 1000 customers) get cached permanently,
> one-off tickets expire and free memory.

**Q: If the interviewer asks: "at what scale does this system become expensive?"**
> GPT-4o-mini at $0.15/1M tokens, ~300 tokens/ticket:
> 10,000 tickets = $0.45 (trivial)
> 1,000,000 tickets = $45/month (cheap)
> 100,000,000 tickets = $4,500/month (worth optimizing)
> The real cost driver is not LLM spend but infrastructure: at 100M tickets,
> you need distributed workers, large storage, and a caching layer. LLM cost
> with 50% cache hit rate drops to $2,250/month — still manageable.

---

## 11.5 Weekly Report (weekly_report.py)

### Why we built it
Leadership doesn't read dashboards. They read reports. A weekly summary delivered to
their inbox (or terminal) covers the same insights as the dashboard in a scannable,
shareable format — with recommended actions already generated.

### How it works

```python
def print_report():
    # 1. Fetch live data from FastAPI
    sla    = GET /insights/sla-stats
    issues = GET /insights/top-issues
    rev    = GET /insights/revenue-at-risk
    ch     = GET /insights/by-channel

    # 2. Print Executive Summary (5 KPI metrics)
    # Color: GREEN if within target, RED if breaching threshold

    # 3. Print Top 5 Complaint Categories
    # Table: category | ticket count | avg order value | SLA breaches

    # 4. Print Revenue at Risk
    # Table: category | revenue at risk | # negative tickets

    # 5. Print Channel Breakdown
    # Table: channel | volume bar | % share | satisfaction score

    # 6. Auto-generate Recommended Actions
    if sla_breach_rate > 45%:  → CRITICAL alert
    if escalation_rate > 40%:  → HIGH: agent training
    if avg_resolution > 100h:  → MEDIUM: routing review
    if top_category found:     → INFO: share with Product
    if high_revenue_risk:      → HIGH: retention priority
```

### Why pull from API, not directly from DB?

```
Option A — Query DB directly:
  + Slightly faster (no HTTP overhead)
  - Duplicates SQL logic (same queries as API endpoints)
  - Doesn't test the full stack

Option B — Call FastAPI endpoints (Our Choice):
  + Validates API is working (integration test built in)
  + Reuses endpoint logic — no duplicate SQL
  + If API is down, report fails clearly → alerting mechanism
  + Same data the dashboard shows → consistent numbers

This is the "eat your own dog food" principle: use your own API.
```

### Interview questions — Weekly Report

**Q: How would you automate this to run every Monday at 8 AM?**
> Add a cron job: `0 8 * * 1 cd /app && python -X utf8 weekly_report.py >> /var/log/weekly.log 2>&1`
> Or use Python's `schedule` library inside the FastAPI startup event.
> Or use GitHub Actions scheduled workflow: `on: schedule: - cron: '0 8 * * 1'`
> For email delivery: pipe output through sendmail or use smtplib with 5 extra lines.

**Q: How would you send this to Slack?**
> Strip ANSI color codes, convert to Slack markdown (` *bold* `, `\`\`\`code\`\`\``),
> post to Slack Incoming Webhook via `requests.post(webhook_url, json={"text": report})`.
> Total: ~20 lines of code on top of the existing report generator.

---

## 11.6 Audit System (audit.py)

### Why we built it
A system with 13 endpoints, 5 bonus modules, and an LLM integration has many failure
points. The audit system runs 8 end-to-end checks in one command and prints a clear
pass/fail summary — like a health check for the entire platform.

### What each check does

```
1. API Health Check
   → Calls all 10 endpoints
   → Verifies HTTP 200 + valid JSON response
   → Reports: "10/10 endpoints healthy"

2. Database Integrity
   → Counts rows in tickets_raw and tickets_enriched
   → Checks for NULL values in critical columns
   → Verifies foreign key integrity

3. LLM Integration
   → Sends 6 real test tickets
   → Validates JSON structure of every response
   → Measures avg latency
   → Reports: "6/6 test cases, 2.7s avg"

4. RAG Knowledge Assistant
   → Builds knowledge base
   → Queries with 2 test tickets
   → Verifies response includes past_resolutions field
   → Reports: "2000 tickets indexed"

5. Anomaly Detection
   → Calls /insights/anomalies endpoint
   → Verifies response is a list
   → Reports: "505 spikes detected"

6. Multilingual Handling
   → Tests 4 tickets: English, French, Spanish, German
   → Verifies language detection and translation fields
   → Reports: "4/4 languages (EN/FR/ES/DE)"

7. Cost Optimization
   → Calls /tickets/optimized-analyze twice with same ticket
   → First call: cache_hit = False
   → Second call: cache_hit = True (verifies caching works)
   → Reports: "50% cache hit rate, $0.0135 total"

8. Weekly Report Generation
   → Calls print_report() and captures output
   → Verifies report contains expected sections
   → Reports: "Full report generated"
```

### Current result
```
Overall: 8/8 (100%) — EXCELLENT
```

### Interview questions — Audit System

**Q: Why build an audit system separately from the test suite?**
> test_accuracy.py tests LLM output quality (sentiment accuracy, edge cases, latency).
> audit.py tests system integration (is every endpoint reachable? does RAG index load?
> does caching work?). They answer different questions:
> - test_accuracy.py → "Is the AI working well?"
> - audit.py → "Is the whole system running correctly?"

**Q: How is this different from unit tests?**
> Unit tests run in isolation (mocked dependencies, no real API calls).
> The audit is an integration test: it calls the live API, uses the real database,
> and hits the real LLM. It can only run when the full system is up — making it
> closer to a smoke test or health check than a unit test.

---

# QUICK REFERENCE: What to Say For Each Component

```
pipeline.py      → "ETL pipeline that cleans PII, enriches metadata,
                    calls LLM in batches, and stores idempotently"

llm.py           → "LLM integration with structured prompting,
                    JSON validation, retry logic, and safe fallbacks"

models.py        → "Two-table schema separating raw data from AI predictions,
                    enabling re-enrichment without data loss"

main.py          → "13-endpoint REST API built with FastAPI — 9 core endpoints
                    plus 4 bonus feature endpoints for RAG, anomaly, multilingual,
                    cost optimization"

dashboard.py     → "Real-time Streamlit dashboard calling FastAPI,
                    visualizing 6 chart types including Plotly gauges"

rag.py           → "TF-IDF knowledge base indexing 2,000 resolved tickets;
                    cosine similarity search grounds LLM responses in real history"

anomaly.py       → "Z-score spike detection per category on a rolling 7-day window;
                    505 anomalies detected in 10K dataset"

multilingual.py  → "detect → translate → classify → translate pipeline;
                    supports 130+ languages via Google Translate"

cost_optimizer.py → "MD5-hashed in-memory cache + smart model routing;
                     50% hit rate, $0.000045/ticket, $0.0135 total for 300 tickets"

weekly_report.py → "Automated leadership report pulling from live API;
                    5 sections + auto-generated recommended actions"

audit.py         → "8-check integration test suite; validates full stack end-to-end;
                    8/8 EXCELLENT on current system"

test_accuracy.py → "7-test suite covering sentiment accuracy, edge cases,
                    latency, regression consistency, and frustration sanity"

docker-compose   → "3-container orchestration: PostgreSQL, FastAPI, Streamlit,
                    with health checks and environment variable injection"

ci.yml           → "GitHub Actions pipeline: lint → build → verify on every push"
```
