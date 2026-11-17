import json
import os
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

VALID_ACTIVITIES = [
    "Work",
    "Study",
    "Sleep",
    "Exercise",
    "Family & Friends",
    "Personal Care",
    "Commute",
    "Meals",
    "Leisure",
    "Other",
]


def _get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def parse_natural_language_activities(user_text, reference_date=None):
    """
    Convert natural language (Marathi, Hindi, or English) into structured activity records.
    Returns (list_of_dicts, error_message_or_none).
    """
    client = _get_gemini_client()
    if client is None:
        return [], "GEMINI_API_KEY is not set. Please configure it in Streamlit Secrets or .env."

    ref_date = (reference_date or date.today()).isoformat()
    prompt = f"""
You are a data parser for a Work-Life Balance tracker.
Reference date (today): {ref_date}
Allowed activity_type values: {json.dumps(VALID_ACTIVITIES)}

Extract all logged activities from the user's message below (which may be in English, Marathi, or Hindi).
Return ONLY a valid JSON array of objects, with no markdown fences or extra commentary.
Each object must have:
- "activity_date": "YYYY-MM-DD" (use {ref_date} unless user says yesterday/kal/kalcha etc.)
- "activity_type": one of the exact allowed values above
- "duration_hours": float (between 0.25 and 24.0)
- "notes": short clean description in English
- "energy_level": integer 1 to 5 (default 3 if not implied)

User message:
{user_text}
"""
    try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        items = json.loads(raw)
        if not isinstance(items, list):
            return [], "AI returned an unexpected format."
        cleaned = []
        for item in items:
            act_type = item.get("activity_type", "Other")
            if act_type not in VALID_ACTIVITIES:
                act_type = "Other"
            cleaned.append({
                "activity_date": item.get("activity_date", ref_date),
                "activity_type": act_type,
                "duration_hours": float(item.get("duration_hours", 1.0)),
                "notes": str(item.get("notes", ""))[:200],
                "energy_level": max(1, min(5, int(item.get("energy_level", 3)))),
            })
        return cleaned, None
    except Exception as exc:
        # Fallback friendly message for 503 / high demand / timeout
        err_str = str(exc)
        if "503" in err_str or "UNAVAILABLE" in err_str:
            return [], "AI server is currently experiencing high demand (503). Please try again in 10 seconds or use the 'Manual' tab to log instantly."
        return [], f"Could not parse text with AI: {exc}"


def generate_weekly_coach_insight(df, weekly_summary_dict):
    """
    Analyze the last 7 days of activity logs + energy ratings and return
    actionable burnout & balance coaching advice.
    """
    client = _get_gemini_client()
    if client is None:
        return None, "GEMINI_API_KEY is not set. Please configure it in Streamlit Secrets or .env."

    if df.empty:
        return "Log a few days of activities first so the AI Coach can analyze your routine!", None

    records_preview = df[["activity_date", "activity_type", "duration_hours", "energy_level", "notes"]].tail(40).to_dict(orient="records")
    prompt = f"""
You are a supportive, practical Work-Life Balance & Productivity Coach.
Analyze the user's recent activity logs and weekly balance score ({weekly_summary_dict.get('score')}/100 - {weekly_summary_dict.get('label')}).

Recent logs:
{json.dumps(records_preview, default=str)}

Provide a concise, high-impact coaching check-in with:
1. **Burnout & Sleep Check:** Spot overwork or low sleep patterns.
2. **Energy Drain vs Boost:** Point out which activities gave high energy (4-5) vs drained energy (1-2).
3. **3 Concrete Actions for Tomorrow:** Specific, realistic adjustments.
Keep it friendly, crisp, and under 220 words.
"""
    try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
        )
        return response.text.strip(), None
    except Exception as exc:
        err_str = str(exc)
        if "503" in err_str or "UNAVAILABLE" in err_str:
            return None, "AI Coach is temporarily busy due to high traffic (503). Please click 'Generate' again in a moment."
        return None, f"AI Coach error: {exc}"