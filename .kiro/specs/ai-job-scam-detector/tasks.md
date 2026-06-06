# Implementation Plan: AI Job Scam Detector

## Overview

Implement a Python/Streamlit web application that analyzes job postings for scam signals using the Google Gemini API. The build follows a bottom-up order: data models → service components → orchestration → UI → deployment wiring. Each step integrates immediately into the pipeline so no code is left orphaned.

---

## Tasks

- [ ] 1. Set up project structure, dependencies, and data models
  - Create the directory layout: `app.py`, `models.py`, `exceptions.py`, `domain_auditor.py`, `prompt_builder.py`, `gemini_client.py`, `schema_validator.py`, `orchestrator.py`, `dashboard.py`
  - Create `requirements.txt` pinning: `streamlit>=1.35.0`, `google-generativeai>=0.7.0`, `python-whois>=0.9.4`, `hypothesis>=6.100.0`, `pytest>=8.2.0`
  - Create `.streamlit/secrets.toml.example` with a placeholder `GEMINI_API_KEY = "YOUR_KEY_HERE"` and add `secrets.toml` to `.gitignore`
  - _Requirements: 12.2, 12.5_

  - [ ] 1.1 Implement data models and custom exceptions in `models.py` and `exceptions.py`
    - Write `RiskCategory` enum with six values: `linguistic`, `financial`, `domain`, `identity`, `process`, `compensation`
    - Write `AnalysisRequest`, `DomainAuditResult`, `RiskIndicator`, `SafetyStep`, `ScamAnalysisReport` dataclasses exactly as specified in the design
    - Write `GeminiAPIError`, `SchemaValidationError`, `ConfigurationError` exception classes in `exceptions.py`
    - Write the `derive_risk_label(score: int) -> str` helper function in `models.py`
    - Write `SCAM_ANALYSIS_SCHEMA` dict in `models.py`
    - _Requirements: 7.1, 7.2, 7.5, 7.6, 7.7, 7.8, 7.9, 7.11_

  - [ ]* 1.2 Write property tests for `derive_risk_label` and `ScamAnalysisReport` model integrity
    - **Property 2: Label Consistency** — `@given(st.integers(min_value=0, max_value=100))` — assert `derive_risk_label(score)` returns the correct label for all valid scores
    - **Validates: Requirements 5.4, 5.5, 7.2, 13.3**

- [ ] 2. Implement `SchemaValidator`
  - [ ] 2.1 Implement `validate(raw_json: str) -> ScamAnalysisReport` in `schema_validator.py`
    - Parse raw JSON string with `json.loads`; raise `SchemaValidationError` on `JSONDecodeError`
    - Check all seven required top-level fields; raise `SchemaValidationError` naming any missing field
    - Clamp `risk_score` to `max(0, min(100, int(risk_score)))`; raise `SchemaValidationError` if non-numeric
    - Apply `derive_risk_label` to self-heal any `risk_label` inconsistency
    - Validate each `risk_indicator` item for required fields (`category`, `indicator`, `explanation`, `severity`, `evidence_quote`); raise `SchemaValidationError` with item index and missing field name
    - Validate each `safety_step` item for required fields (`action`, `reason`, `priority`); raise `SchemaValidationError` with item index and missing field name
    - Return a fully-populated `ScamAnalysisReport` on success
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

  - [ ]* 2.2 Write property test for score clamping (Property 1)
    - **Property 1: Score Boundedness and Self-Healing** — `@given(st.integers())` — assert `clamp_score(n)` always returns a value in `[0, 100]`
    - **Validates: Requirements 5.3, 7.1**

  - [ ]* 2.3 Write property test for serialization round-trip (Property 10)
    - **Property 10: Serialization Round-Trip** — build a `ScamAnalysisReport` from a valid dict, serialize via `json.dumps`, deserialize via `json.loads`, assert all fields compare equal
    - **Validates: Requirements 13.2, 5.8**

  - [ ]* 2.4 Write unit tests for `SchemaValidator` in `tests/test_schema_validator.py`
    - Test valid JSON → successful `ScamAnalysisReport` with all fields populated
    - Test invalid JSON string → `SchemaValidationError` raised
    - Test missing required top-level field → `SchemaValidationError` with field name in message
    - Test out-of-range `risk_score` (e.g., -5, 150) → clamped to `[0, 100]`
    - Test mismatched `risk_label` → self-healed to correct label
    - Test malformed `risk_indicators` item → `SchemaValidationError` with item index
    - Test malformed `safety_steps` item → `SchemaValidationError` with item index
    - _Requirements: 5.1–5.8_

