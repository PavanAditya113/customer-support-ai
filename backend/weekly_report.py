"""
BONUS 5 — Automated Weekly Insight Report
Generates a formatted report and prints to terminal (+ optional email).
"""

import os
import sys
sys.path.append(os.path.dirname(__file__))

import requests
from datetime import datetime, timedelta
from database import SessionLocal
from sqlalchemy import text

API = "http://localhost:8001"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
DIM    = "\033[2m"


def fetch_data():
    try:
        sla    = requests.get(f"{API}/insights/sla-stats",      timeout=5).json()
        issues = requests.get(f"{API}/insights/top-issues",     timeout=5).json()
        rev    = requests.get(f"{API}/insights/revenue-at-risk",timeout=5).json()
        ch     = requests.get(f"{API}/insights/by-channel",     timeout=5).json()
        return sla, issues, rev, ch
    except Exception as e:
        print(f"{RED}API not reachable: {e}{RESET}")
        return None, None, None, None


def generate_actions(sla, issues, rev):
    actions = []
    if sla["sla_breach_rate"] > 45:
        actions.append(("CRITICAL", f"SLA breach at {sla['sla_breach_rate']}% — immediate staffing review needed"))
    if sla["escalation_rate"] > 40:
        actions.append(("HIGH",     f"Escalation rate {sla['escalation_rate']}% — agent training recommended"))
    if sla["avg_resolution_hours"] > 100:
        actions.append(("MEDIUM",   f"Avg resolution {sla['avg_resolution_hours']}h — review ticket routing logic"))
    if issues:
        actions.append(("INFO",     f"Top complaint '{issues[0]['category']}' — share with Product team this week"))
    if rev:
        actions.append(("HIGH",     f"${rev[0]['revenue_at_risk']:,.0f} revenue at risk in '{rev[0]['category']}' — prioritize retention"))
    if not actions:
        actions.append(("INFO",     "All metrics within acceptable range — maintain current operations"))
    return actions


def print_report():
    print(f"\n{BOLD}{BLUE}{'='*65}{RESET}")
    print(f"{BOLD}{CYAN}   WEEKLY CUSTOMER SUPPORT INSIGHT REPORT{RESET}")
    print(f"{BOLD}{BLUE}   Week of {(datetime.now()-timedelta(days=7)).strftime('%B %d')} — {datetime.now().strftime('%B %d, %Y')}{RESET}")
    print(f"{BOLD}{BLUE}{'='*65}{RESET}")

    sla, issues, rev, channels = fetch_data()
    if not sla:
        return

    # ── EXECUTIVE SUMMARY ────────────────────────────────────
    print(f"\n{BOLD}  EXECUTIVE SUMMARY{RESET}")
    print(f"  {'─'*60}")

    def kpi(label, value, unit="", good_fn=None):
        val_str = f"{value}{unit}"
        if good_fn:
            color = GREEN if good_fn(value) else RED
        else:
            color = CYAN
        print(f"  {label:<35} {color}{BOLD}{val_str}{RESET}")

    kpi("Total Tickets",              f"{sla['total_tickets']:,}")
    kpi("SLA Breach Rate",            sla['sla_breach_rate'],  "%",  lambda x: x < 30)
    kpi("Escalation Rate",            sla['escalation_rate'],  "%",  lambda x: x < 25)
    kpi("Avg Resolution Time",        sla['avg_resolution_hours'], "h", lambda x: x < 72)
    kpi("Avg First Response Time",    sla['avg_first_response_hours'], "h", lambda x: x < 24)

    # ── TOP COMPLAINT CATEGORIES ─────────────────────────────
    print(f"\n{BOLD}  TOP COMPLAINT CATEGORIES{RESET}")
    print(f"  {'─'*60}")
    print(f"  {'Category':<30} {'Tickets':>8} {'Avg Order':>12} {'SLA Breach':>11}")
    print(f"  {'─'*60}")

    for i, issue in enumerate(issues[:5]):
        rank_color = RED if i == 0 else YELLOW if i == 1 else RESET
        bar_len    = int(issue['count'] / max(i['count'] for i in issues) * 20)
        bar        = "█" * bar_len
        print(
            f"  {rank_color}{issue['category']:<30}{RESET}"
            f"  {issue['count']:>6}"
            f"  ${issue['avg_order_value']:>10.2f}"
            f"  {issue['sla_breached_count']:>9}"
        )

    # ── REVENUE AT RISK ───────────────────────────────────────
    if rev:
        print(f"\n{BOLD}  REVENUE AT RISK (Negative Sentiment Tickets){RESET}")
        print(f"  {'─'*60}")
        print(f"  {'Category':<30} {'Revenue at Risk':>16} {'Tickets':>8}")
        print(f"  {'─'*60}")
        total_risk = 0
        for r in rev[:5]:
            total_risk += r['revenue_at_risk']
            print(
                f"  {RED}{r['category']:<30}{RESET}"
                f"  ${r['revenue_at_risk']:>14,.2f}"
                f"  {r['negative_tickets']:>7}"
            )
        print(f"  {'─'*60}")
        print(f"  {'TOTAL REVENUE AT RISK':<30}  ${total_risk:>14,.2f}")

    # ── CHANNEL BREAKDOWN ────────────────────────────────────
    if channels:
        print(f"\n{BOLD}  TICKETS BY CHANNEL{RESET}")
        print(f"  {'─'*60}")
        total_ch = sum(c['count'] for c in channels)
        for c in channels:
            pct = round(c['count'] / total_ch * 100, 1)
            bar = "█" * int(pct / 3)
            sat_color = GREEN if c['avg_satisfaction'] >= 3.5 else RED
            print(
                f"  {c['channel']:<15} {bar:<20} {pct:>5}%"
                f"  Satisfaction: {sat_color}{c['avg_satisfaction']:.2f}/5{RESET}"
            )

    # ── RECOMMENDED ACTIONS ───────────────────────────────────
    actions = generate_actions(sla, issues, rev or [])
    print(f"\n{BOLD}  RECOMMENDED ACTIONS FOR LEADERSHIP{RESET}")
    print(f"  {'─'*60}")
    severity_colors = {
        "CRITICAL": RED,
        "HIGH":     YELLOW,
        "MEDIUM":   CYAN,
        "INFO":     GREEN,
    }
    for severity, action in actions:
        color = severity_colors.get(severity, RESET)
        print(f"  {color}[{severity:<8}]{RESET} {action}")

    # ── FOOTER ───────────────────────────────────────────────
    print(f"\n{BOLD}{BLUE}{'='*65}{RESET}")
    print(f"{DIM}  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    print(f"{DIM}  Source: Customer Support Insight Platform — AI Analysis{RESET}")
    print(f"{BOLD}{BLUE}{'='*65}{RESET}\n")


if __name__ == "__main__":
    print_report()
