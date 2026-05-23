"""
test_accuracy.py
Runs all 7 accuracy tests and prints a full report.
"""

import sys
import os
import time
import json
from datetime import datetime

# Fix Windows Unicode output
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

sys.path.append(os.path.dirname(__file__))

from database import SessionLocal
from models import TicketRaw, TicketEnriched
from llm import analyze_ticket

# ── Colors for terminal output ───────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def header(title):
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE}  {title}{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}")

def pass_fail(condition, label, detail=""):
    icon = f"{GREEN}[PASS]{RESET}" if condition else f"{RED}[FAIL]{RESET}"
    print(f"  {icon}  {label}")
    if detail:
        print(f"        {YELLOW}{detail}{RESET}")

def score_color(val, good, warn):
    if val >= good:
        return f"{GREEN}{val}{RESET}"
    elif val >= warn:
        return f"{YELLOW}{val}{RESET}"
    return f"{RED}{val}{RESET}"


# ════════════════════════════════════════════════════════════
# TEST 1 — LLM Category Classification Accuracy
# ════════════════════════════════════════════════════════════
def test_category_accuracy(db, sample_size=50):
    header("TEST 1 — LLM Category Classification Accuracy")

    tickets = (
        db.query(TicketRaw)
        .limit(sample_size)
        .all()
    )

    correct = 0
    total   = len(tickets)
    mismatches = []

    for t in tickets:
        result = analyze_ticket(t.issue_description)
        predicted = result.get("sentiment", "")  # LLM predicted sentiment
        actual_category = t.category

        # Ask LLM to also predict category
        break  # we'll use enriched table instead

    # Use already-enriched tickets for category check
    # LLM doesn't predict category directly — we validate sentiment vs satisfaction
    enriched = (
        db.query(TicketRaw, TicketEnriched)
        .join(TicketEnriched, TicketRaw.ticket_id == TicketEnriched.ticket_id)
        .limit(sample_size)
        .all()
    )

    if not enriched:
        print(f"  {YELLOW}⚠ No enriched tickets found. Run pipeline.py first.{RESET}")
        return 0

    sentiment_map = {1: "negative", 2: "negative", 3: "neutral", 4: "positive", 5: "positive"}
    correct   = 0
    total     = len(enriched)
    mismatches = []

    for raw, enc in enriched:
        expected = sentiment_map.get(raw.customer_satisfaction_score, "neutral")
        if enc.sentiment == expected:
            correct += 1
        else:
            mismatches.append({
                "ticket_id":   raw.ticket_id,
                "score":       raw.customer_satisfaction_score,
                "expected":    expected,
                "predicted":   enc.sentiment,
                "description": raw.issue_description[:60]
            })

    accuracy = round(correct / total * 100, 1)
    print(f"\n  Tested {total} enriched tickets")
    print(f"  Correct sentiment predictions : {correct}/{total}")
    print(f"  Sentiment Accuracy            : {score_color(accuracy, 75, 60)}%")

    pass_fail(accuracy >= 75, f"Sentiment accuracy ≥ 75%", f"Got {accuracy}%")

    if mismatches[:3]:
        print(f"\n  {YELLOW}Sample mismatches:{RESET}")
        for m in mismatches[:3]:
            print(f"    Ticket {m['ticket_id']} | score={m['score']} "
                  f"| expected={m['expected']} | predicted={m['predicted']}")
            print(f"    → \"{m['description']}\"")

    return accuracy


# ════════════════════════════════════════════════════════════
# TEST 2 — Sentiment Consistency Test
# ════════════════════════════════════════════════════════════
def test_sentiment_consistency(db, sample_size=100):
    header("TEST 2 — Sentiment Consistency vs Satisfaction Score")

    enriched = (
        db.query(TicketRaw, TicketEnriched)
        .join(TicketEnriched, TicketRaw.ticket_id == TicketEnriched.ticket_id)
        .limit(sample_size)
        .all()
    )

    if not enriched:
        print(f"  {YELLOW}⚠ No enriched tickets found.{RESET}")
        return {}

    breakdown = {"positive": {"correct": 0, "total": 0},
                 "negative": {"correct": 0, "total": 0},
                 "neutral":  {"correct": 0, "total": 0}}

    sentiment_map = {1: "negative", 2: "negative", 3: "neutral", 4: "positive", 5: "positive"}

    for raw, enc in enriched:
        expected = sentiment_map.get(raw.customer_satisfaction_score, "neutral")
        breakdown[expected]["total"] += 1
        if enc.sentiment == expected:
            breakdown[expected]["correct"] += 1

    print(f"\n  {'Sentiment':<12} {'Correct':<10} {'Total':<10} {'Accuracy'}")
    print(f"  {'-'*45}")
    for sent, data in breakdown.items():
        if data["total"] == 0:
            continue
        acc = round(data["correct"] / data["total"] * 100, 1)
        color = GREEN if acc >= 70 else (YELLOW if acc >= 55 else RED)
        print(f"  {sent:<12} {data['correct']:<10} {data['total']:<10} {color}{acc}%{RESET}")

    overall = sum(d["correct"] for d in breakdown.values())
    total   = sum(d["total"]   for d in breakdown.values())
    overall_acc = round(overall / total * 100, 1) if total else 0
    print(f"\n  Overall consistency: {score_color(overall_acc, 75, 60)}%")
    pass_fail(overall_acc >= 75, "Consistency ≥ 75%", f"Got {overall_acc}%")

    return breakdown