- [ ] 3. Implement `DomainAuditor`
  - [ ] 3.1 Implement `audit_domain(company_input: str) -> DomainAuditResult` in `domain_auditor.py`
    - Use `urllib.parse.urlparse` to parse the input; return `DomainAuditResult(is_auditable=False, ...)` with advisory flag if scheme is not `http` or `https`
    - Extract `parsed.hostname.lower()` as domain
    - Set `uses_https` flag and append HTTP-insecure flag string if scheme is `http`
    - Check domain against the exact free-email set; set `is_free_email_domain=True` and append flag if matched
    - Attempt WHOIS lookup inside `try/except`; set 10-second timeout; append new-domain flag if `domain_age_days < 180`; set `domain_age_days=None` on any failure
    - Never raise; all exceptions caught internally
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [ ]* 3.2 Write property test for domain audit safety (Property 4)
    - **Property 4: Domain Audit Safety** — `@given(st.text())` — assert `DomainAuditor().audit_domain(s)` always returns a `DomainAuditResult` and never raises for any string
    - **Validates: Requirements 2.2, 2.8**

  - [ ]* 3.3 Write unit tests for `DomainAuditor` in `tests/test_domain_auditor.py`
    - Test HTTPS URL → `uses_https=True`, no HTTP flag
    - Test HTTP URL → `uses_https=False`, HTTP insecure flag appended
    - Test free email domain (e.g., `http://gmail.com`) → `is_free_email_domain=True`, flag appended
    - Test non-URL string → `is_auditable=False`, advisory flag present
    - Test empty string → `is_auditable=False`, no exception raised
    - Test WHOIS timeout (mock `whois.query` to raise `Exception`) → `domain_age_days=None`, no exception raised
    - _Requirements: 2.1–2.8_

- [ ] 4. Implement `PromptBuilder`
  - [ ] 4.1 Implement `build_prompt(request, domain_result) -> tuple[str, dict]` in `prompt_builder.py`
    - Define `PROMPT_VERSION = "v1.0"` constant; embed it verbatim in the prompt text
    - Embed `request.company_input` verbatim between `=== COMPANY / SOURCE ===` delimiters
    - Embed `request.jd_text` verbatim between `=== JOB DESCRIPTION / EMAIL TEXT ===` delimiters
    - Inject all non-empty flags from `domain_result.flags` into `=== DOMAIN AUDIT FLAGS ===`; insert `"No domain flags detected"` placeholder when flags list is empty
    - Include instructions to evaluate all six `RiskCategory` dimensions
    - Return `(prompt_str, SCAM_ANALYSIS_SCHEMA)` as a tuple; raise immediately if flag injection fails
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 12.3_

  - [ ]* 4.2 Write property test for prompt embedding round-trip (Property 9)
    - **Property 9: Prompt Embedding Round-Trip** — `@given(st.text(min_size=50), st.text(min_size=1, max_size=500))` — assert that the built prompt contains `company_input` and `jd_text` verbatim within their delimited sections
    - **Validates: Requirements 3.1, 12.3, 13.1**

  - [ ]* 4.3 Write unit tests for `PromptBuilder` in `tests/test_prompt_builder.py`
    - Test that returned schema dict equals `SCAM_ANALYSIS_SCHEMA`
    - Test that `=== COMPANY / SOURCE ===` section contains verbatim `company_input`
    - Test that `=== JOB DESCRIPTION / EMAIL TEXT ===` section contains verbatim `jd_text`
    - Test that `=== DOMAIN AUDIT FLAGS ===` section contains all flag strings when flags are present
    - Test that `=== DOMAIN AUDIT FLAGS ===` section contains `"No domain flags detected"` when flags list is empty
    - Test that prompt string contains the version string `"v1.0"`
    - _Requirements: 3.1–3.6_

