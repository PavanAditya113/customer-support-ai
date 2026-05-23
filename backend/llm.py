import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL   = "openai/gpt-4o-mini"

VALID_SENTIMENTS  = ["positive", "negative", "neutral"]
VALID_CATEGORIES  = [
    "Payment Problem", "Bug Report", "Login Issue", "Refund Request",
    "Feature Request", "Account Suspension", "Data Sync Issue",
    "Performance Issue", "Security Concern", "Subscription Cancellation"
]
VALID_PRIORITIES  = ["Low", "Medium", "High", "Critical"]

PROMPT_PREFIX = """You are a customer support analyst for an e-commerce company.
Analyze the support ticket below and return ONLY valid JSON — no explanation, no markdown.

Ticket: \""""

PROMPT_SUFFIX = """\"

Return exactly this JSON structure:
{
  "sentiment": "positive" or "negative" or "neutral",
  "frustration_level": integer from 1 to 10,
  "category": one of "Payment Problem" or "Bug Report" or "Login Issue" or "Refund Request" or "Feature Request" or "Account Suspension" or "Data Sync Issue" or "Performance Issue" or "Security Concern" or "Subscription Cancellation",
  "priority": one of "Low" or "Medium" or "High" or "Critical",
  "issue_summary": "one sentence describing the core problem",
  "suggested_response": "a professional agent reply under 60 words"
}"""


def build_prompt(issue_description: str) -> str:
    # Use concatenation instead of .format() to avoid crashes
    # when issue_description contains { or } characters
    return PROMPT_PREFIX + issue_description + PROMPT_SUFFIX


def analyze_ticket(issue_description: str, retries: int = 3) -> dict:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": build_prompt(issue_description)}
        ],
        "temperature": 0.2,
    }

    last_error = None
    for attempt in range(retries):
        try:
            response = httpx.post(API_URL, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"].strip()

            # Strip markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            result = json.loads(content)

            # Validate sentiment
            if result.get("sentiment") not in VALID_SENTIMENTS:
                raise ValueError(f"Invalid sentiment: {result.get('sentiment')}")

            # Accept int or float for frustration_level, convert to int
            fl = result.get("frustration_level")
            if not isinstance(fl, (int, float)):
                raise ValueError(f"Invalid frustration_level: {fl}")
            result["frustration_level"] = int(fl)

            if not result.get("issue_summary"):
                raise ValueError("Missing issue_summary")
            if not result.get("suggested_response"):
                raise ValueError("Missing suggested_response")

            # Normalize category
            if result.get("category") not in VALID_CATEGORIES:
                result["category"] = "General Inquiry"

            # Normalize priority
            if result.get("priority") not in VALID_PRIORITIES:
                result["priority"] = "Medium"

            return result

        except Exception as e:
            last_error = str(e)
            if attempt < retries - 1:
                continue

    # All retries failed — return safe defaults
    print(f"LLM fallback triggered after {retries} attempts. Last error: {last_error}")
    return {
        "sentiment": "neutral",
        "frustration_level": 5,
        "category": "General Inquiry",
        "priority": "Medium",
        "issue_summary": issue_description[:100],
        "suggested_response": "Thank you for reaching out. Our team is reviewing your issue and will respond shortly."
    }
