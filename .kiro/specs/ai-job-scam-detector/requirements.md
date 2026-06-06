# Requirements Document

## Introduction

The AI Job Scam Detector is a Streamlit web application that helps college students (particularly those hunting for internships in India) identify fraudulent job postings and recruitment emails. A student pastes a company name or URL and the raw job description or email text. The system routes this input through a Google Gemini-powered multi-step analysis pipeline that evaluates linguistic red flags, domain/metadata anomalies, financial fraud patterns, and high-pressure semantic cues. The output is a structured risk report rendered as a live dashboard: a color-coded Job Trust Score (0–100), categorized Detected Risk Indicators, and an actionable Student Safety Checklist.

---

## Glossary

- **IntakeForm**: The Streamlit UI component that collects user input (company name/URL and job description text).
- **AnalysisOrchestrator**: The central Python service that sequences domain audit, prompt construction, Gemini API call, and schema validation into a single pipeline.
- **PromptBuilder**: The service component that constructs the structured Gemini prompt and response schema from the analysis request and domain audit result.
- **GeminiClient**: The thin wrapper around the Google Gemini API SDK that enforces structured JSON output mode and applies retry logic.
- **SchemaValidator**: The component that parses and validates raw JSON from Gemini against the `ScamAnalysisReport` model.
- **DomainAuditor**: The component that performs lightweight URL/domain sanity checks (HTTPS usage, free email domains, domain age).
- **Dashboard**: The collection of Streamlit rendering components (`render_trust_score_gauge`, `render_risk_indicators`, `render_safety_checklist`) that display the analysis result.
- **AnalysisRequest**: A dataclass holding `company_input` (company name or URL) and `jd_text` (raw job description or email text).
- **ScamAnalysisReport**: The structured output dataclass containing `risk_score`, `risk_label`, `summary`, `risk_indicators`, `safety_steps`, `confidence`, and `analysis_version`.
- **FallbackReport**: A `ScamAnalysisReport` with `is_fallback=True` and a populated `error_message`, returned when the pipeline encounters an unrecoverable error.
- **DomainAuditResult**: The structured output of the `DomainAuditor` containing domain metadata flags.
- **RiskIndicator**: A single detected fraud signal with a category, indicator label, explanation, severity, and evidence quote.
- **SafetyStep**: An actionable recommendation for the student with an action, reason, and priority.
- **RiskCategory**: An enumeration of fraud signal categories: `linguistic`, `financial`, `domain`, `identity`, `process`, `compensation`.
- **Job_Trust_Score**: The integer value (0–100) where 0 means completely legitimate and 100 means definite scam.
- **GEMINI_API_KEY**: The environment variable or Streamlit secret holding the Google Gemini API key.

---

## Requirements

### Requirement 1: Student Input Collection

**User Story:** As a college student, I want to paste a company name or URL and a job description into a web form, so that I can submit suspicious job postings for analysis.

#### Acceptance Criteria

1. THE IntakeForm SHALL render a text input field labeled "Company Name or URL" and a text area labeled "Job Description or Email Text".
2. WHEN a student submits the form with a company name field that is empty or contains only whitespace, THE IntakeForm SHALL prevent submission and display an inline validation message.
3. WHEN a student submits the form with a job description field that is empty or contains only whitespace, THE IntakeForm SHALL prevent submission and display an inline validation message.
4. WHEN a student submits a job description shorter than 50 characters (excluding leading/trailing whitespace), THE IntakeForm SHALL prevent submission and display a warning prompting the student to paste more content.
5. WHEN a student submits a company input exceeding 500 characters, THE IntakeForm SHALL prevent submission and display a character limit validation message.
6. WHEN a student submits a job description exceeding 10,000 characters, THE IntakeForm SHALL prevent submission and display a character limit validation message.
7. WHEN a student submits input where `company_input` is non-empty, non-whitespace-only, and within 1–500 characters, AND `jd_text` is non-empty, non-whitespace-only, and within 50–10,000 characters, THE IntakeForm SHALL construct an AnalysisRequest with `company_input` set to the trimmed company field value and `jd_text` set to the trimmed job description value, and pass it to the AnalysisOrchestrator.
8. THE IntakeForm SHALL display a live character count for both input fields, updating on each keystroke, along with placeholder text guiding the student on what to paste.

---

### Requirement 2: Domain Audit

**User Story:** As a student, I want the system to automatically check whether the company URL looks suspicious, so that obvious structural red flags are surfaced before AI analysis.

