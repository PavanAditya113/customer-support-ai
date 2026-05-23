import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL   = "openai/gpt-4o-mini"

PROMPT_TEMPLATE = """You are a customer support analyst for an e-commerce company.
Analyze the support ticket below and return ONLY valid JSON — no explanation, no markdown.

Ticket: "{issue_description}"

Return exactly this JSON structure:
{{
  "sentiment": "positive" or "negative" or "neutral",
  "frustration_level": integer from 1 to 10,
  "issue_summary": "one sentence describing the core problem",
  "suggested_response": "a professional agent reply under 60 words"
}}"""


def analyze_ticket(issue_description: str, retries: int = 3) -> dict:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": PROMPT_TEMPLATE.format(issue_description=issue_description)}
        ],
        "temperature": 0.2,
    }

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

            # Validate required fields
            assert result.get("sentiment") in ["positive", "negative", "neutral"]
            assert isinstance(result.get("frustration_level"), int)
            assert result.get("issue_summary")
            assert result.get("suggested_response")

            return result

        except Exception as e:
            if attempt == retries - 1:
                # Return safe default after all retries
                return {
                    "sentiment": "neutral",
                    "frustration_level": 5,
                    "issue_summary": issue_description[:100],
                    "suggested_response": "Thank you for reaching out. Our team is reviewing your issue and will respond shortly."
                }

    return {}
