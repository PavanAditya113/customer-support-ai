"""
TERMINAL AUDIT SYSTEM
Full live audit of the entire platform — runs in terminal.
Tests all components, shows status, runs all bonus features.
"""

import sys
import os
import time
import json
import requests
from datetime import datetime

sys.path.append(os.path.dirname(__file__))

# ── Terminal Colors ───────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
DIM    = "\033[2m"
BG_BLUE = "\033[44m"

API = "http://localhost:8001"


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def banner():
    print(f"\n{BOLD}{BG_BLUE}{'':^65}{RESET}")
    print(f"{BOLD}{BG_BLUE}{'  CUSTOMER SUPPORT AI — TERMINAL AUDIT SYSTEM':^65}{RESET}")
    print(f"{BOLD}{BG_BLUE}{'':^65}{RESET}")
    print(f"{DIM}  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}\n")


def section(title):
    print(f"\n{BOLD}{BLUE}{'─'*65}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{BLUE}{'─'*65}{RESET}")


def status(label, ok, detail="", warn=False):
    if ok:
        icon  = f"{GREEN}[PASS]{RESET}"
    elif warn:
        icon  = f"{YELLOW}[WARN]{RESET}"
    else:
        icon  = f"{RED}[FAIL]{RESET}"
    print(f"  {icon}  {label:<45} {DIM}{detail}{RESET}")


def metric(label, value, unit="", good_fn=None):
    if good_fn is not None:
        color = GREEN if good_fn(value) else RED
    else:
        color = CYAN
    print(f"  {'→'} {label:<40} {color}{BOLD}{value}{unit}{RESET}")


# ════════════════════════════════════════════════════════════
# AUDIT 1 — API HEALTH CHECK
# ════════════════════════════════════════════════════════════
def audit_api():
    section("AUDIT 1 — API HEALTH CHECK")

    endpoints = [
        ("GET", "/",                          "Root health check"),
        ("GET", "/insights/sla-stats",        "SLA statistics"),
        ("GET", "/insights/top-issues",       "Top complaint categories"),
        ("GET", "/insights/sentiment-trend",  "Sentiment trend"),
        ("GET", "/insights/by-channel",       "Channel breakdown"),
        ("GET", "/insights/revenue-at-risk",  "Revenue at risk"),
        ("GET", "/insights/anomalies",        "Anomaly detection"),
        ("GET", "/insights/cost-stats",       "LLM cost tracking"),
        ("GET", "/insights/language-dist",    "Language distribution"),
        ("GET", "/tickets",                   "Ticket listing"),
    ]

    passed = 0
    for method, path, label in endpoints:
        try:
            start = time.time()
            r = requests.get(f"{API}{path}", timeout=5)
            ms = round((time.time() - start) * 1000)
            ok = r.status_code == 200
            if ok:
                passed += 1
            status(label, ok, f"{r.status_code} | {ms}ms")
        except Exception as e:
            status(label, False, f"Connection error: {str(e)[:40]}")

    print(f"\n  Result: {passed}/{len(endpoints)} endpoints healthy")
    return passed == len(endpoints)


# ════════════════════════════════════════════════════════════
# AUDIT 2 — DATABASE AUDIT
# ════════════════════════════════════════════════════════════
def audit_database():
    section("AUDIT 2 — DATABASE AUDIT")

    from database import engine, SessionLocal
    from models import TicketRaw, TicketEnriched
    from sqlalchemy import text, inspect

    try:
        db = SessionLocal()

        # Table existence
        inspector = inspect(engine)
        tables    = inspector.get_table_names()
        status("tickets_raw table exists",      "tickets_raw" in tables)
        status("tickets_enriched table exists", "tickets_enriched" in tables)

        # Row counts
        raw_count      = db.query(TicketRaw).count()
        enriched_count = db.query(TicketEnriched).count()
        enrich_pct     = round(enriched_count / raw_count * 100, 1) if raw_count else 0

        metric("Total raw tickets",      raw_count,      "", lambda x: x >= 1000)
        metric("Total enriched tickets", enriched_count, "", lambda x: x >= 50)
        metric("Enrichment coverage",    enrich_pct,     "%",lambda x: x >= 1)

        # Null checks on critical columns
        null_desc = db.execute(text(
            "SELECT COUNT(*) FROM tickets_raw WHERE issue_description IS NULL OR issue_description = ''"
        )).scalar()
        null_cat = db.execute(text(
            "SELECT COUNT(*) FROM tickets_raw WHERE category IS NULL OR category = ''"
        )).scalar()

        status("No null issue_descriptions", null_desc == 0, f"{null_desc} nulls found")
        status("No null categories",         null_cat  == 0, f"{null_cat} nulls found")

        # Category distribution
        rows = db.execute(text(
            "SELECT category, COUNT(*) as c FROM tickets_raw GROUP BY category ORDER BY c DESC"
        )).fetchall()

        print(f"\n  {'Category':<32} {'Count':>8} {'%':>6}")
        print(f"  {'─'*48}")
        for cat, cnt in rows:
            pct     = round(cnt / raw_count * 100, 1)
            bar     = "█" * int(pct / 2)
            color   = YELLOW if pct > 15 else RESET
            print(f"  {color}{cat:<32}{RESET}  {cnt:>7}  {pct:>5}%  {DIM}{bar}{RESET}")

        # Sentiment distribution (enriched)
        sent_rows = db.execute(text(
            "SELECT sentiment, COUNT(*) as c FROM tickets_enriched GROUP BY sentiment"
        )).fetchall()
        if sent_rows:
            print(f"\n  Sentiment Distribution (enriched tickets):")
            for sent, cnt in sent_rows:
                pct   = round(cnt / enriched_count * 100, 1)
                color = GREEN if sent == "positive" else RED if sent == "negative" else YELLOW
                print(f"    {color}{sent:<12}{RESET} {cnt:>6} tickets ({pct}%)")

        db.close()
        return True

    except Exception as e:
        status("Database connection", False, str(e))
        return False