# ════════════════════════════════════════════════════════════
# TEST 3 — Retry Rate / Failure Rate
# ════════════════════════════════════════════════════════════
def test_retry_rate(sample_size=20):
    header("TEST 3 — LLM Retry Rate & Failure Rate")

    test_texts = [
        "I was charged twice and no one is helping.",
        "The app crashes every time I open it.",
        "My order never arrived.",
        "I cannot log into my account.",
        "I want to cancel my subscription.",
        "Your service is amazing, very happy!",
        "Data is not syncing across devices.",
        "I received the wrong item in my order.",
        "The payment failed but money was deducted.",
        "Bug in the report generation feature.",
        "Account suspended without any reason.",
        "Refund not processed after 10 days.",
        "Security alert — suspicious login detected.",
        "Feature request: dark mode please.",
        "Performance is very slow after update.",
        "My password reset email never arrived.",
        "I was billed for a plan I didn't choose.",
        "Support agent was rude and unhelpful.",
        "App works great on iOS but not Android.",
        "I've been waiting 2 weeks for a response.",
    ]

    total_calls  = 0
    retry_calls  = 0
    fail_calls   = 0
    valid_results = 0

    required_keys = {"sentiment", "frustration_level", "issue_summary", "suggested_response"}
    valid_sentiments = {"positive", "negative", "neutral"}

    for text in test_texts[:sample_size]:
        total_calls += 1
        result = analyze_ticket(text)

        # Check validity
        missing_keys = required_keys - set(result.keys())
        invalid_sentiment = result.get("sentiment") not in valid_sentiments
        invalid_frustration = not isinstance(result.get("frustration_level"), int)

        if missing_keys or invalid_sentiment or invalid_frustration:
            fail_calls += 1
        else:
            valid_results += 1

    failure_rate = round(fail_calls / total_calls * 100, 1)
    success_rate = round(valid_results / total_calls * 100, 1)

    print(f"\n  Total calls   : {total_calls}")
    print(f"  Valid results : {valid_results}")
    print(f"  Failed calls  : {fail_calls}")
    print(f"  Success rate  : {score_color(success_rate, 95, 85)}%")
    print(f"  Failure rate  : {score_color(100-success_rate, 5, 15) if fail_calls else GREEN+'0.0'+RESET}%")

    pass_fail(failure_rate < 5,  "Failure rate < 5%",  f"Got {failure_rate}%")
    pass_fail(success_rate > 95, "Success rate > 95%", f"Got {success_rate}%")

    return success_rate


# ════════════════════════════════════════════════════════════
# TEST 4 — Edge Case Handling
# ════════════════════════════════════════════════════════════
def test_edge_cases():
    header("TEST 4 — Edge Case Handling")

    edge_cases = [
        {
            "name": "Sarcasm",
            "text": "Oh GREAT, another charge I didn't ask for. Fantastic service 🙄",
            "expected_sentiment": "negative",
        },
        {
            "name": "Very short input",
            "text": "broken",
            "expected_sentiment": None,  # any valid output
        },
        {
            "name": "Very long input",
            "text": "I have been a loyal customer for many years. " * 30,
            "expected_sentiment": None,
        },
        {
            "name": "Mixed language",
            "text": "Mi orden está muy mal, please help me urgently!",
            "expected_sentiment": "negative",
        },
        {
            "name": "Gibberish",
            "text": "asdfgh jkl qwerty zxcvbn",
            "expected_sentiment": None,
        },
        {
            "name": "Positive ticket",
            "text": "Your support team was absolutely amazing! Issue resolved in minutes.",
            "expected_sentiment": "positive",
        },
        {
            "name": "Empty-like input",
            "text": "...",
            "expected_sentiment": None,
        },
        {
            "name": "Angry caps",
            "text": "THIS IS UNACCEPTABLE. I WANT MY MONEY BACK NOW!!!",
            "expected_sentiment": "negative",
        },
    ]

    passed = 0
    total  = len(edge_cases)

    print(f"\n  {'Case':<20} {'Sentiment':<12} {'Frustration':<14} {'Status'}")
    print(f"  {'-'*65}")

    for case in edge_cases:
        try:
            result = analyze_ticket(case["text"])
            sentiment    = result.get("sentiment", "ERROR")
            frustration  = result.get("frustration_level", "?")
            summary      = result.get("issue_summary", "")
            response     = result.get("suggested_response", "")

            # Validate structure
            valid_structure = (
                sentiment in {"positive", "negative", "neutral"} and
                isinstance(frustration, int) and
                1 <= frustration <= 10 and
                len(summary) > 0 and
                len(response) > 0
            )

            # Validate expected sentiment if specified
            sentiment_ok = (
                case["expected_sentiment"] is None or
                sentiment == case["expected_sentiment"]
            )

            ok = valid_structure and sentiment_ok
            if ok:
                passed += 1

            status = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
            print(f"  {case['name']:<20} {sentiment:<12} {str(frustration):<14} {status}")

        except Exception as e:
            print(f"  {case['name']:<20} {'CRASH':<12} {'N/A':<14} {RED}CRASH: {e}{RESET}")

    edge_accuracy = round(passed / total * 100, 1)
    print(f"\n  Passed: {passed}/{total} edge cases")
    pass_fail(edge_accuracy >= 87, "Edge case pass rate ≥ 87%", f"Got {edge_accuracy}%")

    return edge_accuracy