- [ ] 5. Implement `GeminiClient`
  - [ ] 5.1 Implement `GeminiClient` class in `gemini_client.py`
    - In `__init__`, read `GEMINI_API_KEY` from `os.environ` or `st.secrets`; raise `ConfigurationError` immediately if absent or empty
    - Configure `genai.GenerativeModel("gemini-1.5-flash")` with a system instruction
    - Implement `generate(prompt: str, response_schema: dict) -> str` with `generation_config` setting `response_mime_type="application/json"`, `temperature=0.2`, `max_output_tokens=2048`, and the provided `response_schema`
    - Apply retry loop: up to 3 attempts; on transient HTTP status codes `{429, 500, 502, 503, 504}` sleep `1.0 * 2^attempt` seconds and retry; on fatal codes raise `GeminiAPIError` immediately without retrying
    - After all 3 attempts exhausted raise `GeminiAPIError("Max retries exhausted")`
    - If `response.text` is `None`, empty, or whitespace-only raise `GeminiAPIError("Empty response from Gemini")`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 12.2_

  - [ ]* 5.2 Write property test for retry backoff (Property 14)
    - **Property 14: GeminiClient Retry Backoff** — mock the model to fail N times (N < 3) with a transient error then succeed; assert exactly N+1 calls made and delays match `1.0 * 2^i` pattern
    - **Validates: Requirements 4.3, 4.4**

  - [ ]* 5.3 Write unit tests for `GeminiClient` in `tests/test_gemini_client.py`
    - Test that `ConfigurationError` is raised when `GEMINI_API_KEY` is absent (mock env)
    - Test that `ConfigurationError` is raised when `GEMINI_API_KEY` is an empty string
    - Test successful response returns raw JSON string
    - Test empty/whitespace response raises `GeminiAPIError("Empty response from Gemini")`
    - Test that a fatal HTTP error code (e.g., 400) raises `GeminiAPIError` without retrying
    - Test that after 3 transient errors `GeminiAPIError` is raised
    - _Requirements: 4.1–4.9_

- [ ] 6. Checkpoint — core services complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Implement `AnalysisOrchestrator`
  - [ ] 7.1 Implement `analyze(request: AnalysisRequest) -> ScamAnalysisReport` in `orchestrator.py`
    - Stage 1: Call `DomainAuditor.audit_domain(request.company_input)`; emit structured log entry with stage name, status, and UTC timestamp
    - Stage 2: Call `PromptBuilder.build_prompt(request, domain_result)`; catch any exception from `PromptBuilder` and return `FallbackReport` with `is_fallback=True` and `error_message` containing exception type and message; emit log entry
    - Stage 3: Call `GeminiClient.generate(prompt, schema)`; catch `GeminiAPIError` and return `FallbackReport`; emit log entry
    - Stage 4: Call `SchemaValidator.validate(raw_json)`; catch `SchemaValidationError` and return `FallbackReport`; emit log entry
    - Return `ScamAnalysisReport` with `is_fallback=False` when all stages succeed
    - Never raise for any `AnalysisRequest` with non-null `company_input` and `jd_text`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9_

  - [ ]* 7.2 Write property test for no-raise guarantee (Property 3)
    - **Property 3: No-Raise Guarantee** — `@given(st.text(min_size=1, max_size=500), st.text(min_size=50, max_size=10000))` — mock `GeminiClient` to raise `GeminiAPIError`; assert `orchestrator.analyze(request)` always returns a `ScamAnalysisReport` and never raises
    - **Validates: Requirements 6.3, 6.4, 6.5**

  - [ ]* 7.3 Write property test for fallback completeness (Property 7)
    - **Property 7: Fallback Completeness** — for any report returned by `analyze()`, assert `report.is_fallback == (report.error_message is not None)` holds; the two states are mutually exclusive
    - **Validates: Requirements 7.5, 7.6, 6.3, 6.4**

  - [ ]* 7.4 Write unit tests for `AnalysisOrchestrator` in `tests/test_orchestrator.py`
    - Test full happy path with mocked `GeminiClient` returning valid JSON → `is_fallback=False`
    - Test `GeminiAPIError` from client → `FallbackReport` with `is_fallback=True` and non-empty `error_message`
    - Test `SchemaValidationError` from validator → `FallbackReport`
    - Test `PromptBuilder` exception → `FallbackReport`
    - Test that domain auditor internal error still allows pipeline to continue
    - Test that four structured log entries are emitted for each pipeline stage
    - _Requirements: 6.1–6.9_