# ════════════════════════════════════════════════════════════
# AUDIT 3 — LLM INTEGRATION AUDIT
# ════════════════════════════════════════════════════════════
def audit_llm():
    section("AUDIT 3 — LLM INTEGRATION AUDIT")

    from llm import analyze_ticket

    test_cases = [
        ("Positive",  "Your team resolved my issue in minutes! Great service.",  "positive"),
        ("Negative",  "I was charged TWICE and nobody is responding!!!",          "negative"),
        ("Neutral",   "I have a question about my subscription plan.",            "neutral"),
        ("Sarcasm",   "Oh GREAT, another broken feature. Very helpful indeed.",   "negative"),
        ("Short",     "app broken",                                               None),
        ("Multilang", "Mon paiement a echoue, aidez moi s'il vous plait.",        "negative"),
    ]

    passed   = 0
    latencies = []

    print(f"\n  {'Case':<12} {'Expected':<12} {'Got':<12} {'Frustration':<14} {'Latency':<10} {'Status'}")
    print(f"  {'─'*72}")

    for name, text, expected in test_cases:
        start  = time.time()
        result = analyze_ticket(text)
        ms     = round((time.time() - start) * 1000)
        latencies.append(ms)

        got     = result.get("sentiment", "ERROR")
        frust   = result.get("frustration_level", "?")
        has_sum = bool(result.get("issue_summary"))
        has_res = bool(result.get("suggested_response"))

        valid_structure = (
            got in ["positive", "negative", "neutral"] and
            isinstance(frust, int) and 1 <= frust <= 10 and
            has_sum and has_res
        )
        correct_sentiment = expected is None or got == expected
        ok = valid_structure and correct_sentiment

        if ok:
            passed += 1

        icon  = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        color = GREEN if ok else RED
        print(
            f"  {name:<12} {str(expected or 'any'):<12} "
            f"{color}{got:<12}{RESET} {str(frust):<14} {ms}ms{'':<5} {icon}"
        )

    avg_ms = round(sum(latencies) / len(latencies))
    max_ms = max(latencies)

    print(f"\n  Passed       : {passed}/{len(test_cases)}")
    print(f"  Avg Latency  : {GREEN if avg_ms < 4000 else RED}{avg_ms}ms{RESET}")
    print(f"  Max Latency  : {GREEN if max_ms < 8000 else RED}{max_ms}ms{RESET}")

    return passed >= len(test_cases) - 1