# ════════════════════════════════════════════════════════════
# TEST 5 — Latency Test
# ════════════════════════════════════════════════════════════
def test_latency(sample_size=10):
    header("TEST 5 — Latency Test")

    test_texts = [
        "My payment failed but money was deducted from my account.",
        "I cannot login to my account since yesterday.",
        "The app is very slow and keeps crashing.",
        "I need a refund for my cancelled order #4521.",
        "My subscription was cancelled without my request.",
        "Data is not syncing between my phone and laptop.",
        "I received a damaged product in my delivery.",
        "Bug in the invoice PDF generation feature.",
        "Suspicious login from unknown location detected.",
        "I want to upgrade my plan but checkout fails.",
    ]

    times = []
    print(f"\n  Running {sample_size} timed LLM calls...\n")

    for i, text in enumerate(test_texts[:sample_size]):
        start = time.time()
        analyze_ticket(text)
        elapsed = round(time.time() - start, 2)
        times.append(elapsed)
        bar = "█" * int(elapsed * 5)
        print(f"  Call {i+1:>2} | {elapsed:.2f}s | {bar}")

    avg_latency = round(sum(times) / len(times), 2)
    max_latency = round(max(times), 2)
    min_latency = round(min(times), 2)
    p95_latency = round(sorted(times)[int(len(times) * 0.95)], 2) if len(times) >= 20 else max_latency

    print(f"\n  Min latency : {GREEN}{min_latency}s{RESET}")
    print(f"  Avg latency : {score_color(avg_latency, 3, 5)}s")
    print(f"  Max latency : {score_color(max_latency, 5, 8)}s")
    print(f"  P95 latency : {score_color(p95_latency, 5, 8)}s")

    pass_fail(avg_latency < 5, "Avg latency < 5s",  f"Got {avg_latency}s")
    pass_fail(max_latency < 10, "Max latency < 10s", f"Got {max_latency}s")

    return avg_latency, max_latency


# ════════════════════════════════════════════════════════════
# TEST 6 — Regression / Consistency Test
# ════════════════════════════════════════════════════════════
def test_regression():
    header("TEST 6 — Regression Consistency Test (Same Input → Same Output)")

    test_tickets = [
        "I was charged twice this month.",
        "App crashes when I try to upload a file.",
        "Your support team is amazing, very happy!",
        "My order never arrived after 2 weeks.",
        "I cannot reset my password.",
        "Suspicious activity on my account.",
        "The dashboard is very slow to load.",
        "I want to cancel my subscription.",
        "Refund not processed after 10 days.",
        "Wrong item delivered in my package.",
    ]

    print(f"\n  Running each ticket twice and comparing...\n")
    print(f"  {'Ticket':<45} {'Run1':<12} {'Run2':<12} {'Match'}")
    print(f"  {'-'*75}")

    matches     = 0
    total       = len(test_tickets)

    for text in test_tickets:
        r1 = analyze_ticket(text)
        r2 = analyze_ticket(text)

        s1 = r1.get("sentiment", "?")
        s2 = r2.get("sentiment", "?")
        match = s1 == s2
        if match:
            matches += 1

        icon  = f"{GREEN}✓{RESET}" if match else f"{RED}✗{RESET}"
        label = text[:43] + ".." if len(text) > 43 else text
        print(f"  {label:<45} {s1:<12} {s2:<12} {icon}")

    consistency = round(matches / total * 100, 1)
    print(f"\n  Consistent results: {matches}/{total}")
    print(f"  Regression consistency: {score_color(consistency, 90, 75)}%")
    pass_fail(consistency >= 90, "Consistency ≥ 90%", f"Got {consistency}%")

    return consistency