- [ ] 8. Implement Dashboard rendering components
  - [ ] 8.1 Implement `render_trust_score_gauge(report: ScamAnalysisReport) -> None` in `dashboard.py`
    - If `report.is_fallback=True`, render `st.error` banner with `report.error_message` and return early; do not render score, indicators, or checklist
    - Map `risk_score` to color: `≥70` → red (`#d32f2f`), `40–69` → yellow (`#f9a825`), `<40` → green (`#388e3c`)
    - Render `st.metric` with score value and `risk_label`
    - Render `st.progress(report.risk_score / 100)` styled with the mapped color via `st.markdown` HTML injection
    - Display `report.summary` beneath the score; show default placeholder text if `summary` is null or empty
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ] 8.2 Implement `render_risk_indicators(report: ScamAnalysisReport) -> None` in `dashboard.py`
    - Sort `risk_indicators` by severity: `high` → `medium` → `low`
    - Render each indicator as a `st.expander` collapsed by default showing category badge, indicator label, severity tag
    - When expanded show explanation text and evidence quote in a styled blockquote via `st.markdown`
    - Apply a unique background/border color for each of the six `RiskCategory` values
    - Apply distinct visual treatment per severity level (high/medium/low)
    - Display `"No suspicious patterns detected"` when `risk_indicators` is empty
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ] 8.3 Implement `render_safety_checklist(report: ScamAnalysisReport) -> None` in `dashboard.py`
    - Sort `safety_steps` by priority: `urgent` → `recommended` → `informational`; preserve original order within same priority
    - Render each step as a row with a priority badge in Title Case, bold action text, and muted reason text via `st.markdown`
    - Display `"No immediate actions required"` when `safety_steps` is empty
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ]* 8.4 Write property test for dashboard color coding consistency (Property 11)
    - **Property 11: Dashboard Color Coding Consistency** — `@given(st.integers(min_value=0, max_value=100))` — call the color-mapping helper with any score in `[0, 100]`; assert the returned color matches the expected bucket and is never `None` or empty
    - **Validates: Requirements 8.2, 8.3, 8.4**

  - [ ]* 8.5 Write property test for safety checklist ordering (Property 13)
    - **Property 13: Safety Checklist Ordering** — generate a random list of `SafetyStep` objects with shuffled priorities; assert rendered output order is always `urgent` → `recommended` → `informational` with original intra-priority order preserved
    - **Validates: Requirements 10.3**

  - [ ]* 8.6 Write property test for fallback dashboard exclusion (Property 15)
    - **Property 15: Fallback Dashboard Exclusion** — for any `ScamAnalysisReport` with `is_fallback=True`, assert that the fallback banner is rendered and that no trust score, risk indicator list, or safety checklist content is rendered
    - **Validates: Requirements 8.6**

  - [ ]* 8.7 Write property test for risk indicator rendering completeness (Property 12)
    - **Property 12: Risk Indicator Rendering Completeness** — `@given(st.lists(...))` — for any non-empty `risk_indicators` list, assert the rendered HTML/markdown output contains each indicator's category, label, severity, explanation, and evidence quote with no entry omitted
    - **Validates: Requirements 9.1, 9.2**

  - [ ]* 8.8 Write unit tests for dashboard components in `tests/test_dashboard.py`
    - Test `render_trust_score_gauge` with `risk_score=85` → red color applied
    - Test `render_trust_score_gauge` with `risk_score=55` → yellow color applied
    - Test `render_trust_score_gauge` with `risk_score=20` → green color applied
    - Test `render_trust_score_gauge` with `is_fallback=True` → only error banner rendered
    - Test `render_risk_indicators` with empty list → "No suspicious patterns detected" message
    - Test `render_risk_indicators` with mixed-severity indicators → sorted high first
    - Test `render_safety_checklist` with empty list → "No immediate actions required" message
    - Test `render_safety_checklist` with shuffled priorities → urgent first
    - _Requirements: 8.1–8.6, 9.1–9.5, 10.1–10.4_