# ════════════════════════════════════════════════════════════
# AUDIT 4 — BONUS 1: RAG KNOWLEDGE ASSISTANT
# ════════════════════════════════════════════════════════════
def audit_rag():
    section("AUDIT 4 — BONUS: RAG KNOWLEDGE ASSISTANT")

    from rag import build_knowledge_base, find_similar_tickets, rag_answer
    from database import SessionLocal

    db = SessionLocal()

    print("  Building knowledge base from resolved tickets...")
    built = build_knowledge_base(db)
    status("Knowledge base built", built)

    if not built:
        db.close()
        return False

    # Test similarity search
    test_query = "I was charged twice on my credit card"
    similar    = find_similar_tickets(test_query, top_k=3)
    status("Similarity search returns results", len(similar) > 0,
           f"Found {len(similar)} similar tickets")

    if similar:
        print(f"\n  Query: '{test_query}'")
        print(f"  Top similar past tickets:")
        for i, s in enumerate(similar, 1):
            print(f"    {i}. [{s['category']}] similarity={s['similarity_score']}")
            print(f"       Issue: {s['issue_description'][:70]}...")
            print(f"       Resolution: {s['resolution_notes'][:70]}...")

    # Test full RAG answer
    print(f"\n  Testing full RAG answer generation...")
    start  = time.time()
    result = rag_answer(test_query)
    ms     = round((time.time() - start) * 1000)

    status("RAG answer generated",  bool(result.get("suggested_response")), f"{ms}ms")
    status("RAG context used",      result.get("rag_used", False))
    status("Valid JSON structure",  result.get("sentiment") in ["positive","negative","neutral"])

    if result.get("suggested_response"):
        print(f"\n  {CYAN}RAG Suggested Response:{RESET}")
        print(f"  '{result['suggested_response']}'")
        print(f"  {DIM}(informed by {len(similar)} similar past resolutions){RESET}")

    db.close()
    return bool(result.get("suggested_response"))


# ════════════════════════════════════════════════════════════
# AUDIT 5 — BONUS 2: ANOMALY DETECTION
# ════════════════════════════════════════════════════════════
def audit_anomaly():
    section("AUDIT 5 — BONUS: ANOMALY DETECTION")

    from anomaly import detect_spikes, get_trend_summary
    from database import SessionLocal

    db     = SessionLocal()
    spikes = detect_spikes(db, z_threshold=1.5)
    trends = get_trend_summary(db)

    status("Anomaly detection runs without error", True)
    metric("Anomalies detected (z>1.5)", len(spikes))

    if spikes:
        print(f"\n  {'Date':<12} {'Category':<30} {'Count':>7} {'Z-Score':>9} {'Severity'}")
        print(f"  {'─'*65}")
        for s in spikes[:5]:
            color = RED if s['severity'] == "CRITICAL" else YELLOW
            print(
                f"  {s['date']:<12} {color}{s['category']:<30}{RESET}"
                f"  {s['ticket_count']:>6}  {s['z_score']:>8}  {color}{s['severity']}{RESET}"
            )
    else:
        print(f"  {GREEN}No anomalies detected — ticket volumes are stable{RESET}")

    # Week-over-week trends
    print(f"\n  Week-over-Week Trends:")
    print(f"  {'Category':<30} {'This Week':>10} {'Last Week':>10} {'Change':>8}")
    print(f"  {'─'*60}")
    for t in trends[:5]:
        color = RED if t['change_pct'] > 20 else GREEN if t['change_pct'] < -10 else RESET
        arrow = "▲" if t['direction'] == "UP" else "▼" if t['direction'] == "DOWN" else "─"
        print(
            f"  {t['category']:<30} {t['this_week']:>10} {t['last_week']:>10}"
            f"  {color}{arrow} {t['change_pct']:>5}%{RESET}"
        )

    db.close()
    return True


# ════════════════════════════════════════════════════════════
# AUDIT 6 — BONUS 3: MULTILINGUAL
# ════════════════════════════════════════════════════════════
def audit_multilingual():
    section("AUDIT 6 — BONUS: MULTILINGUAL TICKET HANDLING")

    from multilingual import handle_multilingual_ticket, detect_language, LANGDETECT_AVAILABLE, TRANSLATOR_AVAILABLE

    status("langdetect library available",   LANGDETECT_AVAILABLE)
    status("deep-translator library available", TRANSLATOR_AVAILABLE)

    test_tickets = [
        ("English",    "My payment failed and I need help immediately."),
        ("French",     "Mon paiement a echoue, aidez moi s'il vous plait."),
        ("Spanish",    "Mi pedido nunca llego y nadie me responde."),
        ("German",     "Die App ist abgesturzt und ich verliere meine Daten."),
    ]

    print(f"\n  {'Language':<12} {'Detected':<12} {'Sentiment':<12} {'Translated?':<14} {'Status'}")
    print(f"  {'─'*65}")

    passed = 0
    for lang, text in test_tickets:
        result   = handle_multilingual_ticket(text)
        detected = result.get("detected_language", "?")
        sent     = result.get("sentiment", "?")
        trans    = result.get("translation_applied", False)
        valid    = sent in ["positive", "negative", "neutral"]

        if valid:
            passed += 1

        icon  = f"{GREEN}PASS{RESET}" if valid else f"{RED}FAIL{RESET}"
        trans_str = f"{GREEN}Yes{RESET}" if trans else f"{DIM}No (EN){RESET}"
        print(f"  {lang:<12} {detected:<12} {sent:<12} {trans_str:<22} {icon}")

        if result.get("suggested_response_translated") and trans:
            print(f"    {DIM}Response ({detected}): {result['suggested_response_translated'][:70]}...{RESET}")

    print(f"\n  Passed: {passed}/{len(test_tickets)}")
    return passed >= 3