#### Acceptance Criteria

1. WHEN an AnalysisRequest is received by the DomainAuditor, THE DomainAuditor SHALL attempt to parse `company_input` as a URL using standard URL parsing and extract the hostname.
2. IF `company_input` cannot be parsed as a URL with an `http` or `https` scheme, THEN THE DomainAuditor SHALL return a DomainAuditResult with `is_auditable=False` and a flag message recommending manual domain verification.
3. WHEN the parsed URL uses `http` instead of `https`, THE DomainAuditor SHALL include a flag indicating an insecure connection.
4. WHEN the extracted domain exactly matches one of the specified free email providers (gmail.com, yahoo.com, outlook.com, hotmail.com, rediffmail.com, ymail.com, protonmail.com), THE DomainAuditor SHALL set `is_free_email_domain=True` and include a flag indicating this is a red flag for corporate roles; domains not in this list SHALL NOT be flagged as free email providers.
5. WHEN `is_auditable=True`, THE DomainAuditor SHALL attempt a WHOIS lookup for the extracted domain.
6. IF a WHOIS lookup result is available and the domain registration date is within 180 days of the current date, THEN THE DomainAuditor SHALL include a flag warning that the domain is very new.
7. IF a WHOIS lookup fails, times out (after 10 seconds), or returns no creation date, THEN THE DomainAuditor SHALL silently skip the lookup result and return a DomainAuditResult with `domain_age_days=None`.
8. THE DomainAuditor SHALL never raise an exception for any string input (including empty strings); all errors SHALL be handled internally and reflected in the returned DomainAuditResult.

---

### Requirement 3: Prompt Construction

**User Story:** As a developer, I want the system to construct a structured prompt that instructs Gemini to act as a multi-agent scam evaluator, so that the AI analysis is consistent, contextualized, and schema-bound.

#### Acceptance Criteria

1. WHEN building a prompt, THE PromptBuilder SHALL embed `company_input` verbatim within a section explicitly labeled `=== COMPANY / SOURCE ===` and `jd_text` verbatim within a section explicitly labeled `=== JOB DESCRIPTION / EMAIL TEXT ===`.
2. WHEN building a prompt, THE PromptBuilder SHALL inject all non-empty flags from the DomainAuditResult into a section explicitly labeled `=== DOMAIN AUDIT FLAGS ===`; IF domain flag injection fails for any reason, THEN THE PromptBuilder SHALL raise an error and halt prompt construction entirely.
3. WHEN building a prompt, THE PromptBuilder SHALL include explicit instructions for Gemini to evaluate the submission across all six RiskCategory dimensions: linguistic, financial, compensation, identity, domain, and process — regardless of whether any domain audit flags were detected.
4. THE PromptBuilder SHALL return the `SCAM_ANALYSIS_SCHEMA` JSON Schema dict as the `response_schema` alongside the prompt string.
5. THE PromptBuilder SHALL embed a non-empty prompt version string (e.g., `v1.0`) within the constructed prompt text so that the version is identifiable by inspection.
6. WHEN `domain_result.flags` is empty, THE PromptBuilder SHALL insert a non-empty placeholder string (e.g., "No domain flags detected") within the `=== DOMAIN AUDIT FLAGS ===` section.

---

### Requirement 4: Gemini API Integration

**User Story:** As a developer, I want the system to call the Google Gemini API with enforced structured JSON output, so that the AI response is always type-safe and parseable.

#### Acceptance Criteria

1. THE GeminiClient SHALL configure every API call with `response_mime_type="application/json"` and the provided `response_schema` to enforce structured output.
2. THE GeminiClient SHALL set `temperature=0.2` and `max_output_tokens=2048` for every API call.
3. WHEN an API call returns an HTTP error with status code in {429, 500, 502, 503, 504}, THE GeminiClient SHALL retry the call using exponential backoff with a base delay of 1.0 second, a maximum delay of 16.0 seconds, and a maximum of 3 total attempts.
4. IF all 3 retry attempts are exhausted, THEN THE GeminiClient SHALL raise a `GeminiAPIError`.
5. IF an API call returns an HTTP error with a status code not in the transient set {429, 500, 502, 503, 504}, THEN THE GeminiClient SHALL raise a `GeminiAPIError` immediately without retrying.
6. WHEN Gemini returns a response where the text field is None, an empty string, or contains only whitespace, THE GeminiClient SHALL raise a `GeminiAPIError` with the message "Empty response from Gemini".
7. THE GeminiClient SHALL use the `gemini-1.5-flash` model to minimize API latency.
8. THE GeminiClient SHALL read the `GEMINI_API_KEY` from environment variables or Streamlit secrets and SHALL NOT accept the key as a hardcoded value.
9. IF `GEMINI_API_KEY` is not set or is an empty string at initialization time, THEN THE GeminiClient SHALL raise a `ConfigurationError` immediately before making any API call.

