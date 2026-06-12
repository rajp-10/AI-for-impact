import json
import os
from google import genai
from dotenv import load_dotenv
load_dotenv()

def analyze_job_posting(company_name: str, job_text: str):

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        return {"error": "Missing GEMINI_API_KEY environment variable."}

    client = genai.Client(api_key=api_key)

    prompt = f"""
You are a professional Cyber Security Threat Analyst specializing in recruitment fraud.

Analyze the following job posting.

Return ONLY valid JSON.

{{
    "risk_score": 0,
    "risk_level": "",
    "red_flags": [],
    "analysis_summary": "",
    "safety_checklist": []
}}

Company Name:
{company_name}

Job Description:
{job_text}
"""

    try:

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        clean_text = (
            response.text
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        return json.loads(clean_text)

    except Exception as e:
        return {"error": f"API Evaluation Failed: {str(e)}"}