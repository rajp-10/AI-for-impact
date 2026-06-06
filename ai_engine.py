import json
import os
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# 1. Define the exact strict structure we want back from Gemini
class ThreatReport(BaseModel):
    risk_score: int = Field(description="Risk score from 0 (Safe) to 100 (Absolute Scam)")
    risk_level: str = Field(description="Low, Medium, or High risk level classification")
    red_flags: list[str] = Field(description="Specific bulleted list of linguistic or operational red flags found")
    analysis_summary: str = Field(description="A brief, harsh breakdown of why this listing failed or passed verification")
    safety_checklist: list[str] = Field(description="Actionable steps the student must take next to stay safe")

def analyze_job_posting(company_name: str, job_text: str):
    # Fetch API key from environment variable
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"error": "Missing GEMINI_API_KEY environment variable."}
    
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are a professional Cyber Security Threat Analyst specializing in recruitment fraud.
    Analyze this internship/job posting for a college student:
    Company Name/URL: {company_name}
    Job Description Text: {job_text}
    
    Evaluate deep semantic patterns (urgency, vague tracking, asking for security deposits, unofficial domains).
    """
    
    try:
        # Request a structured JSON object matching our Pydantic schema
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ThreatReport,
                temperature=0.2 # Keep it consistent and analytical
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        return {"error": f"API Evaluation Failed: {str(e)}"}