---

### Requirement 5: Schema Validation and Self-Healing

**User Story:** As a developer, I want the system to validate and self-heal the Gemini JSON response, so that students always receive a consistent and accurate risk report regardless of AI output drift.

#### Acceptance Criteria

1. WHEN a raw JSON string is received from Gemini, THE SchemaValidator SHALL parse it and verify all required top-level fields are present: `risk_score`, `risk_label`, `summary`, `confidence`, `analysis_version`, `risk_indicators`, `safety_steps`.
2. IF the raw JSON is not valid JSON, or a required top-level field is absent, THEN THE SchemaValidator SHALL raise a `SchemaValidationError` whose message identifies the missing field or parse failure reason.
3. IF `risk_score` is a numeric value outside the range [0, 100], THEN THE SchemaValidator SHALL clamp it to `max(0, min(100, int(risk_score)))`; IF `risk_score` is non-numeric or cannot be cast to int, THEN THE SchemaValidator SHALL raise a `SchemaValidationError`.
4. WHEN `risk_label` is inconsistent with `risk_score` (i.e., does not match the deterministic derivation rule), THE SchemaValidator SHALL override `risk_label` with the correct value derived from `risk_score`.
5. THE SchemaValidator SHALL derive `risk_label` deterministically: `risk_score ≥ 70` → `"HIGH RISK"`, `40 ≤ risk_score < 70` → `"MEDIUM RISK"`, `risk_score < 40` → `"LOW RISK"`.
6. IF any item in `risk_indicators` is missing one or more of the required fields (`category`, `indicator`, `explanation`, `severity`, `evidence_quote`), THEN THE SchemaValidator SHALL raise a `SchemaValidationError` identifying the malformed item index and missing field.
7. IF any item in `safety_steps` is missing one or more of the required fields (`action`, `reason`, `priority`), THEN THE SchemaValidator SHALL raise a `SchemaValidationError` identifying the malformed item index and missing field.
8. THE SchemaValidator SHALL return a fully-populated ScamAnalysisReport on success.

---

### Requirement 6: Analysis Pipeline Orchestration

**User Story:** As a student, I want the system to coordinate domain audit, prompt construction, AI analysis, and validation into a single seamless pipeline, so that I receive a complete risk report from a single submission.

#### Acceptance Criteria

1. WHEN an AnalysisRequest is received, THE AnalysisOrchestrator SHALL execute the pipeline in order: domain audit → prompt construction → Gemini API call → schema validation → report delivery.
2. THE AnalysisOrchestrator SHALL pass the DomainAuditResult from the DomainAuditor to the PromptBuilder before constructing the Gemini prompt.
3. IF the GeminiClient raises a `GeminiAPIError`, THEN THE AnalysisOrchestrator SHALL immediately construct and return a FallbackReport with `is_fallback=True` and `error_message` containing the exception type and message text, skipping schema validation entirely.
4. IF the SchemaValidator raises a `SchemaValidationError`, THEN THE AnalysisOrchestrator SHALL construct and return a FallbackReport with `is_fallback=True` and `error_message` containing the exception type and message text.
5. THE AnalysisOrchestrator SHALL never raise an exception for any AnalysisRequest that passes input validation (non-null `company_input` and `jd_text` fields); all pipeline errors SHALL be captured in a FallbackReport.
6. THE AnalysisOrchestrator SHALL emit a structured log entry — containing at minimum the stage name, status (started/completed/failed), and UTC timestamp — for each of the four pipeline stages.
7. WHEN all four pipeline stages complete without raising an exception, THE AnalysisOrchestrator SHALL return a ScamAnalysisReport with `is_fallback=False`.
8. IF the DomainAuditor returns a DomainAuditResult indicating an internal error (e.g., unexpected exception caught internally), THE AnalysisOrchestrator SHALL continue the pipeline using that DomainAuditResult and SHALL NOT treat it as a pipeline failure.
9. IF the PromptBuilder raises any exception, THEN THE AnalysisOrchestrator SHALL construct and return a FallbackReport with `is_fallback=True` and `error_message` containing the exception type and message text.

