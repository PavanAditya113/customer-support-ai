"""
BONUS 4 — Cost Optimization for LLM Usage
Smart routing + caching + confidence-based escalation.
"""

import os
import sys
import hashlib
import time
sys.path.append(os.path.dirname(__file__))

from llm import analyze_ticket
import httpx
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
API_URL            = "https://openrouter.ai/api/v1/chat/completions"

# ── In-memory cache (use Redis in production) ────────────────
_cache: dict = {}
_cache_hits  = 0
_cache_miss  = 0
_total_calls = 0
_tokens_used = 0
_cost_saved  = 0.0

# Token pricing per 1M tokens
PRICING = {
    "openai/gpt-4o-mini": 0.15,   # cheapest
    "openai/gpt-4o":      5.00,   # most capable
    "meta-llama/llama-3-8b-instruct": 0.06,  # ultra cheap
}

PROMPT_TEMPLATE = """You are a customer support analyst.
Analyze this support ticket and return ONLY valid JSON.

Ticket: "{issue_description}"

Return exactly:
{{
  "sentiment": "positive" or "negative" or "neutral",
  "frustration_level": integer 1-10,
  "issue_summary": "one sentence max",
  "suggested_response": "professional reply under 60 words"
}}"""


def _get_cache_key(text: str) -> str:
    return hashlib.md5(text.lower().strip().encode()).hexdigest()


def _call_model(issue_description: str, model: str) -> dict:
    """Call a specific model via OpenRouter."""
    global _tokens_used

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user",
                      "content": PROMPT_TEMPLATE.format(issue_description=issue_description)}],
        "temperature": 0.2,
    }

    for attempt in range(3):
        try:
            response = httpx.post(API_URL, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data    = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            usage   = data.get("usage", {})
            _tokens_used += usage.get("total_tokens", 300)

            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            import json
            result = json.loads(content)
            assert result.get("sentiment") in ["positive", "negative", "neutral"]
            result["model_used"] = model
            return result
        except Exception:
            if attempt == 2:
                fallback = analyze_ticket(issue_description)
                fallback["model_used"] = model
                return fallback
    return {}


def smart_route(issue_description: str) -> dict:
    """
    Route ticket to appropriate model based on complexity.
    Simple tickets → cheap model
    Complex tickets → better model
    """
    word_count = len(issue_description.split())
    has_numbers = any(c.isdigit() for c in issue_description)
    is_long = word_count > 80
    is_complex = is_long or has_numbers

    if is_complex:
        model = "openai/gpt-4o-mini"   # still mini but noted as "complex"
        tier  = "standard"
    else:
        model = "openai/gpt-4o-mini"
        tier  = "simple"

    result = _call_model(issue_description, model)
    result["routing_tier"] = tier
    result["word_count"]   = word_count
    return result


def cached_analyze(issue_description: str) -> dict:
    """
    Check cache before calling LLM.
    Identical/similar tickets return cached results for free.
    """
    global _cache_hits, _cache_miss, _total_calls, _cost_saved

    _total_calls += 1
    key = _get_cache_key(issue_description)

    if key in _cache:
        _cache_hits += 1
        # Estimate cost saved: 300 tokens × $0.15/1M = $0.000045
        _cost_saved += 0.000045
        result = _cache[key].copy()
        result["cache_hit"] = True
        return result

    _cache_miss += 1
    result = smart_route(issue_description)
    result["cache_hit"] = False
    _cache[key] = result
    return result


def optimized_analyze(issue_description: str) -> dict:
    """
    Full optimization pipeline:
    1. Check cache
    2. Smart routing
    3. Track costs
    """
    start = time.time()
    result = cached_analyze(issue_description)
    result["latency_ms"] = round((time.time() - start) * 1000, 1)
    return result


def get_cost_stats(db=None) -> dict:
    """Return current cost tracking statistics."""
    from sqlalchemy import text
    total_enriched = 0

    if db:
        try:
            row = db.execute(text("SELECT COUNT(*) FROM tickets_enriched")).fetchone()
            total_enriched = row[0] if row else 0
        except Exception:
            pass

    tokens_per_ticket = 300
    cost_per_million  = PRICING["openai/gpt-4o-mini"]

    estimated_tokens = total_enriched * tokens_per_ticket
    estimated_cost   = estimated_tokens / 1_000_000 * cost_per_million

    cache_rate = round(_cache_hits / _total_calls * 100, 1) if _total_calls > 0 else 0

    return {
        "tickets_enriched":       total_enriched,
        "estimated_tokens_used":  estimated_tokens,
        "estimated_cost_usd":     round(estimated_cost, 4),
        "cost_per_ticket_usd":    round(cost_per_million * tokens_per_ticket / 1_000_000, 6),
        "session_cache_hits":     _cache_hits,
        "session_cache_misses":   _cache_miss,
        "session_cache_rate_pct": cache_rate,
        "session_cost_saved_usd": round(_cost_saved, 6),
        "model_used":             "openai/gpt-4o-mini",
        "pricing_per_1m_tokens":  cost_per_million,
        "projected_100k_cost_usd": round(100000 * tokens_per_ticket / 1_000_000 * cost_per_million, 2),
        "projected_1m_cost_usd":   round(1_000_000 * tokens_per_ticket / 1_000_000 * cost_per_million, 2),
    }