# ════════════════════════════════════════════════════════════
# AUDIT 7 — BONUS 4: COST OPTIMIZATION
# ════════════════════════════════════════════════════════════
def audit_cost_optimizer():
    section("AUDIT 7 — BONUS: COST OPTIMIZATION")

    from cost_optimizer import optimized_analyze, cached_analyze, get_cost_stats
    from database import SessionLocal

    db = SessionLocal()

    # Test caching
    test_text = "I cannot login to my account since yesterday."

    print("  Testing cache (same ticket sent twice)...")
    start = time.time()
    r1    = cached_analyze(test_text)
    ms1   = round((time.time() - start) * 1000)

    start = time.time()
    r2    = cached_analyze(test_text)
    ms2   = round((time.time() - start) * 1000)

    cache_worked = r2.get("cache_hit", False)
    status("First call hits LLM",   not r1.get("cache_hit", True), f"{ms1}ms")
    status("Second call hits cache", cache_worked,                  f"{ms2}ms (saved ~{ms1-ms2}ms)")
    status("Cache returns same sentiment",
           r1.get("sentiment") == r2.get("sentiment"),
           f"Both: {r1.get('sentiment')}")

    # Cost stats
    stats = get_cost_stats(db)
    print(f"\n  {BOLD}Cost Statistics:{RESET}")
    metric("Tickets enriched",          stats['tickets_enriched'])
    metric("Estimated tokens used",     f"{stats['estimated_tokens_used']:,}")
    metric("Estimated total cost",      f"${stats['estimated_cost_usd']:.4f}", " USD")
    metric("Cost per ticket",           f"${stats['cost_per_ticket_usd']:.6f}", " USD")
    metric("Projected cost (100K tkts)",f"${stats['projected_100k_cost_usd']:.2f}", " USD")
    metric("Projected cost (1M tkts)",  f"${stats['projected_1m_cost_usd']:.2f}", " USD")
    metric("Session cache hit rate",    stats['session_cache_rate_pct'], "%", lambda x: x >= 0)

    db.close()
    return cache_worked


# ════════════════════════════════════════════════════════════
# AUDIT 8 — WEEKLY REPORT
# ════════════════════════════════════════════════════════════
def audit_weekly_report():
    section("AUDIT 8 — BONUS: AUTOMATED WEEKLY REPORT")
    print()
    from weekly_report import print_report
    print_report()
    return True


# ════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ════════════════════════════════════════════════════════════
def final_summary(results: dict):
    section("FINAL AUDIT SUMMARY")

    total  = len(results)
    passed = sum(1 for v in results.values() if v)
    pct    = round(passed / total * 100, 1)

    print(f"\n  {'Audit':<45} {'Result'}")
    print(f"  {'─'*60}")
    for name, ok in results.items():
        icon = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"  {name:<45} {icon}")

    grade_color = GREEN if pct >= 85 else YELLOW if pct >= 70 else RED
    grade = "EXCELLENT" if pct >= 85 else "GOOD" if pct >= 70 else "NEEDS WORK"

    print(f"\n  {BOLD}Overall: {passed}/{total} audits passed ({pct}%){RESET}")
    print(f"  {grade_color}{BOLD}Grade: {grade}{RESET}")
    print(f"\n  {DIM}Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    print(f"\n{BOLD}{BLUE}{'='*65}{RESET}\n")


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════
def main():
    banner()

    audits = [
        ("API Health Check",          audit_api),
        ("Database Integrity",        audit_database),
        ("LLM Integration",           audit_llm),
        ("RAG Knowledge Assistant",   audit_rag),
        ("Anomaly Detection",         audit_anomaly),
        ("Multilingual Handling",     audit_multilingual),
        ("Cost Optimization",         audit_cost_optimizer),
        ("Weekly Report Generation",  audit_weekly_report),
    ]

    results = {}
    for name, fn in audits:
        try:
            result = fn()
            results[name] = result
        except Exception as e:
            print(f"  {RED}AUDIT CRASHED: {e}{RESET}")
            results[name] = False

    final_summary(results)


if __name__ == "__main__":
    main()