---

### Requirement 7: Risk Report Data Model Integrity

**User Story:** As a developer, I want the ScamAnalysisReport to enforce data integrity rules, so that every report delivered to the student is internally consistent and valid.

#### Acceptance Criteria

1. THE ScamAnalysisReport SHALL always contain a `risk_score` in the integer range [0, 100].
2. THE ScamAnalysisReport SHALL always contain a `risk_label` that is one of `"HIGH RISK"`, `"MEDIUM RISK"`, or `"LOW RISK"`.
3. IF `risk_score ≥ 70`, THEN THE ScamAnalysisReport SHALL contain at least one RiskIndicator in `risk_indicators`.
4. IF `risk_score ≥ 40`, THEN THE ScamAnalysisReport SHALL contain at least one SafetyStep in `safety_steps`.
5. IF `is_fallback=True`, THEN THE ScamAnalysisReport SHALL have a non-null, non-empty `error_message`.
6. IF `is_fallback=False`, THEN THE ScamAnalysisReport SHALL have a null `error_message`.
7. THE ScamAnalysisReport SHALL contain a non-empty `analysis_version` string identifying the prompt/schema version used.
8. THE ScamAnalysisReport SHALL contain a `confidence` field with value `"high"`, `"medium"`, or `"low"`.
9. Each RiskIndicator SHALL have a `severity` field with value `"high"`, `"medium"`, or `"low"`.
10. Each RiskIndicator SHALL have a non-empty `evidence_quote` field containing a verbatim substring (up to 500 characters) from the submitted `jd_text` or `company_input` that triggered the indicator.
11. Each SafetyStep SHALL have a `priority` field with value `"urgent"`, `"recommended"`, or `"informational"`.
12. IF `is_fallback=True`, THEN THE ScamAnalysisReport SHALL have `risk_score=0`, `risk_label="LOW RISK"`, `risk_indicators=[]`, and `safety_steps=[]`.

---

### Requirement 8: Trust Score Dashboard Rendering

**User Story:** As a student, I want to see a color-coded Job Trust Score on a visual dashboard, so that I can immediately understand the risk level of the job posting.

#### Acceptance Criteria

1. WHEN rendering a ScamAnalysisReport with `is_fallback=False`, THE Dashboard SHALL display the `risk_score` as a numeric metric alongside a progress bar filled proportionally to `risk_score` on a 0–100 scale.
2. WHEN rendering a ScamAnalysisReport with `is_fallback=False` and `risk_score ≥ 70`, THE Dashboard SHALL render the score, label, and progress bar in red to indicate HIGH RISK.
3. WHEN rendering a ScamAnalysisReport with `is_fallback=False` and `40 ≤ risk_score < 70`, THE Dashboard SHALL render the score, label, and progress bar in yellow to indicate MEDIUM RISK.
4. WHEN rendering a ScamAnalysisReport with `is_fallback=False` and `risk_score < 40`, THE Dashboard SHALL render the score, label, and progress bar in green to indicate LOW RISK.
5. WHEN rendering a ScamAnalysisReport with `is_fallback=False`, THE Dashboard SHALL display `report.summary` beneath the trust score; IF `report.summary` is null or empty, THE Dashboard SHALL display a default placeholder message.
6. WHEN `is_fallback=True`, THE Dashboard SHALL display a warning banner containing the `error_message` and SHALL NOT render any trust score, risk indicator list, or safety checklist.

---

### Requirement 9: Risk Indicators Rendering

**User Story:** As a student, I want to see a categorized list of detected risk signals with explanations and evidence, so that I understand specifically why the job posting was flagged.

#### Acceptance Criteria

1. WHEN `risk_indicators` is non-empty, THE Dashboard SHALL render each RiskIndicator as a card that is collapsed by default, showing the category badge, indicator label, and severity tag in its collapsed state.
2. WHEN a RiskIndicator card is expanded, THE Dashboard SHALL additionally display a 1–2 sentence explanation and the evidence quote styled as a blockquote; the severity tag SHALL be styled with a distinct visual treatment per severity level (high, medium, low) such that each level is visually distinguishable from the others.
3. WHEN `risk_indicators` is empty, THE Dashboard SHALL display a "No suspicious patterns detected" message in place of the risk indicator list.
4. THE Dashboard SHALL apply a unique visual style (color or background) to each of the six RiskCategory values (linguistic, financial, domain, identity, process, compensation) such that no two categories share the same style.
5. WHEN `risk_indicators` contains multiple entries, THE Dashboard SHALL display them sorted by severity in the order: `high` → `medium` → `low`.