- [ ] 9. Implement `IntakeForm` and wire the main `app.py`
  - [ ] 9.1 Implement `render_intake_form() -> Optional[AnalysisRequest]` in `app.py` or a dedicated `intake_form.py`
    - Render `st.text_input("Company Name or URL")` with placeholder text
    - Render `st.text_area("Job Description or Email Text", height=250)` with placeholder text
    - Display live character counts for both fields updating on each keystroke using `st.caption`
    - Validate on submit: company field empty/whitespace → inline `st.error`; JD empty/whitespace → inline `st.error`
    - Validate `len(jd_text.strip()) < 50` → `st.warning` prompting more content
    - Validate `len(company_input.strip()) > 500` → `st.error` with character limit message
    - Validate `len(jd_text.strip()) > 10000` → `st.error` with character limit message
    - On valid submit, construct `AnalysisRequest(company_input=company_input.strip(), jd_text=jd_text.strip())` and return it
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [ ] 9.2 Wire full pipeline in `app.py`
    - Set page config: `st.set_page_config(page_title="AI Job Scam Detector", page_icon="🔍", layout="wide")`
    - Display title and caption
    - Call `render_intake_form()`; when an `AnalysisRequest` is returned, run the pipeline inside `st.spinner("Analyzing with AI... this may take a few seconds")`
    - Implement 120-second timeout check; if exceeded dismiss spinner and display timeout error message
    - On `is_fallback=True`, render `render_trust_score_gauge` (which handles the error banner internally)
    - On `is_fallback=False`, call `render_trust_score_gauge`, `render_safety_checklist`, `render_risk_indicators` in a two-column layout
    - Do not carry results across sessions (no `st.session_state` persistence between page loads)
    - _Requirements: 6.1, 11.1, 11.2, 11.3, 12.1, 12.4_

  - [ ]* 9.3 Write property test for input validation (Property 8)
    - **Property 8: Input Validation Rejects All Invalid Inputs** — `@given(st.text())` — assert that the validation logic rejects any `company_input` with `len > 500` or blank, and any `jd_text` with `len < 50` or `len > 10000` or blank, and never constructs an `AnalysisRequest` for invalid inputs
    - **Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.6_

  - [ ]* 9.4 Write unit tests for `IntakeForm` validation logic in `tests/test_intake_form.py`
    - Test empty company field → validation rejects, no `AnalysisRequest` returned
    - Test whitespace-only company field → validation rejects
    - Test JD shorter than 50 chars → validation rejects with warning
    - Test company exceeding 500 chars → validation rejects with char limit message
    - Test JD exceeding 10,000 chars → validation rejects with char limit message
    - Test valid inputs at boundaries (50-char JD, 500-char company) → `AnalysisRequest` constructed with trimmed values
    - _Requirements: 1.2–1.7_

- [ ] 10. Checkpoint — full pipeline integrated
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Add property tests for cross-component properties
  - [ ]* 11.1 Write property test for indicator non-empty on high risk (Property 5)
    - **Property 5: Indicator Non-Empty on High Risk** — for any `ScamAnalysisReport` with `risk_score ≥ 70` produced by `SchemaValidator`, assert `len(report.risk_indicators) ≥ 1` and each has a non-empty `evidence_quote`
    - **Validates: Requirements 7.3, 7.10**

  - [ ]* 11.2 Write property test for safety steps non-empty on risk (Property 6)
    - **Property 6: Safety Steps Non-Empty on Risk** — for any `ScamAnalysisReport` with `risk_score ≥ 40`, assert `len(report.safety_steps) ≥ 1`
    - **Validates: Requirements 7.4**

- [ ] 12. Deployment configuration
  - [ ] 12.1 Finalize `requirements.txt` with pinned versions and verify all imports resolve
    - Confirm `streamlit>=1.35.0`, `google-generativeai>=0.7.0`, `python-whois>=0.9.4`, `hypothesis>=6.100.0`, `pytest>=8.2.0` are all present
    - Add a `pytest.ini` or `pyproject.toml` `[tool.pytest.ini_options]` section setting `testpaths = ["tests"]`
    - _Requirements: 12.2_

  - [ ] 12.2 Create Streamlit Cloud deployment configuration
    - Create `.streamlit/config.toml` with `[server] headless = true` and `[theme]` branding if desired
    - Document in `README.md` how to set `GEMINI_API_KEY` via Streamlit secrets for cloud deployment
    - _Requirements: 4.8, 4.9, 12.2, 12.5_

- [ ] 13. Final checkpoint — ensure all tests pass
  - Run `pytest --tb=short` and confirm zero failures; ask the user if any questions arise before closing.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP build
- All property tests use the `hypothesis` library; run with `pytest tests/ --tb=short`
- The design uses Python — no language selection step is required
- `GeminiClient` must never be instantiated in test code without a mocked API key env variable
- WHOIS lookups are network calls; mock `whois.query` in all unit tests to avoid flakiness
- Each property test task is annotated with its property number from the design document
- Checkpoints at tasks 6 and 10 ensure incremental validation at natural integration boundaries

---

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "4.1"] },
    { "id": 4, "tasks": ["4.2", "4.3", "5.1"] },
    { "id": 5, "tasks": ["5.2", "5.3", "7.1"] },
    { "id": 6, "tasks": ["7.2", "7.3", "7.4", "8.1"] },
    { "id": 7, "tasks": ["8.2", "8.3"] },
    { "id": 8, "tasks": ["8.4", "8.5", "8.6", "8.7", "8.8", "9.1"] },
    { "id": 9, "tasks": ["9.2", "11.1", "11.2"] },
    { "id": 10, "tasks": ["9.3", "9.4", "12.1"] },
    { "id": 11, "tasks": ["12.2"] }
  ]
}
```