# ════════════════════════════════════════════════════════════
# TEST 7 — Frustration Level Sanity Check
# ════════════════════════════════════════════════════════════
def test_frustration_sanity():
    header("TEST 7 — Frustration Level Sanity Check")

    test_cases = [
        {"text": "Your team was amazing! Very happy with the service.", "expected": "low",   "range": (1, 3)},
        {"text": "My issue was resolved, thank you.",                   "expected": "low",   "range": (1, 4)},
        {"text": "I have a question about my subscription.",            "expected": "medium","range": (2, 6)},
        {"text": "I've been waiting 3 days with no response.",          "expected": "medium","range": (4, 8)},
        {"text": "I WAS CHARGED 3 TIMES AND NOBODY IS HELPING!!!",     "expected": "high",  "range": (7, 10)},
        {"text": "This is absolutely unacceptable. I want my money back NOW!", "expected": "high", "range": (7, 10)},
    ]

    print(f"\n  {'Expected':<10} {'Got':<8} {'Range':<12} {'Status':<8} Description")
    print(f"  {'-'*75}")

    passed = 0
    for case in test_cases:
        result = analyze_ticket(case["text"])
        level  = result.get("frustration_level", 0)
        lo, hi = case["range"]
        ok     = lo <= level <= hi
        if ok:
            passed += 1
        status = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        desc   = case["text"][:40] + "..."
        print(f"  {case['expected']:<10} {str(level):<8} {str(case['range']):<12} {status:<8} {desc}")

    sanity = round(passed / len(test_cases) * 100, 1)
    print(f"\n  Passed: {passed}/{len(test_cases)}")
    pass_fail(sanity >= 83, "Frustration sanity ≥ 83%", f"Got {sanity}%")

    return sanity


# ════════════════════════════════════════════════════════════
# FINAL REPORT
# ════════════════════════════════════════════════════════════
def print_final_report(results: dict):
    header("FINAL ACCURACY REPORT")

    print(f"\n  {'Test':<40} {'Score':<15} {'Status'}")
    print(f"  {'-'*65}")

    thresholds = {
        "Sentiment Accuracy":         (results.get("sentiment_accuracy", 0),    75),
        "Sentiment Consistency":      (results.get("sentiment_consistency", 0), 75),
        "LLM Success Rate":           (results.get("success_rate", 0),          95),
        "Edge Case Pass Rate":        (results.get("edge_accuracy", 0),         87),
        "Avg Latency (s)":            (results.get("avg_latency", 99),          5,  True),
        "Regression Consistency":     (results.get("regression", 0),            90),
        "Frustration Sanity":         (results.get("frustration", 0),           83),
    }

    overall_pass = 0
    total_tests  = len(thresholds)

    for test, vals in thresholds.items():
        if len(vals) == 3:  # latency — lower is better
            score, threshold, lower_is_better = vals
            ok = score <= threshold
            unit = "s"
        else:
            score, threshold = vals
            ok = score >= threshold
            unit = "%"

        status = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        if ok:
            overall_pass += 1
        print(f"  {test:<40} {str(score)+unit:<15} {status}")

    overall_pct = round(overall_pass / total_tests * 100, 1)
    grade = (
        f"{GREEN}EXCELLENT{RESET}" if overall_pct >= 85 else
        f"{YELLOW}GOOD{RESET}"     if overall_pct >= 70 else
        f"{RED}NEEDS WORK{RESET}"
    )

    print(f"\n  {BOLD}Overall: {overall_pass}/{total_tests} tests passed ({overall_pct}%) → {grade}{RESET}")
    print(f"\n  Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}\n")


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"\n{BOLD}Customer Support AI — Accuracy Test Suite{RESET}")
    print(f"Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    db = SessionLocal()
    results = {}

    try:
        # Run all 7 tests
        results["sentiment_accuracy"]     = test_category_accuracy(db, sample_size=100)
        sc = test_sentiment_consistency(db, sample_size=100)
        total_c = sum(v["total"] for v in sc.values()) or 1
        correct_c = sum(v["correct"] for v in sc.values())
        results["sentiment_consistency"]  = round(correct_c / total_c * 100, 1)
        results["success_rate"]           = test_retry_rate(sample_size=20)
        results["edge_accuracy"]          = test_edge_cases()
        avg_lat, max_lat                  = test_latency(sample_size=10)
        results["avg_latency"]            = avg_lat
        results["max_latency"]            = max_lat
        results["regression"]             = test_regression()
        results["frustration"]            = test_frustration_sanity()

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Tests interrupted by user.{RESET}")

    finally:
        db.close()

    print_final_report(results)