---

### Requirement 10: Safety Checklist Rendering

**User Story:** As a student, I want to see an actionable checklist of safety steps tailored to the specific job posting I submitted, so that I know exactly what to do to protect myself.

#### Acceptance Criteria

1. WHEN `safety_steps` is non-empty, THE Dashboard SHALL render each SafetyStep as a checklist row.
2. WHEN rendering a SafetyStep, THE Dashboard SHALL display a priority badge using Title Case (`Urgent`, `Recommended`, or `Informational` mapping from the lowercase field values `urgent`, `recommended`, `informational` respectively), the action text in bold, and the reason in a visually subdued style (e.g., smaller font or lighter color) that is distinguishable from the action text.
3. WHEN rendering a list of SafetySteps, THE Dashboard SHALL display all `urgent` steps before all `recommended` steps, and all `recommended` steps before all `informational` steps; steps with the same priority SHALL maintain their original list order.
4. WHEN `safety_steps` is empty, THE Dashboard SHALL display a "No immediate actions required" message instead of the checklist; the checklist and this message are mutually exclusive displays.

---

### Requirement 11: Analysis Loading State

**User Story:** As a student, I want to see a loading indicator while the AI analysis is running, so that I know the system is working and am not left wondering if something went wrong.

#### Acceptance Criteria

1. WHEN an AnalysisRequest is submitted and the pipeline is executing, THE IntakeForm SHALL display a loading spinner with the message "Analyzing with AI... this may take a few seconds".
2. WHEN the pipeline completes successfully or returns a FallbackReport in the current session, THE IntakeForm SHALL dismiss the spinner and render the result dashboard; results from previous sessions in the same browser tab SHALL NOT be displayed.
3. IF the pipeline does not complete within 120 seconds, THE IntakeForm SHALL dismiss the spinner and display an error message indicating that the analysis timed out.

---

### Requirement 12: Security and Privacy

**User Story:** As a student, I want to be sure my submitted job description is not stored or shared, so that I can safely paste sensitive recruitment emails without privacy concerns.

#### Acceptance Criteria

1. THE System SHALL process all AnalysisRequest data in-memory and SHALL NOT persist `company_input`, `jd_text`, or any ScamAnalysisReport to any database, file, or external service; temporary in-memory data within a single request lifecycle is permitted.
2. THE System SHALL never embed or hardcode the `GEMINI_API_KEY` in source code; THE GeminiClient SHALL read it exclusively from environment variables or Streamlit secrets.
3. THE PromptBuilder SHALL embed job description text inside clearly delimited prompt sections (e.g., `=== JOB DESCRIPTION ===`) to mitigate prompt injection from malicious JD content; no additional content sanitization beyond these delimiters is required.
4. THE System SHALL operate statelessly per request — no session data SHALL be shared between different students' submissions.
5. IF `GEMINI_API_KEY` is absent or empty at application startup, THE System SHALL refuse to start and SHALL display a clear error message indicating that the API key is missing, without exposing any partial key value.

---

### Requirement 13: Input Validation Round-Trip

**User Story:** As a developer, I want the PromptBuilder and SchemaValidator to be verifiable through serialization round-trips, so that I can confirm data fidelity end-to-end.

#### Acceptance Criteria

1. THE PromptBuilder SHALL produce a prompt string such that extracting the content between the `=== COMPANY / SOURCE ===` and `=== JOB DESCRIPTION / EMAIL TEXT ===` delimiters returns the original `company_input` and `jd_text` values character-for-character identical to what was passed in.
2. THE SchemaValidator SHALL produce a ScamAnalysisReport such that serializing it to JSON via `json.dumps` and deserializing it back via `json.loads` produces an object where every field (`risk_score`, `risk_label`, `summary`, `confidence`, `analysis_version`, `risk_indicators`, `safety_steps`, `is_fallback`, `error_message`) compares equal by value to the original.
3. THE SchemaValidator SHALL ensure that for all ScamAnalysisReport objects it produces, calling `derive_risk_label(report.risk_score)` returns the same value as `report.risk_label`.
